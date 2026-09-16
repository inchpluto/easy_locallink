# LocalLink LAN Protocol v2

LocalLink 的 MVP 只依赖局域网。互联网、账号系统和云端服务器都不参与传输。

## 1. 设备发现

- IPv4 multicast group: `239.255.42.99`
- UDP port: `53318`
- 周期: 3 秒
- 过期时间: 12 秒

广播数据为 UTF-8 JSON：

```json
{
  "service": "locallink",
  "version": "2",
  "id": "随机设备 ID",
  "name": "Pluto-PC",
  "port": 53317
}
```

广播 socket 显式绑定用户选择的 LAN IPv4，避免误走 VPN、WSL、VMware 或 TUN 网卡。

## 2. 配对

每台主机使用 6 位本地配对码。API 请求通过查询参数 `code` 或请求头
`X-LocalLink-Code` 携带配对码。关闭进程后随机码失效。

这能防止同一局域网中的陌生设备直接浏览或写入文件，但它不是端到端加密。
只应在可信局域网使用 MVP；正式版本应加入基于二维码的公钥交换和 TLS。

6 位配对码只有约 20 bit 熵，因此每台主机必须对失败尝试限速，否则同一局域网内的设备
可以在数秒内枚举出配对码。约定如下：

- 限速按**来源地址**计数，某台设备猜测失败不会锁定其他设备。
- 前 `free_attempts`（默认 5）次错误尝试会正常比对配对码并返回 `401`。
- 之后每次尝试先等待指数退避（`1s` 起，每次翻倍，上限 `60s`），并在比对配对码
  **之前**直接返回 `429 Too Many Requests`，响应头带 `Retry-After` 秒数。
  也就是说被限速的来源即使愿意等待，也无法继续枚举。
- 任何一次认证成功会清空该来源的计数；`idle_forget`（默认 900 秒）后条目被回收。
- `429` 不读取请求体，客户端不得在同一连接上继续 pipeline 该请求体。
- `/api/status` 返回 `auth: {failed_attempts, throttled_sources}` 用于观测。

## 3. API

| Method | Path | 用途 |
|---|---|---|
| GET | `/api/status` | 设备、网络、发现的节点与历史 |
| GET | `/api/health` | 无敏感信息的服务可用性探测 |
| POST | `/api/scan` | 异步扫描当前 IPv4 `/24` 网段中的 LocalLink 主机 |
| POST | `/api/text` | 发送 UTF-8 文本，最大 256 KB |
| POST | `/api/upload` | 原始文件流上传 |
| GET | `/api/download/{id}` | 下载文件，支持 HTTP Range |
| GET | `/api/preview/{id}` | 浏览器安全内联预览；Office 可加 `format=pdf` |
| DELETE | `/api/items/{id}` | 删除历史及对应文件 |

除 `/api/health` 外，所有接口都需要配对码：错误或已失效返回 `401`，来源被限速时
返回 `429 Too Many Requests` 并带 `Retry-After` 秒数。

上传请求头：

- `Content-Length`: 文件字节数，必需
- `X-Filename`: URL 编码后的原始文件名
- `X-Sender`: URL 编码后的发送端名称
- `X-SHA256`: 可选；若提供，服务端写入后必须校验一致

文件先写入 `.part`，长度和摘要校验成功后原子重命名。失败的临时文件会被清理。

### 3.1 文件能力

`/api/status` 的每条文件记录包含 `mime_type`、`category`、`actions` 和
`installable`。操作值包括 `preview_inline`、`preview_convert`、`open_external`、
`install` 与 `download`。客户端只按这些能力显示操作，避免各端自行猜测文件类型。

Windows 的 `preview_convert` 使用本机 LibreOffice 无界面转换，默认最大 200 MB、
超时 60 秒，并按记录 ID、大小和修改时间缓存 PDF。转换失败会删除 `.part` 文件。
Android 不嵌入 Office 引擎，通过 FileProvider 临时授权给兼容应用。

### 3.2 连接状态

连接状态固定为 `idle → probing → authenticating → ready`，普通失败进入 `failed`，已认证但可信 ID 变化时进入可恢复的 `retrust_required`。
探测阶段校验 `/api/health` 的 `service=locallink`，认证阶段请求受保护的
`/api/status`。可信设备还会比较健康接口返回的设备 ID；若 ID 变化，返回
`IDENTITY_CHANGED` 并停止自动发送。客户端必须先完成配对码认证，再提示用户明确重新信任；确认后更新可信设备 ID 并继续连接，取消则保持断开。

可信记录以设备 ID 为主键，IP 和端口是可随发现结果更新的路由信息，配对码按设备分别保存。连接从休眠或长时间离线恢复时允许有限次数重试，但配对码错误和身份变化不得静默放行。

## 4. 多主机模型

- Windows EXE 与每台 Android APP 都运行相同语义的 HTTP 主机和本地收件箱。
- Android 使用前台服务保持 `53317` 监听，并通过 `53318/UDP` 广播自身。
- 组播发现失败时，可主动扫描当前 `/24` 网段的 `/api/health`。
- 发送方连接接收方主机；文本和文件始终落盘在接收设备，记录保存 `sender → receiver`。
- 手机与手机、手机与电脑、电脑与手机均不依赖第三台中转设备。

## 5. 边界

- VPN 若在防火墙/WFP 层启用了 Block LAN/Kill Switch，应用层无法绕过，需在 VPN 中允许 LAN。
- Android 会将 LocalLink 进程绑定到 Wi-Fi 网络，避免手机侧 VPN/移动数据分流。
- 断点下载已通过 HTTP Range 支持；断点上传、E2E 加密属于后续协议版本。
- EXE、MSI 和 APK 均不会静默执行；Windows SmartScreen/UAC 与 Android 系统安装确认不会被绕过。
