from __future__ import annotations

import socket
import sys
import threading
from urllib.parse import quote
from pathlib import Path

from PySide6.QtCore import QSettings, QUrl, Qt, Signal
from PySide6.QtGui import QAction, QDesktopServices, QIcon
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow, QMessageBox, QMenu, QSystemTrayIcon
from PySide6.QtWebEngineCore import QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView

from .core import TransferStore, choose_lan_ip, ensure_windows_firewall_access
from .server import create_server, run_server


def default_data_dir() -> Path:
    """Keep portable builds self-contained and source runs inside the project."""
    base = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path.cwd()
    return base / "LocalLinkData"


class MainWindow(QMainWindow):
    """Windows host. Constructing the window also starts the LocalLink service."""
    received = Signal(str, str)

    def __init__(self, host: str | None = None, port: int = 53317, code: str = "123456"):
        super().__init__()
        self.setWindowTitle("LocalLink · 本地传输主机")
        self.resize(1280, 840)
        self._really_quit = False
        self._tray_hint_shown = False
        self.settings = QSettings("LocalLink", "LocalLink")
        self.received.connect(self._show_received_notification)
        lan_ip = choose_lan_ip(host)
        saved_data_dir = str(self.settings.value("data_dir", "") or "").strip()
        data_dir = Path(saved_data_dir) if saved_data_dir else default_data_dir()
        try:
            self.server = create_server(
                data_dir, lan_ip, port, socket.gethostname() or "LocalLink-PC", code,
                bind_all=True, on_receive=self._received_from_server,
            )
        except (OSError, ValueError) as exc:
            raise RuntimeError(
                f"无法在 {lan_ip}:{port} 启动服务。请确认端口未被占用。\n\n{exc}"
            ) from exc

        self.server_thread = threading.Thread(
            target=run_server, args=(self.server,), name="locallink-host", daemon=True
        )
        self.server_thread.start()
        # python.exe may already be allowed while a newly built LocalLink.exe
        # is not. Request a narrow one-time firewall rule for this LAN port.
        self.server.firewall_state = ensure_windows_firewall_access(self.server.server_port)

        self.view = QWebEngineView(self)
        QWebEngineProfile.defaultProfile().downloadRequested.connect(self._accept_download)
        self.view.setUrl(QUrl(
            f"http://127.0.0.1:{self.server.server_port}/"
            f"?code={self.server.pairing_code}&client={quote('电脑端')}"
        ))
        self.setCentralWidget(self.view)
        self._create_tray()

    def _create_tray(self) -> None:
        self.tray = QSystemTrayIcon(QIcon(sys.executable), self)
        self.tray.setToolTip("LocalLink · 本地收件箱在线")
        menu = QMenu(self)
        show_action = QAction("打开 LocalLink", self)
        show_action.triggered.connect(self._restore_window)
        open_folder_action = QAction("打开接收目录", self)
        open_folder_action.triggered.connect(self._open_receive_folder)
        choose_folder_action = QAction("更改接收目录…", self)
        choose_folder_action.triggered.connect(self._choose_receive_folder)
        quit_action = QAction("退出并停止服务", self)
        quit_action.triggered.connect(self._quit_from_tray)
        menu.addAction(show_action)
        menu.addAction(open_folder_action)
        menu.addAction(choose_folder_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self._restore_window() if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self.tray.show()

    def _received_from_server(self, record) -> None:
        title = "收到文字" if record.kind == "text" else "收到文件"
        detail = f"{record.sender} · {record.text[:48]}" if record.kind == "text" else f"{record.sender} · {record.name}"
        self.received.emit(title, detail)

    def _show_received_notification(self, title: str, detail: str) -> None:
        self.tray.showMessage(title, detail, QSystemTrayIcon.MessageIcon.Information, 5000)

    def _restore_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _quit_from_tray(self) -> None:
        self._really_quit = True
        self.server.shutdown()
        self.tray.hide()
        QApplication.quit()

    def _open_receive_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.server.store.root)))

    def _choose_receive_folder(self) -> None:
        target = QFileDialog.getExistingDirectory(self, "选择 LocalLink 接收目录", str(self.server.store.root))
        if not target:
            return
        try:
            new_store = TransferStore(Path(target))
        except OSError as exc:
            QMessageBox.warning(self, "无法使用该目录", str(exc))
            return
        self.server.store = new_store
        self.settings.setValue("data_dir", str(new_store.root))
        self.view.reload()
        self.tray.showMessage("接收目录已更新", str(new_store.root), QSystemTrayIcon.MessageIcon.Information, 4500)

    def _accept_download(self, download):
        target, _ = QFileDialog.getSaveFileName(self, "保存文件", download.downloadFileName())
        if not target:
            download.cancel()
            return
        path = Path(target)
        download.setDownloadDirectory(str(path.parent))
        download.setDownloadFileName(path.name)
        download.accept()

    def closeEvent(self, event):
        if self._really_quit or not QSystemTrayIcon.isSystemTrayAvailable():
            self.server.shutdown()
            event.accept()
            return
        event.ignore()
        self.hide()
        if not self._tray_hint_shown:
            self._tray_hint_shown = True
            self.tray.showMessage("LocalLink 仍在运行", "本机收件箱已缩小到系统托盘，仍可继续接收内容。", QSystemTrayIcon.MessageIcon.Information, 4500)


def main() -> int:
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    app.setApplicationName("LocalLink")
    app.setWindowIcon(QIcon(sys.executable))
    try:
        window = MainWindow()
    except RuntimeError as exc:
        QMessageBox.critical(None, "LocalLink 启动失败", str(exc))
        return 1
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
