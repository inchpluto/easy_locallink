import json
import re
import socket
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

    def test_device_identity_survives_server_restart(self):
        data_dir = Path(self.temp.name) / "stable-host"
        first = create_server(data_dir, "127.0.0.1", 0, "Stable PC", "123456")
        first_id = first.device_id
        first.server_close()

        second = create_server(data_dir, "127.0.0.1", 0, "Stable PC", "123456")
        try:
            self.assertEqual(second.device_id, first_id)
        finally:
            second.server_close()

    def test_different_data_directories_have_different_identities(self):
        first = create_server(Path(self.temp.name) / "host-a", "127.0.0.1", 0, "A", "123456")
        second = create_server(Path(self.temp.name) / "host-b", "127.0.0.1", 0, "B", "123456")
        try:
            self.assertNotEqual(first.device_id, second.device_id)
        finally:
            first.server_close()
            second.server_close()


class PreviewConfinementTests(unittest.TestCase):
    """Inline previews share the console origin, so they must not run scripts."""

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

    def upload(self, name: str, payload: bytes) -> str:
        request = urllib.request.Request(
            self.base + "/api/upload?code=123456", data=payload, method="POST",
            headers={"X-Filename": name, "Content-Length": str(len(payload))},
        )
        with urllib.request.urlopen(request, timeout=3) as response:
            return json.loads(response.read())["item"]["id"]

    def preview(self, identifier: str, extra: str = ""):
        with urllib.request.urlopen(f"{self.base}/api/preview/{identifier}?code=123456{extra}", timeout=3) as response:
            return response.read(), response.headers

    def test_svg_preview_is_confined_to_a_sandboxed_origin(self):
        payload = b'<svg xmlns="http://www.w3.org/2000/svg" onload="fetch(\'/api/status\')"></svg>'
        identifier = self.upload("invite.svg", payload)

        body, headers = self.preview(identifier)

        self.assertEqual(body, payload)
        self.assertEqual(headers.get_content_type(), "image/svg+xml")
        self.assertEqual(headers["Content-Security-Policy"], "sandbox")
        self.assertTrue(headers["Content-Disposition"].startswith("inline;"))

    def test_html_preview_downloads_instead_of_rendering(self):
        identifier = self.upload("page.html", b"<script>alert(1)</script>")

        _, headers = self.preview(identifier)

        self.assertEqual(headers.get_content_type(), "text/html")
        self.assertTrue(headers["Content-Disposition"].startswith("attachment;"))
        self.assertNotIn("Content-Security-Policy", headers)

    def test_office_pdf_preview_is_sandboxed(self):
        self.server.preview_service = FakePreviewService(Path(self.temp.name))
        identifier = self.upload("quarterly.pptx", b"fake-presentation")

        body, headers = self.preview(identifier, extra="&format=pdf")

        self.assertEqual(body, b"%PDF-local-link")
        self.assertEqual(headers.get_content_type(), "application/pdf")
        self.assertEqual(headers["Content-Security-Policy"], "sandbox")


class KeepAliveFramingTests(unittest.TestCase):
    """A client that over-sends must not corrupt the next pipelined request."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.server = create_server(Path(self.temp.name), "127.0.0.1", 0, "Test PC", "123456")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_port

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.temp.cleanup()

    @staticmethod
    def statuses(response: bytes) -> list[bytes]:
        # Response bodies carry no trailing CRLF, so status lines are searched
        # for anywhere in the stream instead of being split per line.
        return re.findall(rb"HTTP/1\.1 \d{3} [^\r\n]*", response)

    def _exchange(self, raw: bytes, timeout: float = 10.0) -> bytes:
        """Send one blob (so both requests are pipelined) and read to EOF."""
        connection = socket.create_connection(("127.0.0.1", self.port), timeout=timeout)
        connection.settimeout(timeout)
        try:
            connection.sendall(raw)
            connection.shutdown(socket.SHUT_WR)
            response = b""
            while True:
                data = connection.recv(65536)
                if not data:
                    break
                response += data
            return response
        finally:
            connection.close()

    def test_pipelined_request_survives_a_body_the_handler_rejected(self):
        # A bad X-SHA256 aborts the handler before it reads the body.  The
        # declared bytes are still drained, so the pipelined request is parsed.
        upload = (
            b"POST /api/upload?code=123456 HTTP/1.1\r\n"
            b"Host: test\r\nContent-Length: 4\r\n"
            b"X-Filename: bad.bin\r\nX-SHA256: nope\r\n\r\nabcd"
        )
        follow_up = b"GET /api/health HTTP/1.1\r\nHost: test\r\nConnection: close\r\n\r\n"

        response = self._exchange(upload + follow_up)

        self.assertEqual(self.statuses(response), [b"HTTP/1.1 400 Bad Request", b"HTTP/1.1 200 OK"], response[:400])
        self.assertIn(b'"service": "locallink"', response)

    def test_pipelined_request_survives_an_undeclared_json_tail(self):
        payload = json.dumps({"text": "hello", "sender": "Phone"}).encode()
        request = (
            b"POST /api/text?code=123456 HTTP/1.1\r\n"
            b"Host: test\r\nContent-Length: " + str(len(payload)).encode() + b"\r\n"
            b"Content-Type: application/json\r\n\r\n" + payload + b"TRAILINGGARBAGE"
        )
        follow_up = b"GET /api/health HTTP/1.1\r\nHost: test\r\nConnection: close\r\n\r\n"

        response = self._exchange(request + follow_up)

        self.assertIn(b"HTTP/1.1 201 Created", response)
        # The undeclared tail is not consumed, so the connection is torn down
        # after rejecting it: it must never be mistaken for a real request.
        self.assertNotIn(b'"service"', response)

    def test_oversized_body_never_yields_a_second_valid_response(self):
        upload = (
            b"POST /api/upload?code=123456 HTTP/1.1\r\n"
            b"Host: test\r\nContent-Length: 100\r\n"
            b"X-Filename: lying.bin\r\nX-Sender: probe\r\n\r\n" + b"A" * 5000
        )
        follow_up = b"GET /api/status?code=123456 HTTP/1.1\r\nHost: test\r\nConnection: close\r\n\r\n"

        response = self._exchange(upload + follow_up)

        # Before the fix the leftover body bytes were parsed as a request line
        # and answered with a 501 carrying the raw payload.  Either way the
        # misframed client must not reach an authenticated endpoint.
        self.assertIn(b"HTTP/1.1 201 Created", response)
        self.assertNotIn(b"HTTP/1.1 200 OK", response)
        self.assertNotIn(b'"pairing_code"', response)


if __name__ == "__main__":
    unittest.main()
