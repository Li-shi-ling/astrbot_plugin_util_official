# QQOfficial Util

QQOfficial 适配版娱乐工具插件。当前主功能移植自 NullDox 的“虚拟开盒”效果，但只保留 QQOfficial 能稳定支持的入口和数据。

当前版本：v1.2.0

## 使用方式

在 QQ 官方机器人群聊里发送：

```text
@机器人 盒 123456789
```

要求：

- 必须先 @ 机器人。
- QQOfficial 的机器人 @ 在 AstrBot 消息链中表现为 `At(qq="qq_official")`。
- 纯文本必须匹配 `盒 QQ号`。
- 不支持唤醒词触发，不支持 `/盒`，不支持 `@目标用户` 解析目标。

## 输出内容

插件会生成随机娱乐信息：

- 账号：使用指令里输入的 QQ 号。
- 手机：随机生成。
- IP 地址：随机生成。
- 物理地址：从本地行政区划数据随机生成，或在启用腾讯地图增强时随机搜索 POI。
- QQ 头像：使用 `qlogo.cn` 按输入 QQ 号加载。
- 可选静态地图：启用腾讯地图增强后附加。

输出中不会包含群聊 ID。QQOfficial 群聊 ID 是 `group_openid`，不是用户可识别的真实群号。

## QQOfficial 限制

- 无法从群聊事件拿到发送者真实 QQ 号，只能拿到 openid/member_openid。
- 无法通过 openid 换取真实 QQ 号。
- 无法获取可靠退群事件，所以本插件不实现退群触发。
- 配置项里没有群聊白名单/黑名单。

## 恶魔轮盘多人模式

QQOfficial 群聊内可使用无庄家多人恶魔轮盘。首版支持 2-10 人，Bot 负责房间、弹队列、道具、回合和结算；所有信息都在群聊公开展示，不使用私聊或回调按钮。

常用指令：

```text
@机器人 轮盘绑定 昵称
@机器人 轮盘我的名字
@机器人 轮盘改名 新昵称
@机器人 轮盘创建
@机器人 轮盘加入
@机器人 轮盘设置
@机器人 轮盘设置 子弹上限 [数量]
@机器人 轮盘设置 子弹下限 [数量]
@机器人 轮盘设置 随机子弹 是/否
@机器人 轮盘设置 道具刷新上限 [数量]
@机器人 轮盘设置 道具刷新下限 [数量]
@机器人 轮盘设置 随机道具 是/否
@机器人 轮盘设置 道具持有上限 [数量]
@机器人 轮盘设置 血量上限 [数量]
@机器人 轮盘设置 血量下限 [数量]
@机器人 轮盘设置 随机血量 是/否
@机器人 轮盘开始
@机器人 轮盘状态
@机器人 轮盘开枪 自己
@机器人 轮盘开枪 编号
@机器人 轮盘道具 啤酒
@机器人 轮盘道具 香烟
@机器人 轮盘道具 手锯
@机器人 轮盘道具 放大镜
@机器人 轮盘道具 换向器
@机器人 轮盘结束
```

昵称绑定使用 QQOfficial 的 `member_openid` / `user_openid` 和群 `group_openid` 保存到插件数据目录下的 `roulette.db`。同一群昵称要求唯一；未绑定玩家会显示为 `玩家_短ID`。

`轮盘设置` 是群内公开默认设置，未开房时也可以修改；创建新房间时会复制当前默认值。数量按钮会生成带 `[数量]` 占位的指令，需要手动改成实际数字后发送。

放大镜仍是玩家个人持有和使用的道具，只是使用结果会在群里公开显示下一发是实弹还是空弹。

按钮说明：轮盘局面回复会附带 QQ 官方自定义 keyboard，按钮全部为 `action.type = 2` 指令按钮。文本指令始终是完整入口，即使客户端不显示按钮也能完成对局。

## 调试

发送：

```text
@机器人 qqofficial_debug
```

可以让 bot 输出当前 `QQOfficialWebhookMessageEvent` / `QQOfficialMessageEvent` 中能序列化的数据，便于查看实际 openid、message chain、raw message 等字段。

发送：

```text
@机器人 qqofficial_buttons
```

可以触发一条 QQOfficial Markdown 按钮组件消息。按钮消息会使用当前消息的 `msg_id` 作为被动回复上下文，避免被平台当作无权限的主动群消息。

当前 A/B 按钮使用 QQOfficial 指令按钮，不依赖 `INTERACTION_CREATE` 回调。点击后会生成 `qqofficial_button_a` / `qqofficial_button_b` 指令，再由插件回复“你按了 A/B”。

发送：

```text
@机器人 qqofficial_callback_buttons
```

可以触发一条 `action.type = 1` 的 QQOfficial 回调按钮组件消息，用于继续研究平台是否会投递 `INTERACTION_CREATE`。点击后的回调仍会尝试由插件 ACK 并回复“你按了 A/B”。

## 配置

`user_list_mode` / `user_list` 只按 QQOfficial 事件里的 sender openid/member_openid 过滤，不是 QQ 号。

腾讯地图增强为可选配置。未开启或接口失败时，插件会使用本地 `china_clean_v2.json` 随机地址。
