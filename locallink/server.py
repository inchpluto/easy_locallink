from __future__ import annotations

import json
import ipaddress
import mimetypes
import os
import re
import secrets
import socket
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

from .core import DiscoveryService, PeerRegistry, TransferStore, choose_lan_ip, network_diagnostics
from .preview import LibreOfficeConverter, OfficePreviewService, PreviewError, find_libreoffice


STATIC_ROOT = Path(__file__).parent / "static"


def load_or_create_device_id(root: Path) -> str:
    """Return a stable opaque host ID stored alongside LocalLink data."""
    identity_file = root.resolve() / ".device-id"
    try:
        saved = identity_file.read_text(encoding="ascii").strip().lower()
        if re.fullmatch(r"[0-9a-f]{16,64}", saved):
            return saved
    except OSError:
        pass
    generated = secrets.token_hex(8)
    try:
        with identity_file.open("x", encoding="ascii") as target:
            target.write(generated)
    except FileExistsError:
        try:
            saved = identity_file.read_text(encoding="ascii").strip().lower()
            if re.fullmatch(r"[0-9a-f]{16,64}", saved):
                return saved
        except OSError:
            pass
    except OSError:
        pass
    return generated


class LocalLinkServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, store: TransferStore, device_name: str, advertised_ip: str, pairing_code: str, on_receive=None):
        super().__init__(address, LocalLinkHandler)
        self.store = store
        self.device_name = device_name
        self.advertised_ip = advertised_ip
        self.pairing_code = pairing_code
        self.device_id = load_or_create_device_id(store.root)
        self.peers = PeerRegistry()
        self.firewall_state = "not_checked"
        self._diagnostic_cache = ({}, 0.0)
        self._scan_lock = threading.Lock()
        self.on_receive = on_receive
        executable = find_libreoffice()
        converter = LibreOfficeConverter(executable) if executable else None
        self.preview_service = OfficePreviewService(store.root / "preview-cache", converter)

    def notify_received(self, record) -> None:
        if self.on_receive:
            try:
                self.on_receive(record)
            except Exception:
                pass

    def diagnostics(self) -> dict:
        value, checked_at = self._diagnostic_cache
        if time.monotonic() - checked_at > 8:
            value = network_diagnostics(self.advertised_ip)
            self._diagnostic_cache = (value, time.monotonic())
        return value

    def scan_subnet_async(self) -> bool:
        """Probe the advertised /24 for LocalLink hosts without blocking HTTP."""
        if not self._scan_lock.acquire(blocking=False):
            return False

        def worker() -> None:
            try:
                network = ipaddress.ip_network(f"{self.advertised_ip}/24", strict=False)

                def probe(address) -> None:
                    ip = str(address)
                    if ip == self.advertised_ip:
                        return
                    try:
                        with urllib.request.urlopen(
                            f"http://{ip}:{self.server_port}/api/health", timeout=0.35
                        ) as response:
                            payload = json.loads(response.read(8192))
                        if payload.get("service") == "locallink":
                            self.peers.update(payload, ip)
                    except (OSError, ValueError, json.JSONDecodeError):
                        pass

                with ThreadPoolExecutor(max_workers=32, thread_name_prefix="locallink-scan") as pool:
                    list(pool.map(probe, network.hosts()))
            finally:
                self._scan_lock.release()

        threading.Thread(target=worker, name="locallink-subnet-scan", daemon=True).start()
        return True


