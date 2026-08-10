from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import secrets
import socket
import subprocess
import threading
import time
import uuid
import ctypes
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import BinaryIO, Iterable

from .capabilities import resolve_capabilities


MAX_TEXT_BYTES = 256 * 1024
CHUNK_SIZE = 1024 * 1024


def ensure_windows_firewall_access(port: int) -> str:
    """Allow LAN clients to reach LocalLink's TCP port.

    The rule is restricted to the local subnet.  When the process is not
    elevated Windows shows a normal UAC prompt for the one-time rule setup.
    """
    if os.name != "nt":
        return "not_required"
    rule_name = f"LocalLink LAN TCP {port}"
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        probe = subprocess.run(
            ["netsh", "advfirewall", "firewall", "show", "rule", f"name={rule_name}"],
            capture_output=True,
            timeout=8,
            creationflags=flags,
        )
        if probe.returncode == 0:
            return "configured"
        arguments = (
            "advfirewall firewall add rule "
            f'name="{rule_name}" dir=in action=allow protocol=TCP localport={port} '
            "remoteip=localsubnet profile=any enable=yes"
        )
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", "netsh.exe", arguments, None, 0
        )
        return "approval_requested" if result > 32 else "blocked"
    except (OSError, subprocess.SubprocessError):
        return "blocked"


def safe_filename(name: str) -> str:
    """Return a portable filename without allowing path traversal."""
    name = Path(name.replace("\\", "/")).name.strip().strip(".")
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    return name[:240] or "unnamed-file"


