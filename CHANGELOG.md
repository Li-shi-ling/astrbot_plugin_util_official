# 更新日志

## v1.1.1

- 适配 QQOfficial 群聊触发方式：仅支持 `@机器人 盒 QQ号`。
- 移除退群触发逻辑和群聊配置项。
- 输出内容不再展示群聊 ID，避免把 `group_openid` 误认为真实群号。
- 保留 `qqofficial_debug` 调试指令用于查看 QQOfficial 事件数据。
- 增加 pytest 覆盖 QQOfficial 触发解析和输出约束。
