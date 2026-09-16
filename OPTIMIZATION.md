# LocalLink 优化清单（2026-09-16 审计）

审计方式：在当前工作区实际运行 `locallink.server` 并发起真实 HTTP 请求验证，结论均可复现。
所有行号基于提交 `ebf8f54`。

**修复进度**：#1、#2、#8、#9、#10 已完成并带回归测试；
`python -m unittest discover -s tests` 现为 `Ran 33 tests ... OK (skipped=1)`。
其余条目仍待处理，#3（配对码速率限制）建议下一个做。

## P0 安全

### 1. 内联预览 SVG / HTML 与控制台同源，可执行脚本 ✅ 已修复

`server.py:_preview` → `_download(inline=True)` 对任意 MIME 一律返回
`Content-Disposition: inline`，且 `_headers` 不下发 CSP。实测：

```text
上传 invite.svg（内含 onload="fetch('/api/status?code='+...)"）
GET /api/preview/<id>?code=...
  Content-Type: image/svg+xml
  Content-Disposition: inline; filename*=UTF-8''invite.svg
  （无 Content-Security-Policy）
```

`.html` 同样拿到 `text/html` + `inline`。预览 URL 与控制台 `/` 同源，浏览器直接打开该 URL 时脚本
以同源身份执行，可读取 `/api/status` 中的 `pairing_code`、`device_id`、`peers`、`history`。
`.svg` 被 `capabilities.py` 归为 `image` 并带 `preview_inline`，所以这是一条正常可达的路径。

前端本身是安全的（缩略图走 `<img>`，PDF/Office 走 `sandbox` iframe），因此触发前提是有人
直接打开预览 URL——分享链接和二维码正是这种用法。

建议：对 `image/svg+xml`、`text/html`、`application/xhtml+xml` 强制 `attachment`，或加
`Content-Security-Policy: sandbox`；更彻底的方案是预览走独立端口（null origin）。

### 2. HTTP/1.1 keep-alive 连接可被残留请求体污染 ✅ 已修复

`LocalLinkHandler.protocol_version = "HTTP/1.1"`，但 `save_file` 只读 `Content-Length`
声明的字节数，不做 drain。实测（单条 keep-alive 连接）：

```text
POST /api/upload  Content-Length: 100，实际发送 5000 字节  -> 201 Created
残留 4900 字节留在 socket 缓冲
同一连接发送 GET /api/status   -> 501 Unsupported method ('AAAA…GET')
```

客户端声明长度小于实际长度（或被截断）就会污染后续请求。

> 状态（2026-09-16）：已修复，但方案与最初设想不同。
> 起初打算「读掉声明字节 + `peek()` 探测多余字节，发现多余就 `Connection: close`」。
> 实测发现这条路走不通：`peek()` 看到的「多余字节」与「客户端正确 pipeline 的下一条请求」
> 在这一层完全无法区分，该方案把合法的 pipeline 请求也一起关掉了。
> 最终实现只做一件确定正确的事——`_drain_request_body(consumed)` 把**声明的**
> `Content-Length` 剩余字节读完（这是 `X-SHA256` 非法等提前 return 的路径真正需要的），
> 超出声明长度的字节不做任何猜测，交由 `http.server` 按标准行为拒绝并断开。
> 回归测试：`tests/test_server.py::KeepAliveFramingTests`。

### 3. 配对码无速率限制，6 位数字可被暴力枚举

实测 200 次错误配对码请求在 **0.14 秒** 内全部返回，无延迟、无锁定。
`create_server` 用 `secrets.randbelow(1_000_000)` 生成，熵约 20 bit；
`desktop.py` 默认码是 `123456`，且 `bind_all=True` 使服务监听 `0.0.0.0`。
`secrets.compare_digest` 已正确使用，但缺少尝试次数限制。

建议：按来源 IP 失败计数 + 指数退避；配对码提到 8 位以上；
`protocol/protocol.md` 已经承诺 3.0 做二维码公钥交换，值得优先。

## P1 正确性与性能

### 4. 每次落盘都全量重写索引

`core.py:add_text` 与 `save_file` 都在追加一条记录后调用 `_persist()`，
把**全部**记录（含内联存储的 `text` 字段）`json.dumps(indent=2)` 重写一遍。
多文件批量发送时是 O(n²) 写放大，长文本会进一步放大。建议改 JSONL 追加或批量合并写。

