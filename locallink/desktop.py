from __future__ import annotations

import socket
import sys
import threading
import json
from urllib.parse import quote
from pathlib import Path

from PySide6.QtCore import QObject, QSettings, QUrl, Qt, Signal, Slot
from PySide6.QtGui import QAction, QDesktopServices, QIcon
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWidgets import QApplication, QCheckBox, QFileDialog, QMainWindow, QMessageBox, QMenu, QSystemTrayIcon, QStyle
from PySide6.QtWebEngineCore import QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView

from .core import TransferStore, choose_lan_ip, ensure_windows_firewall_access
from .native_bridge import NativeFileBridge
from .server import create_server, run_server


def default_data_dir() -> Path:
    """Keep portable builds self-contained and source runs inside the project."""
    base = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path.cwd()
    return base / "LocalLinkData"


def bundled_icon() -> QIcon:
    """Load the same icon for the window and tray in source and frozen builds."""
    roots = [Path(getattr(sys, "_MEIPASS", "")), Path(__file__).resolve().parents[1]]
    for root in roots:
        if root:
            candidate = root / "assets" / "locallink.ico"
            if candidate.exists():
                icon = QIcon(str(candidate))
                if not icon.isNull():
                    return icon
    icon = QIcon(sys.executable)
    return icon if not icon.isNull() else QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)


