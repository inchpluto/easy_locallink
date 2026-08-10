# LocalLink 传输记录、文件预览与连接逻辑优化设计

## 目标

在不改变 LocalLink“每台设备都可成为局域网主机”的基础架构下，解决长文本溢出、文件预览能力不一致和连接流程含混的问题，并为 Android APK 与 Windows 安装包提供由系统确认的安装入口。

## 已确认的产品决策

- 采用统一文件能力模型与连接状态机，不做全量原生重构。
- 文字记录采用三行摘要、自动换行和专门全文阅读窗口。
- Windows 使用本机 LibreOffice 将 Office 文件转换为 PDF；未安装或转换失败时调用系统应用。
- Android 不嵌入 LibreOfficeKit，通过兼容的系统应用打开 Office 文件。
- Android APK 可进入系统安装确认页；Windows EXE/MSI 可交给系统打开，但不静默执行。
- Android 系统分享完成后展示结果页，不自动进入远端主页。

## 根因分析

当前 `.payload strong` 强制 `white-space: nowrap`，而其直接父容器缺少 `min-width: 0`。在 CSS Grid 与 Flex 混合布局中，内部文本按最小内容宽度参与计算，长文本无法收缩。操作列又固定为 170px，增加“预览”按钮后需要更大空间，因此正文跨越传输方向、时间和操作列。

修复必须同时处理文本组件和外层布局：记录正文使用可收缩容器，文字摘要允许多行断词，操作区可换行，窄窗口切换为分层卡片。

## 统一文件能力模型

每条文件记录增加以下字段：

```json
{
  "mime_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  "category": "presentation",
  "actions": ["preview_convert", "open_external", "download"],
  "installable": false
}
```

能力枚举：

- `preview_inline`：浏览器内直接预览。
- `preview_convert`：Windows 主机转换为 PDF 后预览。
- `open_external`：交给当前设备的系统应用。
- `install`：进入系统安装确认流程。
- `download`：保存原文件。
- `unsupported`：没有可用查看方式。

Python 与 Android 主机输出相同协议字段。前端只依据能力渲染操作，不再自行维护一套扩展名判断。旧主机没有能力字段时，前端保留兼容判断。

## 文件类型行为

| 文件类型 | Windows | Android | 普通浏览器 |
|---|---|---|---|
| 图片、音频、视频、PDF | 内联预览 | 内联预览 | 内联预览 |
| TXT、MD、JSON、CSV | 安全文本预览 | 安全文本预览 | 安全文本预览 |
| DOC/DOCX、XLS/XLSX、PPT/PPTX | LibreOffice 转 PDF；失败则系统打开 | 下载到缓存后 `ACTION_VIEW` | 下载 |
| APK | 下载 | 显示包信息并进入系统安装确认 | 下载 |
| EXE/MSI | 系统打开或打开所在目录 | 下载 | 下载 |
| HTML、SVG | 隔离或纯文本预览，不执行脚本 | 同左 | 同左 |

## 预览服务

- `/api/preview/{id}` 继续负责浏览器原生格式。
- `/api/preview/{id}?format=pdf` 返回 Office 转换后的缓存 PDF。
- 缓存键由记录 ID、源文件大小和修改时间组成。
- 删除记录时同步清理预览缓存。
- Office 转换使用 LibreOffice `--headless --safe-mode` 和独立用户配置目录。
- 单次转换超时 60 秒；Office 文件超过 200 MB 不自动转换。
- 文本预览最多返回 2 MB，并通过独立 JSON 接口或转义后的纯文本展示。
- 原文件始终只读，转换失败不修改传输记录。

## 原生文件桥接

Windows 使用 Qt WebChannel 暴露受限操作：打开文件、打开所在目录、检测 LibreOffice。桥接只接受传输记录 ID，由 Python 服务端解析真实路径，网页不能传入任意文件系统路径。

Android WebView 暴露受限桥接：将文件下载到应用缓存、通过 FileProvider 授权临时读取、调用 `ACTION_VIEW`，或对 APK 调用系统安装流程。首次安装 APK 时检查 `canRequestPackageInstalls()`，未授权则打开当前应用的“安装未知应用”设置。所有安装均要求用户确认。

## 文字记录组件

