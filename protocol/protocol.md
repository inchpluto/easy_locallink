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

## 3. API

| Method | Path | 用途 |
|---|---|---|
| GET | `/api/status` | 设备、网络、发现的节点与历史 |
| GET | `/api/health` | 无敏感信息的服务可用性探测 |
| POST | `/api/scan` | 异步扫描当前 IPv4 `/24` 网段中的 LocalLink 主机 |
| POST | `/api/text` | 发送 UTF-8 文本，最大 256 KB |
| POST | `/api/upload` | 原始文件流上传 |
| GET | `/api/download/{id}` | 下载文件，支持 HTTP Range |
| DELETE | `/api/items/{id}` | 删除历史及对应文件 |

上传请求头：

- `Content-Length`: 文件字节数，必需
- `X-Filename`: URL 编码后的原始文件名
- `X-Sender`: URL 编码后的发送端名称
- `X-SHA256`: 可选；若提供，服务端写入后必须校验一致

文件先写入 `.part`，长度和摘要校验成功后原子重命名。失败的临时文件会被清理。

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