class DesktopWebBridge(QObject):
    def __init__(self, bridge: NativeFileBridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge

    @Slot(str, result=str)
    def openRecord(self, record_id: str) -> str:
        return json.dumps(self.bridge.open_record(record_id))

    @Slot(str, result=str)
    def revealRecord(self, record_id: str) -> str:
        return json.dumps(self.bridge.reveal_record(record_id))

    @Slot(str, result=bool)
    def copyText(self, value: str) -> bool:
        if not value:
            return False
        try:
            QApplication.clipboard().setText(value)
            return True
        except RuntimeError:
            return False


class MainWindow(QMainWindow):
    """Windows host. Constructing the window also starts the LocalLink service."""
    received = Signal(str, str)

    def __init__(self, host: str | None = None, port: int = 53317, code: str = "123456"):
        super().__init__()
        self.setWindowTitle("LocalLink 2.4.4 · 本地传输主机")
        self.resize(1280, 840)
        self._really_quit = False
        self._tray_hint_shown = False
        self._service_stopped = False
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
        self.file_bridge = NativeFileBridge(self.server.store)
        self.web_bridge = DesktopWebBridge(self.file_bridge, self)
        self.channel = QWebChannel(self.view.page())
        self.channel.registerObject("localLinkNative", self.web_bridge)
        self.view.page().setWebChannel(self.channel)
        self.view.loadFinished.connect(self._install_web_bridge)
        QWebEngineProfile.defaultProfile().downloadRequested.connect(self._accept_download)
        self.view.setUrl(QUrl(
            f"http://127.0.0.1:{self.server.server_port}/"
            f"?code={self.server.pairing_code}&client={quote('电脑端')}"
        ))
        self.setCentralWidget(self.view)
        self._create_tray()

    def _install_web_bridge(self, ok: bool) -> None:
        if not ok:
            return
        script = """
        (() => {
          const attach = () => new QWebChannel(qt.webChannelTransport, channel => {
            const native = channel.objects.localLinkNative;
            window.LocalLinkNative = {
              openRecord: (id) => native.openRecord(String(id), result => {
                try { const value = JSON.parse(result); if (!value.ok) alert('无法打开文件：' + value.error); } catch (_) {}
              }),
              revealRecord: (id) => native.revealRecord(String(id)),
              copyText: (value) => new Promise(resolve => native.copyText(String(value), result => resolve(Boolean(result))))
            };
          });
          if (window.QWebChannel) { attach(); return; }
          const source = document.createElement('script');
          source.src = 'qrc:///qtwebchannel/qwebchannel.js';
          source.onload = attach;
          document.head.appendChild(source);
        })();
        """
        self.view.page().runJavaScript(script)

    def _create_tray(self) -> None:
        self.tray = QSystemTrayIcon(bundled_icon(), self)
        self.tray.setVisible(True)
        self.tray.setToolTip("LocalLink · 本地收件箱在线")
        menu = QMenu(self)
        show_action = QAction("打开 LocalLink", self)
        show_action.triggered.connect(self._restore_window)
        open_folder_action = QAction("打开接收目录", self)
        open_folder_action.triggered.connect(self._open_receive_folder)
        choose_folder_action = QAction("更改接收目录…", self)
        choose_folder_action.triggered.connect(self._choose_receive_folder)
        ask_on_close_action = QAction("下次关闭时询问", self)
        ask_on_close_action.triggered.connect(self._reset_close_choice)
        quit_action = QAction("退出并停止服务", self)
        quit_action.triggered.connect(self._quit_from_tray)
        menu.addAction(show_action)
        menu.addAction(open_folder_action)
        menu.addAction(choose_folder_action)
        menu.addAction(ask_on_close_action)
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
        # System notifications may be disabled. When the window is visible, also
        # surface the receive event inside the workspace and refresh its records.
        if self.isVisible():
            payload = json.dumps([title, detail], ensure_ascii=False)
            self.view.page().runJavaScript(
                f"window.LocalLinkApp?.notifyReceived?.(...{payload});"
            )

    def _restore_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _quit_from_tray(self) -> None:
        self._really_quit = True
        self._stop_service()
        self.tray.hide()
        QApplication.quit()

    def _stop_service(self) -> None:
        if self._service_stopped:
            return
        self._service_stopped = True
        self.server.shutdown()
        self.server.server_close()

    def _reset_close_choice(self) -> None:
        self.settings.remove("close_behavior")
        self.tray.showMessage(
            "关闭行为已重置",
            "下次点击关闭按钮时将询问是否保留后台服务。",
            QSystemTrayIcon.MessageIcon.Information,
            3500,
        )

    def _hide_to_tray(self, event) -> None:
        event.ignore()
        self.hide()
        if not self._tray_hint_shown:
            self._tray_hint_shown = True
            self.tray.showMessage(
                "LocalLink 正在后台运行",
                "本机收件箱仍在线，可继续接收内容；可从系统托盘打开或退出。",
                QSystemTrayIcon.MessageIcon.Information,
                4500,
            )

    def _ask_close_behavior(self, event) -> None:
        dialog = QMessageBox(self)
        dialog.setWindowTitle("关闭 LocalLink")
        dialog.setIcon(QMessageBox.Icon.Question)
        dialog.setText("要停止本机收件箱吗？")
        dialog.setInformativeText("选择“后台运行”后，其他已连接设备仍可向这台电脑发送内容。你可随时从系统托盘退出。")
        background = dialog.addButton("后台运行", QMessageBox.ButtonRole.AcceptRole)
        quit_button = dialog.addButton("退出并停止服务", QMessageBox.ButtonRole.DestructiveRole)
        dialog.addButton(QMessageBox.StandardButton.Cancel)
        remember = QCheckBox("记住我的选择", dialog)
        dialog.setCheckBox(remember)
        dialog.exec()
        selected = dialog.clickedButton()
        if selected is background:
            if remember.isChecked():
                self.settings.setValue("close_behavior", "hide")
            self._hide_to_tray(event)
            return
        if selected is quit_button:
            if remember.isChecked():
                self.settings.setValue("close_behavior", "quit")
            self._really_quit = True
            self._stop_service()
            self.tray.hide()
            event.accept()
            return
        event.ignore()

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
        self.file_bridge.store = new_store
        self.server.preview_service.cache_dir = (new_store.root / "preview-cache").resolve()
        self.server.preview_service.cache_dir.mkdir(parents=True, exist_ok=True)
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
        if self._really_quit:
            self._stop_service()
            event.accept()
            return
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self._stop_service()
            event.accept()
            QApplication.quit()
            return
        behavior = str(self.settings.value("close_behavior", "ask") or "ask")
        if behavior == "hide":
            self._hide_to_tray(event)
        elif behavior == "quit":
            self._really_quit = True
            self._stop_service()
            self.tray.hide()
            event.accept()
        else:
            self._ask_close_behavior(event)


def main() -> int:
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    app.setApplicationName("LocalLink")
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(bundled_icon())
    try:
        window = MainWindow()
    except RuntimeError as exc:
        QMessageBox.critical(None, "LocalLink 启动失败", str(exc))
        return 1
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