### 5. 没有保留策略，索引无界增长

`grep -niE "retention|max_items|prune|cleanup|expire|quota|limit" locallink/*.py` **无匹配**。
`history.json` 与 `LocalLinkData/files` 只增不减，只能靠用户手动删除。
建议：按数量/天数/磁盘占用配置上限，启动时清理孤立文件。

### 6. 持锁期间做磁盘 I/O

`stats()` 在 `self._lock` 内对每个文件记录调用 `path_for(...).is_file()`；
`list()` 同样在锁内逐条 `is_file()`。`/api/status` 因此会阻塞整个 store。
建议先在锁内快照记录，再在锁外做 stat。

### 7. 配对码走 URL query

`?code=` 会进入访问日志（`log_message` 打印完整请求行）、浏览器历史与 Referer。
虽然已有 `Referrer-Policy: no-referrer`，但 `share_url` 仍把码放进 URL。
建议改为 header 优先 + 一次性会话令牌，URL 只在首次配对时使用。

## P2 工程化缺口

### 8. 没有 CI、没有依赖声明 ✅ 已修复

- `.github/` 下只有 `ISSUE_TEMPLATE/` 和 `PULL_REQUEST_TEMPLATE.md`，**无 workflows 目录**。
- 无 `requirements.txt` / `pyproject.toml` / `setup.py` / `setup.cfg`，也没有 lint、格式化、
  pre-commit 配置；但 `desktop.py` 硬依赖 PySide6（QtWebEngine + QtWebChannel）。
  新贡献者 clone 后无法直接 `python -m locallink.desktop`。

### 9. 测试基线是红的（4/22 失败，均为环境与写法问题） ✅ 已修复

```text
python -m unittest discover -s tests
Ran 22 tests ... FAILED (failures=1, errors=3)
```

- `tests/test_preview.py:4` 用 `import pytest`，而项目 runner 是 unittest →
  `ModuleNotFoundError: No module named 'pytest'`（整个模块加载失败）。
- `tests/test_packaging_runtime.py` 两例：`packaging_runtime.py:9`
  `importlib.util.find_spec('PySide6').origin` 在未安装 PySide6 时抛
  `AttributeError: 'NoneType' object has no attribute 'origin'`。应加 None 判空。
- `tests/test_core.py:32` 断言 `find_adb()` 以 Windows 反斜杠路径结尾，
  非 Windows 平台必然失败。应改为 `os.path.join` 或 `skipUnless(os.name == "nt")`。

### 10. 前端测试没有被任何入口执行 ✅ 已修复

`tests/connection_state.test.mjs` 与 `tests/web_ui.test.mjs` 实际是可通过的
（Node v22.22.3 下两个脚本均输出 passed、退出码 0），
但 `README.md` 的「测试」小节只写了 `python -m unittest discover -s tests -v`，
没有 CI 也没有文档命令，等于长期不被执行。

### 11. Android release 构建未启用混淆

`android/app/build.gradle` 的 `release` 块是 `minifyEnabled false`，
而 `proguard-rules.pro` 已存在。

## P3 文档与第三方依赖

### 12. README 引用的交付物不在仓库中

`README.md` / `README.en.md` 的「交付文件」指向 `dist/LocalLink-Portable.exe`、
`dist/2.4.4/LocalLink-Android-2.4.4-debug.apk`，而工作区不存在 `dist/`。
建议改为构建产物说明或指向 Releases。

### 13. 第三方 JS 缺少版本与完整性记录

`locallink/static/qrcode.min.js` 为单行压缩文件，19,927 字节，
SHA-256 `c541ef06327885a8415bca8df6071e14189b4855336def4f36db54bde8484f36`。
只有 LICENSE 文本，没有上游版本号、来源 URL 和校验和记录。
建议加一份 `THIRD_PARTY.md` 或 vendor manifest。

### 14. 小瑕疵

`core.py:safe_filename` 用 `.strip(".")` 处理首尾点号，导致
`safe_filename(".gitignore")` → `"gitignore"`，dotfile 名字被改写。
建议只去除结尾的点，保留前导点。
