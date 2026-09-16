# LocalLink 稳定设备身份与重新信任设计

## 问题

Windows 主机每次创建服务时都随机生成 `device_id`，Android 却把该值作为长期可信身份严格比对。重启或升级 EXE 后，正确的主机也会被误判为设备替换。

## 设计

- Python 主机把随机设备 ID 持久化在接收数据目录的 `.device-id`，再次启动同一数据目录时复用它。
- Android 自身继续使用 SharedPreferences 中的稳定 ID。
- 已通过 `/api/health` 服务识别和 `/api/status` 配对码认证、但可信 ID 不同的连接进入 `RETRUST_REQUIRED`，而不是不可恢复的 `FAILED`。
- Android 显示一次重新信任确认。确认后更新该主机的可信 ID 并继续原本的连接或发送；取消则不连接。
- 离线、非 LocalLink 服务、错误配对码和认证失败仍然进入 `FAILED`。

## 安全边界

设备 ID 只是本地稳定标识，不是密码学身份。重新信任必须发生在配对码认证成功之后，并要求手机端显式确认，不能静默迁移。

## 验证

- 同一数据目录连续创建两次 Python 主机，设备 ID 必须一致。
- 不同数据目录应得到不同 ID。
- JavaScript 和 Android 状态机把认证成功后的 ID 变化分类为 `RETRUST_REQUIRED`。
- 配对码错误仍为 `FAILED / PAIRING_REJECTED`。