class LocalLinkHandler(BaseHTTPRequestHandler):
    server: LocalLinkServer
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {self.client_address[0]} {fmt % args}")

    def _headers(self, status: int, content_type: str, length: int, extra: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if extra:
            for key, value in extra.items():
                self.send_header(key, value)
        self.end_headers()

    def _json(self, payload, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._headers(status, "application/json; charset=utf-8", len(body))
        self.wfile.write(body)

    def _error(self, status: int, message: str) -> None:
        self._json({"ok": False, "error": message}, status)

    def _query(self) -> dict[str, list[str]]:
        return parse_qs(urlparse(self.path).query)

    def _authorized(self) -> bool:
        query_code = self._query().get("code", [""])[0]
        header_code = self.headers.get("X-LocalLink-Code", "")
        return secrets.compare_digest(query_code or header_code, self.server.pairing_code)

    def _require_auth(self) -> bool:
        if self._authorized():
            return True
        self._error(HTTPStatus.UNAUTHORIZED, "配对码错误或已失效")
        return False

    def _read_json(self, max_bytes: int = 300_000):
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValueError("Content-Length 无效")
        if size <= 0 or size > max_bytes:
            raise ValueError("请求内容大小无效")
        return json.loads(self.rfile.read(size).decode("utf-8"))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/status":
            if not self._require_auth():
                return
            self._json({
                "ok": True,
                "device": self.server.device_name,
                "ip": self.server.advertised_ip,
                "port": self.server.server_port,
                "pairing_code": self.server.pairing_code,
                "device_id": self.server.device_id,
                "share_url": f"http://{self.server.advertised_ip}:{self.server.server_port}/?code={self.server.pairing_code}",
                "network": {**self.server.diagnostics(), "firewall": self.server.firewall_state},
                "peers": self.server.peers.list(self.server.device_id),
                "storage": self.server.store.stats(),
                "history": self.server.store.list(
                    platform="windows",
                    converter_available=self.server.preview_service.available,
                ),
            })
            return
        if path == "/api/health":
            self._json({
                "ok": True,
                "service": "locallink",
                "version": "2",
                "id": self.server.device_id,
                "name": self.server.device_name,
                "port": self.server.server_port,
            })
            return
        if path.startswith("/api/download/"):
            if not self._require_auth():
                return
            self._download(path.rsplit("/", 1)[-1])
            return
        if path.startswith("/api/preview/"):
            if not self._require_auth():
                return
            self._preview(path.rsplit("/", 1)[-1])
            return
        if path in ("/", "/index.html"):
            self._static("index.html")
            return
        if path.startswith("/static/"):
            self._static(path.removeprefix("/static/"))
            return
        self._error(HTTPStatus.NOT_FOUND, "未找到")

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if not self._require_auth():
            return
        try:
            if path == "/api/text":
                payload = self._read_json()
                record = self.server.store.add_text(
                    str(payload.get("text", "")),
                    str(payload.get("sender", "浏览器")),
                    self.server.device_name,
                )
                self.server.notify_received(record)
                self._json({"ok": True, "item": asdict(record)}, HTTPStatus.CREATED)
                return
            if path == "/api/upload":
                size = int(self.headers.get("Content-Length", "-1"))
                filename = unquote(self.headers.get("X-Filename", "unnamed-file"))
                sender = unquote(self.headers.get("X-Sender", "浏览器"))
                sha256 = self.headers.get("X-SHA256", "")
                if sha256 and (len(sha256) != 64 or any(c not in "0123456789abcdefABCDEF" for c in sha256)):
                    raise ValueError("SHA-256 格式无效")
                record = self.server.store.save_file(
                    self.rfile, filename, size, sender, sha256, self.server.device_name
                )
                self.server.notify_received(record)
                self._json({"ok": True, "item": asdict(record)}, HTTPStatus.CREATED)
                return
            if path == "/api/scan":
                started = self.server.scan_subnet_async()
                self._json({"ok": True, "started": started}, HTTPStatus.ACCEPTED)
                return
            self._error(HTTPStatus.NOT_FOUND, "未找到")
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            self._error(HTTPStatus.BAD_REQUEST, str(exc))
        except OSError as exc:
            self._error(HTTPStatus.INTERNAL_SERVER_ERROR, f"存储失败: {exc}")

    def do_DELETE(self) -> None:
        if not self._require_auth():
            return
        path = urlparse(self.path).path
        if path == "/api/items":
            identifiers = [item["id"] for item in self.server.store.list()]
            deleted = self.server.store.clear()
            for identifier in identifiers:
                self.server.preview_service.remove_record(identifier)
            self._json({"ok": True, "deleted": deleted})
            return
        if path.startswith("/api/items/"):
            identifier = path.rsplit("/", 1)[-1]
            deleted = self.server.store.delete(identifier)
            if deleted:
                self.server.preview_service.remove_record(identifier)
            self._json({"ok": deleted}, HTTPStatus.OK if deleted else HTTPStatus.NOT_FOUND)
            return
        self._error(HTTPStatus.NOT_FOUND, "未找到")

    def _static(self, name: str) -> None:
        candidate = (STATIC_ROOT / name).resolve()
        if STATIC_ROOT.resolve() not in candidate.parents and candidate != STATIC_ROOT.resolve():
            self._error(HTTPStatus.FORBIDDEN, "禁止访问")
            return
        if not candidate.is_file():
            self._error(HTTPStatus.NOT_FOUND, "未找到")
            return
        body = candidate.read_bytes()
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        if candidate.suffix in (".js", ".css", ".html"):
            content_type += "; charset=utf-8"
        self._headers(HTTPStatus.OK, content_type, len(body))
        self.wfile.write(body)

    def _download(self, identifier: str, inline: bool = False) -> None:
        record = self.server.store.get(identifier)
        if record is None or record.kind != "file":
            self._error(HTTPStatus.NOT_FOUND, "文件不存在")
            return
        path = self.server.store.path_for(record)
        if not path.is_file():
            self._error(HTTPStatus.GONE, "文件已从磁盘移除")
            return
        total = path.stat().st_size
        start, end = 0, total - 1
        status = HTTPStatus.OK
        range_header = self.headers.get("Range", "")
        if range_header.startswith("bytes="):
            try:
                left, right = range_header[6:].split("-", 1)
                start = int(left) if left else 0
                end = int(right) if right else total - 1
                if start < 0 or end < start or end >= total:
                    raise ValueError
                status = HTTPStatus.PARTIAL_CONTENT
            except ValueError:
                self._headers(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE, "text/plain", 0, {"Content-Range": f"bytes */{total}"})
                return
        length = end - start + 1
        extra = {
            "Accept-Ranges": "bytes",
            "Content-Disposition": f"{'inline' if inline else 'attachment'}; filename*=UTF-8''{quote(record.name)}",
            "ETag": f'"{record.sha256}"',
        }
        if status == HTTPStatus.PARTIAL_CONTENT:
            extra["Content-Range"] = f"bytes {start}-{end}/{total}"
        self._headers(status, mimetypes.guess_type(record.name)[0] or "application/octet-stream", length, extra)
        with path.open("rb") as source:
            source.seek(start)
            remaining = length
            while remaining:
                chunk = source.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def _preview(self, identifier: str) -> None:
        record = self.server.store.get(identifier)
        if record is None or record.kind != "file":
            self._error(HTTPStatus.NOT_FOUND, "文件不存在")
            return
        source = self.server.store.path_for(record)
        if not source.is_file():
            self._error(HTTPStatus.GONE, "文件已从磁盘移除")
            return
        requested_format = self._query().get("format", [""])[0].lower()
        if requested_format != "pdf":
            self._download(identifier, inline=True)
            return
        try:
            preview = self.server.preview_service.get_or_create(record, source)
        except PreviewError as exc:
            status = {
                "PREVIEW_UNSUPPORTED": HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                "PREVIEW_TOO_LARGE": HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            }.get(exc.code, HTTPStatus.INTERNAL_SERVER_ERROR)
            self._json({"ok": False, "error": exc.code, "detail": exc.detail}, status)
            return
        body = preview.read_bytes()
        preview_name = f"{Path(record.name).stem}.pdf"
        self._headers(
            HTTPStatus.OK,
            "application/pdf",
            len(body),
            {"Content-Disposition": f"inline; filename*=UTF-8''{quote(preview_name)}"},
        )
        self.wfile.write(body)


def create_server(
    data_dir: Path,
    host: str | None = None,
    port: int = 53317,
    name: str | None = None,
    pairing_code: str | None = None,
    bind_all: bool = False,
    on_receive=None,
) -> LocalLinkServer:
    lan_ip = choose_lan_ip(host)
    # Desktop hosts listen on every IPv4 interface so route changes caused by
    # VPN, Wi-Fi roaming or virtual adapters do not silently break the server.
    # The advertised address remains the selected physical LAN address.
    bind_ip = "0.0.0.0" if bind_all else lan_ip
    device_name = name or socket.gethostname() or "LocalLink"
    code = pairing_code or f"{secrets.randbelow(1_000_000):06d}"
    return LocalLinkServer((bind_ip, port), TransferStore(data_dir), device_name, lan_ip, code, on_receive)


def run_server(server: LocalLinkServer) -> None:
    discovery = DiscoveryService(
        server.device_id,
        server.device_name,
        server.advertised_ip,
        server.server_port,
        server.peers,
    )
    discovery.start()
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        discovery.stop()
        server.server_close()
