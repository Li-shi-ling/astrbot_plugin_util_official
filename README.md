# QQOfficial Util

QQOfficial 适配版娱乐工具插件。当前主功能移植自 NullDox 的“虚拟开盒”效果，但只保留 QQOfficial 能稳定支持的入口和数据。

当前版本：v1.1.1

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

## 调试

发送：

```text
@机器人 qqofficial_debug
```

可以让 bot 输出当前 `QQOfficialWebhookMessageEvent` / `QQOfficialMessageEvent` 中能序列化的数据，便于查看实际 openid、message chain、raw message 等字段。

## 配置

`user_list_mode` / `user_list` 只按 QQOfficial 事件里的 sender openid/member_openid 过滤，不是 QQ 号。

腾讯地图增强为可选配置。未开启或接口失败时，插件会使用本地 `china_clean_v2.json` 随机地址。
