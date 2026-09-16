# LocalLink

LocalLink 是一个不经过互联网的设备传输工具。Windows 与 Android 都可以成为局域网主机；手机、电脑可直接互相发现并发送文件、图片、链接和文字。

## 交付文件

- Windows 便携单文件：`dist/LocalLink-Portable.exe`
- Windows 2.4.4 单文件：`dist/2.4.4/LocalLink-Portable.exe`
- Android 2.4.4 APK：`dist/2.4.4/LocalLink-Android-2.4.4-debug.apk`

Windows EXE 与 APK 当前均为未签名/开发签名构建，适合个人设备测试。公开分发前应配置代码签名证书和 Android release keystore。

## 已实现功能

### 传输核心

- 文本、链接、单文件和多文件发送
- 大文件流式写入，不一次性载入服务端内存
- SHA-256 完整性校验和失败临时文件清理
- HTTP Range 断点下载
- 传输记录、搜索、类型筛选、全文阅读、复制、预览、打开、下载和删除
- 长文本三行换行摘要，文件名和操作区可响应式折行，不再挤出页面
- Windows 安装 LibreOffice 后可把 Word、Excel、PPT 转为缓存 PDF 在线预览
- 6 位进程级配对码
- 文件名净化和目录穿越防护
- 本地存储数量与空间统计

### 网络

- 指定真实 Wi-Fi/Ethernet IPv4，避开 VPN/TUN/VMware 网卡
- UDP multicast LocalLink 节点发现
- 当前 `/24` 网段主动扫描，列出可连接的 LocalLink 设备
- VPN、网关和 LAN 阻断诊断
- ProtonVPN 等阻断 LAN 时支持 Android USB/ADB 反向端口转发
- 无账号、无云端、无互联网依赖

### Windows EXE

- EXE 是默认传输主机，双击后自动识别 LAN 地址并立即监听 `53317`
- 默认配对码为 `123456`，无需再运行 `python -m locallink`
- 内嵌 Chromium 传输控制台，无需额外打开浏览器
- “打开”只按记录 ID 解析本地文件并交给 Windows 默认应用，网页不能传入任意路径
- 文件下载保存对话框
- 关闭窗口时停止服务并清理 ADB reverse

### Android APP

- Android 2.4 内置本地主机和独立收件箱，不再依赖 Windows
- 原生设备主页压缩为单屏，手动连接表单按需展开
- 收件箱采用“主页 / 发送 / 记录 / 设备”底部导航，不再把所有功能纵向堆叠
- 使用统一的 LocalLink 蓝色应用图标（Windows EXE 与 Android APP）
- 可从相册、文件管理器和浏览器使用“分享 → LocalLink”，再选择接收设备
- 二维码完全离线生成，手机相机扫码即可打开局域网连接地址
- 连接过的设备可保存为可信设备快捷入口（本地保存，不代表 3.0 的加密身份认证）
- 文字、图片、音视频、PDF 与常见文本文件支持直接预览
- Word、Excel、PPT 可下载到应用缓存后交给兼容应用打开
- APK 经包校验、LocalLink 风险确认和 Android 系统安装确认后可安装；不支持静默安装
- 连接经过服务识别、配对码认证和可信设备 ID 核对；身份变化时在认证成功后提示重新信任，不再永久阻断升级后的设备
- 可信设备以稳定 ID 为主键，Wi-Fi 重连或 DHCP 改变 IP 后自动刷新地址，并保留各设备独立的配对码
- 从长时间离线恢复时连接预检会有限重试，区分“服务尚未响应”和“配对失败”，避免误报不同网段
- 从系统分享发送成功后停留在原生结果页，可继续发送、查看记录或返回设备列表
- Android 收到内容时显示系统通知
- Windows 关闭主窗口后缩小到系统托盘，仍可继续接收内容
- Windows 收到文字或文件时显示托盘通知
- Windows 托盘菜单可打开或更改本地接收目录
- 前台服务保持主机在线，并显示持续通知
- 手机与手机可在同一 Wi-Fi 内直接双向发送
- 保存上次主机地址和配对码
- 连接时强制使用手机 Wi-Fi 网络，避免手机 VPN 或移动数据错误分流
- 支持粘贴完整分享链接，并在打开页面前检查电脑健康接口
- LAN 与 USB 两种连接方式
- Android 系统文件选择器和多文件选择
- DownloadManager 下载到系统 Downloads
- 连接失败提示、刷新、返回连接页
- 自动适配 LocalLink 响应式传输界面
- “网络曙光控制舱”深色视觉系统，桌面端强调一屏掌控，手机端保留四页底部导航
- 低干扰连接、成功和错误反馈音，可在双端界面中关闭并记忆设置
- 背景信号光带与连接状态联动；系统关闭动画时自动使用静态效果

接收内容保存在接收设备自己的 `LocalLinkData` 中。传输记录清晰展示发送端与接收端；文字可复制，文件可下载到系统 Downloads，记录支持搜索、筛选和删除。

