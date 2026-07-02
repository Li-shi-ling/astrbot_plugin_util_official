# 更新日志

## v1.1.7

- 将 `qqofficial_buttons` 的 A/B 按钮改为 QQOfficial 指令按钮，点击后生成 `qqofficial_button_a` / `qqofficial_button_b` 命令，避免回调按钮依赖 `INTERACTION_CREATE` 导致请求超时。
- 新增 `qqofficial_button_a` 和 `qqofficial_button_b` 指令，分别回复“你按了 A/B”。

## v1.1.6

- 修复按钮点击后无响应的回调接收链路：发送按钮前兜底安装当前 QQOfficial client 的 `on_interaction_create` hook，并补充 `INTERACTION_CREATE` 所需的 interaction intent。
- 增加日志提示：如果 websocket 已连接，补充 interaction intent 后需要重启/重连 QQOfficial 平台才会收到点击事件。

## v1.1.5

- 调整 `qqofficial_buttons` 自定义按钮 payload 为 QQ 官方发送方式中的 `keyboard.content.rows` 结构，避免 API 返回成功但客户端不渲染按钮。

## v1.1.4

- 为 `qqofficial_buttons` 增加详细诊断日志，记录事件类型、原始消息字段、最终发送 payload、API 返回值和按钮回调处理过程。

## v1.1.3

- 修复 `qqofficial_buttons` 发送按钮组件时被识别为主动群消息导致无权限的问题。
- 按钮组件发送会携带原始消息 `msg_id` 和 `msg_seq`，按钮回调回复会携带 `event_id`，优先走 QQOfficial 被动回复路径。

## v1.1.1

- 适配 QQOfficial 群聊触发方式：仅支持 `@机器人 盒 QQ号`。
- 移除退群触发逻辑和群聊配置项。
- 输出内容不再展示群聊 ID，避免把 `group_openid` 误认为真实群号。
- 保留 `qqofficial_debug` 调试指令用于查看 QQOfficial 事件数据。
- 增加 pytest 覆盖 QQOfficial 触发解析和输出约束。
