from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PLUGIN_ROOT / "main.py"


def load_plugin_module():
    spec = importlib.util.spec_from_file_location("qqofficial_util_main_buttons", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeRawMessage:
    pass


class FakeQQOfficialMessageEvent:
    def __init__(self, module, platform_name="qq_official"):
        self._module = module
        self._platform_name = platform_name
        self.message_obj = type(
            "Obj",
            (),
            {"raw_message": FakeRawMessage(), "sender": None, "message_id": "mid"},
        )()

    def get_platform_name(self):
        return self._platform_name

    def get_message_str(self):
        return "qqofficial_buttons"

    def plain_result(self, text):
        return text

    def stop_event(self):
        self.stopped = True


class FakeQQOfficialWebhookMessageEvent(FakeQQOfficialMessageEvent):
    pass


class FakeNonQQEvent(FakeQQOfficialMessageEvent):
    def get_platform_name(self):
        return "aiocqhttp"


FakeQQOfficialMessageEvent.__module__ = "astrbot.core.platform.sources.qqofficial.qqofficial_message_event"
FakeQQOfficialMessageEvent.__name__ = "QQOfficialMessageEvent"
FakeQQOfficialWebhookMessageEvent.__module__ = (
    "astrbot.core.platform.sources.qqofficial_webhook.qo_webhook_event"
)
FakeQQOfficialWebhookMessageEvent.__name__ = "QQOfficialWebhookMessageEvent"
FakeNonQQEvent.__module__ = "astrbot.core.platform.sources.other.fake_event"
FakeNonQQEvent.__name__ = "OtherEvent"


class FakeGroupMessage:
    def __init__(self, group_openid="group-openid", message_id="raw-mid", msg_seq=42):
        self.group_openid = group_openid
        self.id = message_id
        self.msg_seq = msg_seq


class FakeC2CAuthor:
    def __init__(self, user_openid="user-openid"):
        self.user_openid = user_openid


class FakeC2CMessage:
    def __init__(self, user_openid="user-openid", message_id="raw-c2c-mid", msg_seq=43):
        self.author = FakeC2CAuthor(user_openid=user_openid)
        self.id = message_id
        self.msg_seq = msg_seq


class FakeBotApi:
    def __init__(self):
        self.calls = []

    async def post_group_message(self, **payload):
        self.calls.append(("group", payload))

    async def post_c2c_message(self, **payload):
        self.calls.append(("c2c", payload))


def _collect_async_gen(async_gen):
    async def _runner():
        collected = []
        async for item in async_gen:
            collected.append(item)
        return collected

    return asyncio.run(_runner())


def test_button_keyboard_has_two_command_buttons():
    module = load_plugin_module()

    keyboard = module._build_button_keyboard()
    payload = module._build_button_message_payload()

    assert "content" in keyboard
    assert len(keyboard["content"]["rows"]) == 1
    buttons = keyboard["content"]["rows"][0]["buttons"]
    assert len(buttons) == 2
    assert buttons[0]["action"]["type"] == 2
    assert buttons[1]["action"]["type"] == 2
    assert buttons[0]["action"]["data"] == "qqofficial_button_a"
    assert buttons[1]["action"]["data"] == "qqofficial_button_b"
    assert buttons[0]["action"]["reply"] is True
    assert buttons[1]["action"]["reply"] is True
    assert buttons[0]["action"]["enter"] is False
    assert buttons[1]["action"]["enter"] is False
    assert payload["msg_type"] == 2
    assert payload["markdown"]["content"] == module.BUTTON_PROMPT
    assert payload["keyboard"]["content"]["rows"][0]["buttons"][0]["id"] == module.BUTTON_A_ID
    assert payload["keyboard"]["content"]["rows"][0]["buttons"][1]["id"] == module.BUTTON_B_ID


def test_callback_button_keyboard_has_two_callback_buttons():
    module = load_plugin_module()

    keyboard = module._build_callback_button_keyboard()
    payload = module._build_callback_button_message_payload()

    assert "content" in keyboard
    assert len(keyboard["content"]["rows"]) == 1
    buttons = keyboard["content"]["rows"][0]["buttons"]
    assert len(buttons) == 2
    assert buttons[0]["action"]["type"] == 1
    assert buttons[1]["action"]["type"] == 1
    assert buttons[0]["action"]["data"] == "callback_button_a"
    assert buttons[1]["action"]["data"] == "callback_button_b"
    assert buttons[0]["action"]["permission"]["type"] == 2
    assert buttons[1]["action"]["permission"]["type"] == 2
    assert payload["msg_type"] == 2
    assert payload["markdown"]["content"] == module.CALLBACK_BUTTON_PROMPT
    assert payload["keyboard"]["content"]["rows"][0]["buttons"][0]["id"] == module.CALLBACK_BUTTON_A_ID
    assert payload["keyboard"]["content"]["rows"][0]["buttons"][1]["id"] == module.CALLBACK_BUTTON_B_ID


def test_button_reply_text_maps_id_and_data():
    module = load_plugin_module()

    assert module._build_button_reply_text(module.BUTTON_A_ID, None) == "你按了 A"
    assert module._build_button_reply_text(None, module.BUTTON_B_DATA) == "你按了 B"
    assert module._build_button_reply_text(module.CALLBACK_BUTTON_A_ID, None) == "你按了 A"
    assert module._build_button_reply_text(None, module.CALLBACK_BUTTON_B_DATA) == "你按了 B"
    assert module._build_button_reply_text(None, None) == "你按了 未知"
    assert module._build_button_reply_payload("hello") == {
        "content": "hello",
        "msg_type": 0,
        "markdown": None,
        "keyboard": None,
    }


def test_button_debug_context_extracts_message_fields():
    module = load_plugin_module()
    raw_message = FakeGroupMessage(group_openid="group-openid", message_id="raw-mid", msg_seq=42)
    raw_message.event_id = "event-id"
    raw_message.author = SimpleNamespace(user_openid="user-openid", member_openid="member-openid")
    message_obj = SimpleNamespace(message_id="wrapped-mid")

    debug_context = module._build_button_debug_context(raw_message, message_obj)

    assert debug_context["raw_message_class"].endswith(".FakeGroupMessage")
    assert debug_context["raw_id"] == "raw-mid"
    assert debug_context["raw_msg_seq"] == 42
    assert debug_context["raw_event_id"] == "event-id"
    assert debug_context["message_obj_message_id"] == "wrapped-mid"
    assert debug_context["group_openid"] == "group-openid"
    assert debug_context["author_user_openid"] == "user-openid"
    assert debug_context["author_member_openid"] == "member-openid"


def test_button_command_limited_to_qqofficial_events():
    module = load_plugin_module()

    assert module._is_qqofficial_message_event(FakeQQOfficialMessageEvent(module)) is True
    assert module._is_qqofficial_message_event(FakeQQOfficialWebhookMessageEvent(module)) is True
    assert module._is_qqofficial_message_event(FakeNonQQEvent(module)) is False


def test_button_hook_from_event_adds_interaction_intent():
    module = load_plugin_module()
    plugin = object.__new__(module.QQOfficialUtilPlugin)
    bot = SimpleNamespace(api=FakeBotApi(), intents=1 << 25)
    event = FakeQQOfficialMessageEvent(module)
    event.bot = bot

    plugin._install_interaction_hook_from_event(event)

    assert bot.intents & module.QQOFFICIAL_INTERACTION_INTENT
    assert getattr(bot, "_codex_button_hook_installed", False) is True
    assert getattr(bot, "_codex_button_hook_owner", None) == id(plugin)
    assert callable(bot.on_interaction_create)


def test_button_command_sends_only_group_or_c2c(monkeypatch):
    module = load_plugin_module()
    plugin = object.__new__(module.QQOfficialUtilPlugin)

    group_api = FakeBotApi()
    group_event = FakeQQOfficialMessageEvent(module)
    group_event.message_obj = type("Obj", (), {"raw_message": FakeGroupMessage(), "sender": None, "message_id": "mid"})()
    group_event.bot = SimpleNamespace(api=group_api)
    group_event.stop_event = lambda: setattr(group_event, "stopped", True)

    c2c_api = FakeBotApi()
    c2c_event = FakeQQOfficialWebhookMessageEvent(module)
    c2c_event.message_obj = type("Obj", (), {"raw_message": FakeC2CMessage(), "sender": None, "message_id": "mid"})()
    c2c_event.bot = SimpleNamespace(api=c2c_api)
    c2c_event.stop_event = lambda: setattr(c2c_event, "stopped", True)

    monkeypatch.setattr(module.botpy_message, "GroupMessage", FakeGroupMessage)
    monkeypatch.setattr(module.botpy_message, "C2CMessage", FakeC2CMessage)

    group_result = _collect_async_gen(plugin.qqofficial_buttons(group_event))
    c2c_result = _collect_async_gen(plugin.qqofficial_buttons(c2c_event))

    assert group_result == []
    assert c2c_result == []
    assert group_api.calls[0][0] == "group"
    assert group_api.calls[0][1]["msg_type"] == 2
    assert group_api.calls[0][1]["msg_id"] == "raw-mid"
    assert group_api.calls[0][1]["msg_seq"] == 42
    assert group_api.calls[0][1]["markdown"]["content"] == module.BUTTON_PROMPT
    assert group_api.calls[0][1]["keyboard"] == module._build_button_keyboard()
    assert c2c_api.calls[0][0] == "c2c"
    assert c2c_api.calls[0][1]["msg_type"] == 2
    assert c2c_api.calls[0][1]["msg_id"] == "raw-c2c-mid"
    assert c2c_api.calls[0][1]["msg_seq"] == 43
    assert c2c_api.calls[0][1]["markdown"]["content"] == module.BUTTON_PROMPT
    assert c2c_api.calls[0][1]["keyboard"] == module._build_button_keyboard()
    assert getattr(group_event, "stopped", False) is True
    assert getattr(c2c_event, "stopped", False) is True


def test_callback_button_command_sends_callback_keyboard(monkeypatch):
    module = load_plugin_module()
    plugin = object.__new__(module.QQOfficialUtilPlugin)

    group_api = FakeBotApi()
    group_event = FakeQQOfficialMessageEvent(module)
    group_event.message_obj = type("Obj", (), {"raw_message": FakeGroupMessage(), "sender": None, "message_id": "mid"})()
    group_event.bot = SimpleNamespace(api=group_api)
    group_event.stop_event = lambda: setattr(group_event, "stopped", True)

    monkeypatch.setattr(module.botpy_message, "GroupMessage", FakeGroupMessage)
    monkeypatch.setattr(module.botpy_message, "C2CMessage", FakeC2CMessage)

    group_result = _collect_async_gen(plugin.qqofficial_callback_buttons(group_event))

    assert group_result == []
    assert group_api.calls[0][0] == "group"
    assert group_api.calls[0][1]["msg_type"] == 2
    assert group_api.calls[0][1]["msg_id"] == "raw-mid"
    assert group_api.calls[0][1]["msg_seq"] == 42
    assert group_api.calls[0][1]["markdown"]["content"] == module.CALLBACK_BUTTON_PROMPT
    assert group_api.calls[0][1]["keyboard"] == module._build_callback_button_keyboard()
    assert getattr(group_event, "stopped", False) is True


def test_command_buttons_reply_with_pressed_button():
    module = load_plugin_module()
    plugin = object.__new__(module.QQOfficialUtilPlugin)
    event_a = FakeQQOfficialMessageEvent(module)
    event_b = FakeQQOfficialMessageEvent(module)

    result_a = _collect_async_gen(plugin.qqofficial_button_a(event_a))
    result_b = _collect_async_gen(plugin.qqofficial_button_b(event_b))

    assert result_a == ["你按了 A"]
    assert result_b == ["你按了 B"]
    assert getattr(event_a, "stopped", False) is True
    assert getattr(event_b, "stopped", False) is True


def test_button_callback_reply_uses_interaction_event_id(monkeypatch):
    module = load_plugin_module()
    plugin = object.__new__(module.QQOfficialUtilPlugin)
    api = FakeBotApi()
    platform = SimpleNamespace(client=SimpleNamespace(api=api))
    context = module.QQOfficialInteractionContext(
        interaction_id="interaction-event-id",
        scene="group",
        chat_type=1,
        group_openid="group-openid",
        button_id=module.BUTTON_A_ID,
        button_data=module.BUTTON_A_DATA,
    )
    monkeypatch.setattr(module.random, "randint", lambda _start, _end: 88)

    asyncio.run(plugin._reply_button_press(platform, context))

    assert api.calls == [
        (
            "group",
            {
                "group_openid": "group-openid",
                "content": "你按了 A",
                "msg_type": 0,
                "markdown": None,
                "keyboard": None,
                "event_id": "interaction-event-id",
                "msg_seq": 88,
            },
        )
    ]
