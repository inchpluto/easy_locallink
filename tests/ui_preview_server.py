"""Local-only UI fixture: disposable records, no discovery or production data."""
import io
import tempfile
import time
from pathlib import Path

from locallink.server import create_server


def main():
    with tempfile.TemporaryDirectory(prefix='locallink-ui-') as directory:
        server = create_server(Path(directory), '127.0.0.1', 53421, '设计验证主机（示例数据）', '123456')
        store = server.store
        for index in range(23):
            record = store.add_text(f'示例记录 {index + 1}：用于验证分页与日期分组。', '测试手机', server.device_name)
            record.created_at -= 86400 + index * 7200
        note = '项目交接说明 & README.txt'
        data = '示例文本文件\n路径、符号与中文都应正确显示。\n<script>alert("不会执行")</script>'.encode('utf-8')
        store.save_file(io.BytesIO(data), note, len(data), '办公电脑', receiver=server.device_name)
        store.add_text('会议笔记\n今天确认了文件预览和手机端布局。请保留以下资料链接：\nhttps://example.com/docs\n' + '这是一条很长的文字记录，需要自动换行，不能挤压操作按钮。' * 18, '我的 Android 手机', server.device_name)
        # A removed file is intentional fixture data, not user content.
        record = store.save_file(io.BytesIO(b'demo'), '项目资料_演示文稿_最终确认版本.pptx', 4, '办公电脑', receiver=server.device_name)
        store.path_for(record).unlink()
        print('http://127.0.0.1:53421/?code=123456#historySection', flush=True)
        try:
            server.serve_forever()
        finally:
            server.server_close()


if __name__ == '__main__':
    main()