def human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def is_private_ipv4(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
        return ip.version == 4 and ip.is_private and not ip.is_loopback and not ip.is_link_local
    except ValueError:
        return False


def _candidate_ipv4s() -> list[str]:
    candidates: list[str] = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = info[4][0]
            if is_private_ipv4(address) and address not in candidates:
                candidates.append(address)
    except OSError:
        pass

    # A UDP connect chooses a route but does not transmit data.
    for target in (("192.0.2.1", 9), ("8.8.8.8", 53)):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect(target)
                address = sock.getsockname()[0]
                if is_private_ipv4(address) and address not in candidates:
                    candidates.insert(0, address)
        except OSError:
            pass
    return candidates


def candidate_ipv4s() -> list[str]:
    """Return likely LAN IPv4 addresses, preferring Wi-Fi/Ethernet ranges."""
    values = _candidate_ipv4s()
    # Consumer LAN ranges are preferred over addresses commonly used by VPNs.
    return sorted(values, key=lambda ip: (ip.startswith("10."), ip.startswith("172."), ip))


def choose_lan_ip(requested: str | None = None) -> str:
    if requested:
        # Loopback is accepted for local testing; remote devices cannot use it.
        if requested in ("0.0.0.0", "127.0.0.1") or is_private_ipv4(requested):
            return requested
        raise ValueError(f"不是可用的局域网 IPv4 地址: {requested}")
    candidates = candidate_ipv4s()
    return candidates[0] if candidates else "127.0.0.1"


@dataclass(slots=True)
class TransferRecord:
    id: str
    kind: str
    name: str
    size: int
    sha256: str
    created_at: float
    sender: str
    text: str = ""
    receiver: str = "LocalLink 主机"


class TransferStore:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.files = self.root / "files"
        self.index_path = self.root / "history.json"
        self.files.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._records: list[TransferRecord] = []
        self._load()

    def _load(self) -> None:
        if not self.index_path.exists():
            return
        try:
            raw = json.loads(self.index_path.read_text(encoding="utf-8"))
            records = []
            for item in raw:
                if not isinstance(item, dict):
                    continue
                item.setdefault("receiver", "LocalLink 主机")
                records.append(TransferRecord(**item))
            self._records = records
        except (OSError, ValueError, TypeError):
            self._records = []

    def _persist(self) -> None:
        temp = self.index_path.with_suffix(".tmp")
        temp.write_text(
            json.dumps([asdict(item) for item in self._records], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temp, self.index_path)

    def list(self, platform: str = "windows", converter_available: bool = False) -> list[dict]:
        with self._lock:
            result = []
            for record in reversed(self._records):
                item = asdict(record)
                item["size_human"] = human_size(record.size)
                item["available"] = record.kind == "text" or self.path_for(record).is_file()
                if record.kind == "text":
                    item.update({
                        "mime_type": "text/plain; charset=utf-8",
                        "category": "text",
                        "actions": ["preview_inline"],
                        "installable": False,
                    })
                else:
                    item.update(resolve_capabilities(record.name, platform, converter_available))
                result.append(item)
            return result

    def stats(self) -> dict:
        with self._lock:
            file_items = [item for item in self._records if item.kind == "file" and self.path_for(item).is_file()]
            return {
                "items": len(self._records),
                "files": len(file_items),
                "bytes": sum(item.size for item in file_items),
                "bytes_human": human_size(sum(item.size for item in file_items)),
            }

    def add_text(self, text: str, sender: str, receiver: str = "LocalLink 主机") -> TransferRecord:
        if not text.strip():
            raise ValueError("不能发送空文本")
        encoded = text.encode("utf-8")
        if len(encoded) > MAX_TEXT_BYTES:
            raise ValueError("文本不能超过 256 KB")
        record = TransferRecord(
            id=uuid.uuid4().hex,
            kind="text",
            name="文本消息",
            size=len(encoded),
            sha256=hashlib.sha256(encoded).hexdigest(),
            created_at=time.time(),
            sender=sender[:80],
            text=text,
            receiver=receiver[:80],
        )
        with self._lock:
            self._records.append(record)
            self._persist()
        return record

    def save_file(
        self,
        source: BinaryIO,
        filename: str,
        size: int,
        sender: str,
        expected_sha256: str = "",
        receiver: str = "LocalLink 主机",
    ) -> TransferRecord:
        if size < 0:
            raise ValueError("文件大小无效")
        identifier = uuid.uuid4().hex
        clean_name = safe_filename(filename)
        destination = self.files / f"{identifier}--{clean_name}"
        temp = destination.with_suffix(destination.suffix + ".part")
        digest = hashlib.sha256()
        written = 0
        try:
            with temp.open("wb") as target:
                while written < size:
                    chunk = source.read(min(CHUNK_SIZE, size - written))
                    if not chunk:
                        break
                    target.write(chunk)
                    digest.update(chunk)
                    written += len(chunk)
            if written != size:
                raise ValueError(f"文件不完整：预期 {size} 字节，收到 {written} 字节")
            actual = digest.hexdigest()
            if expected_sha256 and not secrets.compare_digest(actual, expected_sha256.lower()):
                raise ValueError("SHA-256 校验失败")
            os.replace(temp, destination)
        except Exception:
            temp.unlink(missing_ok=True)
            raise

        record = TransferRecord(
            id=identifier,
            kind="file",
            name=clean_name,
            size=size,
            sha256=actual,
            created_at=time.time(),
            sender=sender[:80],
            receiver=receiver[:80],
        )
        with self._lock:
            self._records.append(record)
            self._persist()
        return record

    def get(self, identifier: str) -> TransferRecord | None:
        with self._lock:
            return next((item for item in self._records if item.id == identifier), None)

    def path_for(self, record: TransferRecord) -> Path:
        return self.files / f"{record.id}--{record.name}"

    def delete(self, identifier: str) -> bool:
        with self._lock:
            record = self.get(identifier)
            if record is None:
                return False
            if record.kind == "file":
                self.path_for(record).unlink(missing_ok=True)
            self._records = [item for item in self._records if item.id != identifier]
            self._persist()
            return True

    def clear(self) -> int:
        with self._lock:
            count = len(self._records)
            for record in self._records:
                if record.kind == "file":
                    self.path_for(record).unlink(missing_ok=True)
            self._records = []
            self._persist()
            return count


class PeerRegistry:
    def __init__(self, ttl: float = 12.0):
        self.ttl = ttl
        self._peers: dict[str, dict] = {}
        self._lock = threading.Lock()

    def update(self, payload: dict, source_ip: str) -> None:
        peer_id = str(payload.get("id", ""))
        if not peer_id:
            return
        with self._lock:
            self._peers[peer_id] = {
                "id": peer_id,
                "name": str(payload.get("name", "LocalLink"))[:80],
                "ip": source_ip,
                "port": int(payload.get("port", 0)),
                "version": str(payload.get("version", "1")),
                "last_seen": time.time(),
            }

    def list(self, own_id: str) -> list[dict]:
        now = time.time()
        with self._lock:
            self._peers = {key: value for key, value in self._peers.items() if now - value["last_seen"] <= self.ttl}
            return [value.copy() for key, value in self._peers.items() if key != own_id]


class DiscoveryService:
    GROUP = "239.255.42.99"
    PORT = 53318

    def __init__(self, device_id: str, name: str, ip: str, http_port: int, registry: PeerRegistry):
        self.device_id = device_id
        self.name = name
        self.ip = ip
        self.http_port = http_port
        self.registry = registry
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        for target, name in ((self._announce, "announce"), (self._listen, "listen")):
            thread = threading.Thread(target=target, name=f"locallink-{name}", daemon=True)
            thread.start()
            self._threads.append(thread)

    def stop(self) -> None:
        self._stop.set()

    def _payload(self) -> bytes:
        return json.dumps({
            "service": "locallink",
            "version": "1",
            "id": self.device_id,
            "name": self.name,
            "port": self.http_port,
        }).encode("utf-8")

    def _announce(self) -> None:
        payload = self._payload()
        while not self._stop.is_set():
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as sock:
                    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
                    if is_private_ipv4(self.ip):
                        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(self.ip))
                    sock.sendto(payload, (self.GROUP, self.PORT))
            except OSError:
                pass
            self._stop.wait(3)

    def _listen(self) -> None:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(("", self.PORT))
                membership = socket.inet_aton(self.GROUP) + socket.inet_aton(self.ip if is_private_ipv4(self.ip) else "0.0.0.0")
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership)
                sock.settimeout(1)
                while not self._stop.is_set():
                    try:
                        data, address = sock.recvfrom(4096)
                        payload = json.loads(data.decode("utf-8"))
                        if payload.get("service") == "locallink":
                            self.registry.update(payload, address[0])
                    except (socket.timeout, ValueError, UnicodeDecodeError):
                        continue
        except OSError:
            return


