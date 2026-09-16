# 贡献指南

感谢你考虑为 LocalLink 贡献代码！本文档说明如何参与开发、提交代码和报告问题。

## 行为准则

参与本项目即表示你同意遵守 [行为准则](CODE_OF_CONDUCT.md)。请以尊重、友善的方式与其他人协作。

## 我能做什么

- **报告 Bug**：使用 [Bug 报告模板](.github/ISSUE_TEMPLATE/bug_report.yml)，尽量附上复现步骤、系统环境和日志。
- **提出功能建议**：使用 [功能请求模板](.github/ISSUE_TEMPLATE/feature_request.yml)。
- **改进文档**：README、协议文档 `protocol/protocol.md`、设计规范等。
- **提交代码**：修复 Bug、新增测试、实现新功能。

## 开发环境

- Python 3.10+（Windows 与 Android 两端共用的服务端核心）
- Android SDK / Gradle（`android/` 目录，构建 APK）
- Windows 环境（构建 PyInstaller 单文件 EXE）

## 快速开始

```powershell
# 列出可用网卡，确认真实 LAN 地址
python -m locallink --list-interfaces

# 以源码方式运行局域网主机
python -m locallink --interface 192.168.1.82 --code 123456

# 桌面控制台
python -m locallink.desktop
```

默认接收目录为工作目录下的 `LocalLinkData`（已加入 `.gitignore`，不会被提交）。

## 运行测试

提交前请确保测试通过：

```powershell
# Python 单元测试
python -m unittest discover -s tests -v

# Web UI 测试（需要 Node.js）
node tests/web_ui.test.mjs
node tests/connection_state.test.mjs
```

Android JVM 单元测试：

```powershell
cd android
gradle --no-daemon testDebugUnitTest
```

## 代码风格

- Python 遵循 PEP 8，保持与现有模块一致的命名和注释风格。
- 前端代码位于 `locallink/static/`，为无构建步骤的纯 JavaScript/HTML/CSS。
- 提交信息使用清晰的中文或英文描述，说明「做了什么」和「为什么」。
- 一个提交尽量只做一件事，便于 review 和回溯。

## 提交 Pull Request

1. Fork 本仓库并创建分支（建议命名如 `fix/xxx`、`feat/xxx`）。
2. 在分支上开发，并补充或更新相关测试与文档。
3. 本地运行测试，确保全部通过。
4. 提交 PR，描述变更内容、动机和验证方式。
5. 等待维护者 review；如有反馈，请及时响应。

## 安全相关

LocalLink 涉及网络传输与访问控制。如果你发现安全漏洞，请**不要**在公开 issue 中披露，改按 [SECURITY.md](SECURITY.md) 的流程私下报告。

## 许可证

贡献的代码默认以 [MIT License](LICENSE) 授权。请确认你有权提交这些代码，且不包含违反第三方许可的内容。
