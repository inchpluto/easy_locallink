import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from locallink.server import create_server


class FakePreviewService:
    available = True

    def __init__(self, root: Path):
        self.root = root
        self.removed = []

    def get_or_create(self, record, source: Path) -> Path:
        target = self.root / f"{record.id}.pdf"
        target.write_bytes(b"%PDF-local-link")
        return target

    def remove_record(self, identifier: str) -> None:
        self.removed.append(identifier)


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.server = create_server(Path(self.temp.name), "127.0.0.1", 0, "Test PC", "123456")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.temp.cleanup()

    def request(self, path, method="GET", data=None, headers=None):
        request = urllib.request.Request(self.base + path, data=data, method=method, headers=headers or {})
        with urllib.request.urlopen(request, timeout=3) as response:
            return response.status, response.read(), response.headers

    def test_auth_and_text_round_trip(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request("/api/status")
        self.assertEqual(caught.exception.code, 401)
        body = json.dumps({"text": "局域网消息", "sender": "Phone"}, ensure_ascii=False).encode()
        status, _, _ = self.request(
            "/api/text?code=123456", "POST", body, {"Content-Type": "application/json"}
        )
        self.assertEqual(status, 201)
        _, raw, _ = self.request("/api/status?code=123456")
        status_body = json.loads(raw)
        self.assertEqual(status_body["history"][0]["text"], "局域网消息")
        self.assertEqual(status_body["history"][0]["sender"], "Phone")
        self.assertEqual(status_body["history"][0]["receiver"], "Test PC")
        self.assertEqual(status_body["pairing_code"], "123456")
        self.assertEqual(status_body["storage"]["items"], 1)

    def test_health_does_not_expose_private_state(self):
        status, raw, _ = self.request("/api/health")
        body = json.loads(raw)
        self.assertEqual(status, 200)
        self.assertEqual(body["service"], "locallink")
        self.assertEqual(body["version"], "2")
        self.assertEqual(body["name"], "Test PC")
        self.assertNotIn("pairing_code", body)

    def test_bind_all_keeps_advertised_lan_address(self):
        other = create_server(Path(self.temp.name), "127.0.0.1", 0, "Host", "123456", bind_all=True)
        try:
            self.assertEqual(other.server_address[0], "0.0.0.0")
            self.assertEqual(other.advertised_ip, "127.0.0.1")
        finally:
            other.server_close()

    def test_empty_text_is_rejected(self):
        body = json.dumps({"text": "   ", "sender": "Phone"}).encode()
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request("/api/text?code=123456", "POST", body, {"Content-Type": "application/json"})
        self.assertEqual(caught.exception.code, 400)

    def test_subnet_scan_endpoint_starts_asynchronously(self):
        status, raw, _ = self.request(
            "/api/scan?code=123456", "POST", b"{}", {"Content-Type": "application/json"}
        )
        self.assertEqual(status, 202)
        self.assertTrue(json.loads(raw)["ok"])

    def test_upload_download_and_range(self):
        payload = b"0123456789"
        status, raw, _ = self.request(
            "/api/upload?code=123456",
            "POST",
            payload,
            {"X-Filename": "demo.txt", "Content-Length": str(len(payload))},
        )
        item = json.loads(raw)["item"]
        self.assertEqual(status, 201)
        self.assertEqual(item["receiver"], "Test PC")
        status, body, headers = self.request(
            f"/api/download/{item['id']}?code=123456", headers={"Range": "bytes=2-5"}
        )
        self.assertEqual(status, 206)
        self.assertEqual(body, b"2345")
        self.assertEqual(headers["Accept-Ranges"], "bytes")
        status, body, headers = self.request(f"/api/preview/{item['id']}?code=123456")
        self.assertEqual(status, 200)
        self.assertEqual(body, payload)
        self.assertTrue(headers["Content-Disposition"].startswith("inline;"))

    def test_office_preview_uses_pdf_conversion_service(self):
        preview = FakePreviewService(Path(self.temp.name))
        self.server.preview_service = preview
        payload = b"fake-presentation"
        _, raw, _ = self.request(
            "/api/upload?code=123456", "POST", payload,
            {"X-Filename": "quarterly.pptx", "Content-Length": str(len(payload))},
        )
        item = json.loads(raw)["item"]

        status, body, headers = self.request(
            f"/api/preview/{item['id']}?code=123456&format=pdf"
        )

        self.assertEqual(status, 200)
        self.assertEqual(body, b"%PDF-local-link")
        self.assertEqual(headers.get_content_type(), "application/pdf")
        self.assertTrue(headers["Content-Disposition"].startswith("inline;"))

    def test_delete_record_clears_preview_cache(self):
        preview = FakePreviewService(Path(self.temp.name))
        self.server.preview_service = preview
        _, raw, _ = self.request(
            "/api/upload?code=123456", "POST", b"x",
            {"X-Filename": "notes.docx", "Content-Length": "1"},
        )
        identifier = json.loads(raw)["item"]["id"]

        status, _, _ = self.request(f"/api/items/{identifier}?code=123456", "DELETE")

        self.assertEqual(status, 200)
        self.assertEqual(preview.removed, [identifier])

    def test_receive_callback_and_device_identity(self):
        received = []
        other = create_server(
            Path(self.temp.name) / "notify", "127.0.0.1", 0, "Notify PC", "123456",
            on_receive=received.append,
        )
        thread = threading.Thread(target=other.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{other.server_port}"
            body = json.dumps({"text": "notice", "sender": "Phone"}).encode()
            request = urllib.request.Request(base + "/api/text?code=123456", data=body, method="POST")
            with urllib.request.urlopen(request, timeout=3):
                pass
            self.assertEqual(received[0].text, "notice")
            with urllib.request.urlopen(base + "/api/status?code=123456", timeout=3) as response:
                status = json.loads(response.read())
            self.assertTrue(status["device_id"])
        finally:
            other.shutdown()
            other.server_close()


if __name__ == "__main__":
    unittest.main()
