"""Frozen-app startup check: Qt, WebEngine and bundled UI, no LAN exposure."""
def run(report_path):
    import json
    import os
    from pathlib import Path
    import tempfile
    import threading
    import traceback

    report = Path(report_path)
    try:
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        from PySide6.QtCore import QTimer, QUrl, qVersion
        from PySide6.QtWidgets import QApplication
        from PySide6.QtWebEngineWidgets import QWebEngineView
        from .server import create_server
        app = QApplication([])
        with tempfile.TemporaryDirectory(prefix='locallink-smoke-') as directory:
            server = create_server(Path(directory), '127.0.0.1', 0, 'Startup test', '123456')
            threading.Thread(target=server.serve_forever, daemon=True).start()
            view = QWebEngineView()
            result = {'ok': False, 'qt': qVersion(), 'error': 'startup timeout'}
            def finish(value):
                result.update(ok=bool(value), error='' if value else 'UI did not load')
                app.quit()
            def loaded(ok):
                if not ok:
                    finish(False)
                else:
                    view.page().runJavaScript("Boolean(document.getElementById('historySearch') && document.querySelector('link[href*=workspace]'))", finish)
            view.loadFinished.connect(loaded)
            QTimer.singleShot(30000, app.quit)
            view.load(QUrl(f'http://127.0.0.1:{server.server_port}/?code=123456'))
            app.exec()
            server.shutdown()
            server.server_close()
            report.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
            return 0 if result['ok'] else 1
    except Exception:
        report.write_text(json.dumps({'ok': False, 'error': traceback.format_exc()}), encoding='utf-8')
        return 1
