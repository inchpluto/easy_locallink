# 变更日志

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 格式，并尽量遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [未发布]

## [2.4.4] - 2026

### 新增

- Windows 关闭主窗口后缩小到系统托盘，仍可继续接收内容。
- Windows 托盘菜单可打开或更改本地接收目录，并可退出并停止服务。
- 收到内容时 Windows 与 Android 显示系统通知。

### 修复

- 稳定设备身份：可信设备以稳定 ID 为主键，Wi-Fi 重连或 DHCP 改变 IP 后自动刷新地址。
- 长时间离线恢复时连接预检有限重试，区分「服务未响应」与「配对失败」。

## [2.4.2] - 2026

### 修复

- 修正界面激活相关问题（详见 `docs/2.4.2-ui-activation-fix.md`）。

## [2.4.1] - 2026

### 修复

- 修正启动相关问题（详见 `docs/2.4.1-startup-fix.md`）。

## [2.4.0] - 2026

### 新增

- Android 2.4 内置本地主机与独立收件箱，不再依赖 Windows。
- 记录工作台：搜索、六种分类筛选、排序、日期分组与分页。
- 二维码完全离线生成，扫码即可连接。
- 可信设备快捷入口。
- 从系统分享面板发送文字、链接与文件。
- 背景信号光带与连接状态联动，可关闭的反馈音效。
- 统一的 LocalLink 蓝色应用图标。

### 说明

- 早期版本未系统维护变更日志，以上条目依据现有 `README.md` 与 `docs/` 整理。

[2.4.4]: https://github.com/LocalLink/LocalLink/compare/v2.4.2...v2.4.4
[2.4.2]: https://github.com/LocalLink/LocalLink/compare/v2.4.1...v2.4.2
[2.4.1]: https://github.com/LocalLink/LocalLink/compare/v2.4.0...v2.4.1
[2.4.0]: https://github.com/LocalLink/LocalLink/releases/tag/v2.4.0
