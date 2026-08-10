from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
from pathlib import Path

from .core import candidate_ipv4s, windows_firewall_hint
from .server import create_server, run_server


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="LocalLink：无需互联网的局域网文件与文本传输工具")
    result.add_argument("--interface", help="绑定的局域网 IPv4；建议 VPN 开启时显式指定")
    result.add_argument("--port", type=int, default=53317, help="HTTP 端口（默认 53317）")
    result.add_argument("--name", default=socket.gethostname(), help="设备显示名称")
    result.add_argument("--data-dir", type=Path, default=Path.cwd() / "LocalLinkData", help="接收文件目录")
    result.add_argument("--code", help="固定 6 位配对码；默认每次随机生成")
    result.add_argument("--usb", action="store_true", help="通过 Android USB/ADB 连接，绕开 VPN 的 LAN 限制")
    result.add_argument("--list-interfaces", action="store_true", help="列出检测到的局域网 IPv4 后退出")
    return result


def find_adb() -> str | None:
    candidates = [shutil.which("adb")]
    for variable in ("ANDROID_SDK_ROOT", "ANDROID_HOME"):
        if os.environ.get(variable):
            candidates.append(str(Path(os.environ[variable]) / "platform-tools" / "adb.exe"))
    if os.environ.get("LOCALAPPDATA"):
        candidates.append(str(Path(os.environ["LOCALAPPDATA"]) / "Android" / "Sdk" / "platform-tools" / "adb.exe"))
    return next((candidate for candidate in candidates if candidate and Path(candidate).is_file()), None)


def prepare_android_usb(port: int) -> list[str]:
    adb = find_adb()
    if not adb:
        raise SystemExit(
            "USB 模式需要 Android SDK Platform-Tools（adb）。\n"
            "请从 https://developer.android.com/tools/releases/platform-tools 下载并将 platform-tools 加入 PATH。"
        )
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    probe = subprocess.run([adb, "devices"], capture_output=True, text=True, timeout=10, creationflags=flags)
    devices = []
    unauthorized = []
    for line in probe.stdout.splitlines()[1:]:
        fields = line.split()
        if len(fields) >= 2 and fields[1] == "device":
            devices.append(fields[0])
        elif len(fields) >= 2 and fields[1] == "unauthorized":
            unauthorized.append(fields[0])
    if unauthorized:
        raise SystemExit("手机尚未授权 USB 调试；请解锁手机并确认“允许此电脑进行 USB 调试”。")
    if not devices:
        raise SystemExit("未发现 Android 设备；请连接 USB、启用开发者选项和 USB 调试。")
    physical_devices = [serial for serial in devices if not serial.startswith("emulator-")]
    if not physical_devices:
        raise SystemExit("只检测到 Android 模拟器，未检测到 USB 真机；请重新连接手机并确认 USB 调试授权。")
    if len(physical_devices) == 1:
        selected = physical_devices[0]
    else:
        raise SystemExit("检测到多台真机；请断开其他 Android USB 设备后重试。")
    command = [adb, "-s", selected]
    reverse = subprocess.run(
        command + ["reverse", f"tcp:{port}", f"tcp:{port}"],
        capture_output=True, text=True, timeout=10, creationflags=flags,
    )
    if reverse.returncode != 0:
        raise SystemExit(f"ADB 端口转发失败：{reverse.stderr.strip() or reverse.stdout.strip()}")
    return command


def main() -> int:
    args = parser().parse_args()
    if args.list_interfaces:
        values = candidate_ipv4s()
        print("\n".join(values) if values else "未检测到局域网 IPv4")
        return 0
    if args.code and (len(args.code) != 6 or not args.code.isdigit()):
        raise SystemExit("--code 必须是 6 位数字")
    if args.usb and args.interface:
        raise SystemExit("--usb 与 --interface 不能同时使用")
    if args.usb:
        args.interface = "127.0.0.1"
    try:
        server = create_server(args.data_dir, args.interface, args.port, args.name, args.code)
    except (ValueError, OSError) as exc:
        raise SystemExit(f"启动失败：{exc}") from exc
    adb_command = prepare_android_usb(server.server_port) if args.usb else None
    url = f"http://{server.advertised_ip}:{server.server_port}/?code={server.pairing_code}"
    phone_url = f"http://127.0.0.1:{server.server_port}/?code={server.pairing_code}"
    print("\nLocalLink 已启动")
    print(f"设备：{server.device_name}")
    print(f"地址：{phone_url if args.usb else url}")
    if args.usb:
        print("链路：Android USB（不经过 Wi-Fi/VPN）")
    print(f"配对码：{server.pairing_code}")
    print(f"接收目录：{server.store.root}")
    print(windows_firewall_hint(server.server_port))
    print("按 Ctrl+C 停止。\n")
    try:
        run_server(server)
    except KeyboardInterrupt:
        pass
    finally:
        if adb_command:
            subprocess.run(
                adb_command + ["reverse", "--remove", f"tcp:{server.server_port}"],
                capture_output=True, timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
