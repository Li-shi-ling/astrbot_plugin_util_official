from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PLUGIN_ROOT / "main.py"


def load_plugin_module():
    spec = importlib.util.spec_from_file_location("qqofficial_util_main_open_room", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _run(coro):
    return asyncio.run(coro)


def test_open_room_parser_accepts_friendly_create_template():
    module = load_plugin_module()

    parsed = module.parse_create_payload(
        "1234-5678｜绝地潜兵2 / Steam｜备注=难度7，缺样本｜初始=2｜上限=4"
    )

    assert parsed["locator_text"] == "1234-5678"
    assert parsed["game_or_platform"] == "绝地潜兵2 / Steam"
    assert parsed["note"] == "难度7，缺样本"
    assert parsed["initial_count"] == 2
    assert parsed["max_count"] == 4
    assert parsed["is_long_term"] is False


def test_open_room_keyboard_uses_command_buttons_with_limits():
    module = load_plugin_module()

    keyboard = module._build_open_room_keyboard(kind="menu")
    rows = keyboard["content"]["rows"]
    buttons = [button for row in rows for button in row["buttons"]]

    assert len(rows) <= 5
    assert all(len(row["buttons"]) <= 5 for row in rows)
    assert all(button["action"]["type"] == 2 for button in buttons)
    assert [button["render_data"]["label"] for button in buttons] == [
        "创建短期房",
        "创建长期房",
        "查找房间",
        "输入加入",
        "删除房间",
    ]
    assert buttons[0]["action"]["data"].startswith("开房创建 ")
    assert buttons[2]["action"]["data"] == "开房查找"
    assert buttons[3]["action"]["data"] == "开房加入 #RM0001"


def test_open_room_entry_keyboard_uses_join_buttons_for_not_full_entries(tmp_path):
    module = load_plugin_module()
    store = module.OpenRoomStore(tmp_path / "open_room.db")

    async def scenario():
        await store.initialize()
        entry = await store.create_entry(
            group_id="group",
            owner_id="owner",
            locator_text="room-code",
            game_or_platform="Game",
            note="note",
            initial_count=1,
            max_count=4,
            is_long_term=False,
        )
        return module._build_open_room_keyboard([entry], kind="entry")

    keyboard = _run(scenario())
    buttons = [button for row in keyboard["content"]["rows"] for button in row["buttons"]]

    assert buttons[0]["render_data"]["label"] == "加入 RM0001"
    assert buttons[0]["action"]["data"] == "开房加入 #RM0001"
    assert buttons[-1]["action"]["data"] == "开房"


def test_open_room_store_is_group_scoped_and_prevents_duplicate_join(tmp_path):
    module = load_plugin_module()
    store = module.OpenRoomStore(tmp_path / "open_room.db")

    async def scenario():
        await store.initialize()
        entry = await store.create_entry(
            group_id="group-a",
            owner_id="owner",
            locator_text="room-code",
            game_or_platform="Game",
            note="tonight",
            initial_count=1,
            max_count=2,
            is_long_term=False,
        )
        assert entry.code == "RM0001"
        assert await store.find_entries("group-b", "") == []
        joined = await store.join_entry("group-a", "#RM0001", "member")
        assert joined.current_count == 2
        with pytest.raises(ValueError, match="已经加入"):
            await store.join_entry("group-a", "#RM0001", "member")
        with pytest.raises(ValueError, match="人数已满"):
            await store.join_entry("group-a", "#RM0001", "another")

    _run(scenario())


def test_open_room_dispatch_create_find_join_delete(tmp_path):
    module = load_plugin_module()
    plugin = object.__new__(module.QQOfficialUtilPlugin)
    plugin.open_room_store = module.OpenRoomStore(tmp_path / "open_room.db")

    async def scenario():
        await plugin.open_room_store.initialize()
        message, entries, keyboard = await plugin._dispatch_open_room_command(
            "开房创建 code｜Game｜备注=tonight｜初始=1｜上限=3",
            "group",
            "owner",
        )
        assert "创建成功" in message
        assert entries[0].code == "RM0001"
        assert keyboard == "entry"
        message, entries, keyboard = await plugin._dispatch_open_room_command(
            "开房查找 Game",
            "group",
            "member",
        )
        assert "找到 1 个房间" in message
        assert entries[0].code == "RM0001"
        message, entries, keyboard = await plugin._dispatch_open_room_command(
            "开房加入 #RM0001",
            "group",
            "member",
        )
        assert "加入成功" in message
        assert entries[0].current_count == 2
        message, entries, keyboard = await plugin._dispatch_open_room_command(
            "开房删除 #RM0001",
            "group",
            "owner",
        )
        assert message == "房间已删除。"
        assert entries == []
        assert keyboard == "menu"

    _run(scenario())


class FakeRawMessage:
    def __init__(self):
        self.group_openid = "group-openid"
        self.group_member_openid = "member-openid"
        self.author = SimpleNamespace(member_openid="author-member-openid")


class FakeEvent:
    def __init__(self, module, text):
        self._module = module
        self._text = text
        self.unified_msg_origin = "qq_official:group-openid"
        self.message_obj = SimpleNamespace(raw_message=FakeRawMessage(), self_id="qq_official")
        self._messages = [module.Comp.At(qq="qq_official"), module.Comp.Plain(text)]

    def get_platform_name(self):
        return "qq_official"

    def get_message_str(self):
        return self._text

    def get_messages(self):
        return self._messages

    def get_group_id(self):
        return "fallback-group"

    def get_sender_id(self):
        return "fallback-user"

    def get_self_id(self):
        return "qq_official"

    def chain_result(self, chain):
        return SimpleNamespace(chain=chain)

    def plain_result(self, text):
        return SimpleNamespace(chain=[self._module.Comp.Plain(text)])

    def stop_event(self):
        self.stopped = True


FakeEvent.__module__ = "astrbot.core.platform.sources.qqofficial.qqofficial_message_event"
FakeEvent.__name__ = "QQOfficialMessageEvent"


def test_open_room_command_requires_mention_and_uses_openids():
    module = load_plugin_module()
    plugin = object.__new__(module.QQOfficialUtilPlugin)
    event = FakeEvent(module, "开房查找")

    assert plugin._extract_open_room_command_text(event) == "开房查找"
    assert plugin._open_room_group_and_user(event) == ("group-openid", "author-member-openid")

    event._messages = [module.Comp.Plain("开房查找")]
    assert plugin._extract_open_room_command_text(event) is None


def test_subai_keyboard_uses_command_buttons_with_limits():
    module = load_plugin_module()

    keyboard = module._build_subai_keyboard(kind="menu")
    rows = keyboard["content"]["rows"]
    buttons = [button for row in rows for button in row["buttons"]]

    assert len(rows) <= 5
    assert all(len(row["buttons"]) <= 5 for row in rows)
    assert all(button["action"]["type"] == 2 for button in buttons)
    assert buttons[0]["action"]["data"] == "subai状态"
    assert buttons[1]["action"]["data"] == "subai检查"
    assert buttons[2]["action"]["data"] == "subai榜单 intelligence 10"
    assert buttons[3]["action"]["data"] == "subai模型 [模型名称]"
    assert buttons[-1]["action"]["data"] == "subai榜单 agentic 10"


def test_subai_command_requires_mention_and_accepts_capital_prefix():
    module = load_plugin_module()
    plugin = object.__new__(module.QQOfficialUtilPlugin)
    event = FakeEvent(module, "SubAI榜单 coding 10")

    assert plugin._extract_subai_command_text(event) == "SubAI榜单 coding 10"
    assert plugin._split_subai_action("SubAI榜单 coding 10") == ("榜单", "coding 10")

    event._messages = [module.Comp.Plain("SubAI榜单 coding 10")]
    assert plugin._extract_subai_command_text(event) is None


def test_subai_dispatch_returns_image_path_for_rank():
    module = load_plugin_module()
    plugin = object.__new__(module.QQOfficialUtilPlugin)
    event = FakeEvent(module, "subai榜单 intelligence 10")

    class FakeRuntime:
        async def rank(self, metric, limit):
            assert metric == "intelligence"
            assert limit == "10"
            return SimpleNamespace(text="rank text", image_path="rank.png")

    plugin.subai_runtime = FakeRuntime()

    async def scenario():
        return await plugin._dispatch_subai_command("subai榜单 intelligence 10", event)

    assert _run(scenario()) == ("rank text", "rank", "rank.png")


def test_subai_dispatch_model_detail():
    module = load_plugin_module()
    plugin = object.__new__(module.QQOfficialUtilPlugin)
    event = FakeEvent(module, "subai模型 Gemini 2.5 Pro")

    class FakeRuntime:
        async def model_detail(self, query):
            assert query == "Gemini 2.5 Pro"
            return "model detail"

    plugin.subai_runtime = FakeRuntime()

    async def scenario():
        return await plugin._dispatch_subai_command("subai模型 Gemini 2.5 Pro", event)

    assert _run(scenario()) == ("model detail", "rank", None)


def test_subai_image_reply_uses_component_list():
    module = load_plugin_module()
    plugin = object.__new__(module.QQOfficialUtilPlugin)
    event = FakeEvent(module, "subai榜单 intelligence 10")

    class FakeRuntime:
        async def rank(self, metric, limit):
            return SimpleNamespace(text="rank text", image_path="rank.png")

    plugin.subai_runtime = FakeRuntime()

    async def scenario():
        results = []
        async for result in plugin._handle_subai(event):
            results.append(result)
        return results

    results = _run(scenario())

    assert len(results) == 1
    assert isinstance(results[0].chain, list)
    assert len(results[0].chain) == 1