def windows_firewall_hint(port: int) -> str:
    if os.name != "nt":
        return "请确认系统防火墙允许局域网访问此端口。"
    return (
        "首次运行若出现 Windows 防火墙提示，请勾选“专用网络”。"
        f" 如未出现，可允许 Python 监听 TCP {port} 和 UDP {DiscoveryService.PORT}。"
    )


def network_diagnostics(ip: str) -> dict:
    """Best-effort LAN/VPN diagnosis without administrator privileges."""
    result = {
        "vpn_detected": False,
        "gateway": "",
        "lan_state": "unknown",
        "message": "无法自动确认局域网连通性",
    }
    if os.name != "nt" or not is_private_ipv4(ip):
        return result
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        ipconfig = subprocess.run(
            ["ipconfig", "/all"], capture_output=True, text=True, errors="replace",
            timeout=3, creationflags=flags,
        ).stdout
        result["vpn_detected"] = bool(
            re.search(r"vpn|wireguard|openvpn|tailscale|\btun\b|\btap\b", ipconfig, re.I)
        )
        routes = subprocess.run(
            ["route", "print", "-4"], capture_output=True, text=True, errors="replace",
            timeout=3, creationflags=flags,
        ).stdout
        for line in routes.splitlines():
            fields = line.split()
            if len(fields) >= 5 and fields[0] == "0.0.0.0" and fields[1] == "0.0.0.0" and fields[3] == ip:
                result["gateway"] = fields[2]
                break
        if not result["gateway"]:
            return result
        probe = subprocess.run(
            ["ping", "-n", "1", "-w", "600", result["gateway"]],
            capture_output=True, text=True, errors="replace", timeout=3, creationflags=flags,
        )
        output = f"{probe.stdout}\n{probe.stderr}"
        if probe.returncode == 0:
            result["lan_state"] = "ok"
            result["message"] = "可访问局域网网关"
        elif re.search(r"general failure|一般故障|常规故障", output, re.I):
            result["lan_state"] = "blocked"
            result["message"] = "本机网络策略或 VPN 正在阻止局域网"
        else:
            result["message"] = "网关未响应；也可能是路由器禁用了 ICMP"
    except (OSError, subprocess.SubprocessError):
        pass
    return result