- 列表正文使用 `white-space: pre-wrap`、`overflow-wrap: anywhere` 和三行 `line-clamp`。
- 摘要容器及其所有 Grid/Flex 父项设置 `min-width: 0`。
- 点击正文或“展开全文”打开文本阅读窗口。
- 阅读窗口提供复制、保存为 TXT 和安全链接识别。
- URL 通过 DOM 节点创建，不使用未清洗 HTML。
- 文件名最多显示两行，详情窗口展示完整名称。

## 响应式记录布局

- 宽屏使用 `minmax(0, 1fr) / 230px / 170px / minmax(190px, auto)`。
- 低于 1100px 时元信息和操作区进入第二行。
- 低于 600px 时使用单列卡片，路由、元信息和操作依次排列。
- 操作按钮允许换行；主要操作为实心按钮，删除保持危险色次级按钮。
- 图片记录可显示受限缩略图，其他文件显示类型图标和类别标签。

## 连接状态机

统一状态：

```text
idle → probing → identifying → authenticating → ready
                                      ↘ failed
```

- `probing`：检查目标地址是否可访问。
- `identifying`：读取 `/api/health` 并确认服务类型、设备 ID 和协议版本。
- `authenticating`：通过 `/api/status` 验证配对码。
- `ready`：显示“正在向 {设备名} 发送”，允许传输。
- `failed`：保留输入并显示可恢复操作。

可信设备同时保存设备 ID、名称、地址和配对信息。同一地址返回不同设备 ID 时进入 `IDENTITY_CHANGED`，必须重新确认。已信任设备配对码失效时只清除凭据，不删除设备和历史。

Android 系统分享进入应用后先选择接收设备，发送成功进入结果页，提供“继续发送”“查看记录”“返回设备”三个操作。

## 错误模型

统一错误代码：

- `DEVICE_OFFLINE`
- `NOT_LOCAL_LINK`
- `PAIRING_REQUIRED`
- `PAIRING_REJECTED`
- `IDENTITY_CHANGED`
- `NETWORK_BLOCKED`
- `PREVIEW_UNSUPPORTED`
- `PREVIEW_CONVERSION_FAILED`
- `NO_EXTERNAL_VIEWER`
- `INSTALL_PERMISSION_REQUIRED`

网页和 Android 将错误代码映射为针对性中文说明，不直接显示底层异常。服务端日志保留底层原因。

## 安全边界

- 预览和打开接口仅接受已存在的记录 ID，禁止任意路径。
- Office 转换在独立临时目录运行，最长 60 秒。
- HTML 不在主页面上下文执行；SVG 不允许活动内容。
- 安装按钮必须由用户主动点击。
- APK 显示包名、版本、来源设备、大小和 SHA-256 摘要。
- LocalLink 不绕过 Android 安装确认、Windows SmartScreen、UAC 或杀毒软件。
- 扩展名与实际类型明显不匹配时隐藏安装操作。

## 测试设计

### 自动测试

- 能力解析：常见图片、Office、APK、EXE、未知扩展名和伪装扩展名。
- 文字摘要：包含中文长段落、连续 URL、无空格英文、换行和 HTML 字符。
- 预览接口：鉴权、Range、内联响应、文本大小限制和非法记录 ID。
- Office 转换：未安装、成功、失败、超时、缓存命中和记录删除清理。
- 连接状态：离线、非 LocalLink、错误配对码、身份变化和成功连接。
- Android：FileProvider URI、外部查看器缺失、APK 安装权限未授予。

### 运行时验收

- Windows 1366×768 与窄窗口检查记录无横向溢出。
- Android Pixel 7 检查三行摘要、全文弹窗和底部导航。
- 实际传输 TXT、长链接、PNG、PDF、DOCX、PPTX 和 APK。
- PC 有/无 LibreOffice 两种环境分别验证。
- 手机对手机验证 Office 外部打开与 APK 系统安装确认。
- 验证发送完成后停留在结果页，不跳转到远端主页。

## 版本与兼容性

- 版本提升为 LocalLink 2.3。
- 保留协议 v2 的现有上传、下载和发现接口。
- 新能力字段为向后兼容扩展；旧客户端忽略即可。
- 不引入云端服务，不要求账号，不上传文档到互联网。