## 使用 Windows EXE

运行：

```text
dist\LocalLink-Portable.exe
```

无需选择模式或额外运行后台命令。主窗口出现时服务已经启动，手机填写 EXE 页面显示的 `IP:端口` 和配对码即可。

首次运行新版 EXE 时会出现一次 Windows 管理员授权，用于创建 `LocalLink LAN TCP 53317` 入站规则。该规则只允许本地子网访问，不向互联网开放。必须同意该授权，否则手机无法连接。EXE 会监听所有本机 IPv4 网卡，但只对外展示自动识别的真实 LAN 地址，避免 VPN 或虚拟网卡切换导致服务失联。

若曾拒绝授权，可用管理员 PowerShell 手动执行：

```powershell
netsh advfirewall firewall add rule name="LocalLink LAN TCP 53317" dir=in action=allow protocol=TCP localport=53317 remoteip=localsubnet profile=any enable=yes
```

如果需要 USB/ADB 反向端口模式，仍可使用源码命令 `python -m locallink --usb --code 123456`。

## 使用 Android APP

安装：

```powershell
adb install -r android\app\build\outputs\apk\debug\app-debug.apk
```

打开 APP 后会自动启动“我的本机收件箱”，页面显示手机的 Wi-Fi IP 和配对码。附近安装并打开 LocalLink 的手机或电脑会自动出现在设备列表；也可以点击“扫描”主动检查当前网段。

手机互传：

1. 两台手机连接同一个 Wi-Fi，并分别打开 LocalLink。
2. 在手机 A 的“附近设备”中选择手机 B。
3. 发送内容会直接保存在手机 B 的本机收件箱。
4. 手机 B 打开“我的本机收件箱”即可复制文字、下载文件或管理记录。

手动连接示例：

```text
主机：192.168.1.82:53317
配对码：123456
```

Android 2.4 的 `53317` 端口默认用于手机本机收件箱。USB/ADB 反向端口属于源码兼容模式，使用前需先停止 Android 的 LocalLink 前台服务，避免端口冲突。LAN 互传无需 ADB。

### LocalLink 2.4 新功能

1. 在主页点击“二维码”，同一局域网中的设备扫码即可连接。
2. 点击“信任设备”后，该地址和配对码会保存在当前设备中，便于下次快速连接。
3. 传输记录中的“预览”支持文字、图片、音视频、PDF、Markdown、JSON 和 CSV。
4. Android 可从系统分享面板接收文字、链接、单个文件或多个文件。
5. Windows 点击关闭按钮后服务进入系统托盘；托盘菜单可打开或更改接收目录，选择“退出并停止服务”才会关闭主机。
6. 长文本使用三行摘要和专用全文阅读器；全文可复制或保存为 TXT。
7. Windows 可预览 Office 转换后的 PDF；Android 使用系统兼容应用打开 Office 文件。
8. APK 仅在用户点击“安装”后进入 Android 权限与系统安装确认流程。
9. 连接流程会先检查 LocalLink 身份，再认证配对码，并核对已信任设备 ID；升级或重装造成身份变化时，手机端会要求重新信任后继续连接。
10. PC/Web 与 Android 统一为近黑、钴蓝与青色信号体系；手机端保持主页、发送、记录、设备四个独立工作区。
11. 增加克制的局域网信号背景动效、按钮状态反馈与可关闭音效，并尊重系统“减少动态效果”设置。

二维码功能使用随程序离线分发的 QRCode.js，来源为 davidshimjs/qrcodejs，采用 MIT License；许可文本位于 `locallink/static/qrcodejs.LICENSE`。

## 源码运行

要求 Python 3.10+：

```powershell
python -m locallink --list-interfaces
python -m locallink --interface 192.168.1.82 --code 123456
python -m locallink --usb --code 123456
python -m locallink.desktop
```

默认接收目录为 EXE 同目录下的 `LocalLinkData`。

## 构建

Windows：

```powershell
python -m PyInstaller --noconfirm --clean LocalLink-Portable.spec
```

Android：

```powershell
cd android
gradle --no-daemon assembleDebug
```

Android 工程的 `local.properties` 是本机 SDK 路径，仅用于当前开发环境；迁移机器后应重新生成。

## 测试

```powershell
python -m unittest discover -s tests -v
```

协议细节与安全边界见 [protocol/protocol.md](protocol/protocol.md)。

## 贡献

欢迎提交 issue 和 Pull Request。参与前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 与 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。

发现安全漏洞请勿公开披露，请按 [SECURITY.md](SECURITY.md) 的流程私下报告。

## 许可证

本项目以 [MIT License](LICENSE) 开源，版权归 LocalLink contributors 所有。

二维码功能使用随程序离线分发的 [qrcodejs](https://github.com/davidshimjs/qrcodejs)（MIT License），许可文本见 `locallink/static/qrcodejs.LICENSE`。
