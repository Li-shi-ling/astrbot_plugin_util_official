from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PLUGIN_ROOT / "main.py"


def load_plugin_module():
    spec = importlib.util.spec_from_file_location("qqofficial_util_main_roulette", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeMessageObj:
    self_id = "qq_official"

    def __init__(self, raw_message):
        self.raw_message = raw_message
        self.message_id = "wrapped-mid"


class FakeEvent:
    def __init__(self, module, text=None, raw_message=None, platform="qq_official"):
        self._module = module
        self._text = text or f"{module.ROULETTE_COMMAND_PREFIX}\u72b6\u6001"
        self._platform = platform
        self._messages = [module.Comp.At(qq="qq_official"), module.Comp.Plain(self._text)]
        self.message_obj = FakeMessageObj(raw_message or FakeRawMessage())

    def get_platform_name(self):
        return self._platform

    def get_messages(self):
        return self._messages

    def get_message_str(self):
        return self._text

    def get_group_id(self):
        return "fallback-group"

    def get_sender_id(self):
        return "fallback-user"

    def get_self_id(self):
        return "qq_official"


class FakeRawMessage:
    def __init__(self):
        self.group_openid = "group-openid"
        self.author = SimpleNamespace(
            member_openid="member-openid",
            user_openid="user-openid",
        )
        self.id = "raw-mid"
        self.msg_seq = 12


def make_started_game(module, count=10):
    game = module.RouletteGame(group_openid="group-openid", owner_id="u1")
    for index in range(1, count + 1):
        game.add_player(f"u{index}", f"玩家{index}")
    game.start("u1")
    return game


def test_roulette_keyboard_uses_command_buttons_with_limits():
    module = load_plugin_module()
    game = make_started_game(module, count=10)
    game.current_player().items = [
        module.ITEM_BEER,
        module.ITEM_CIGARETTE,
        module.ITEM_SAW,
        module.ITEM_INVERTER,
    ]

    keyboard = module._build_roulette_keyboard(game)
    rows = keyboard["content"]["rows"]
    buttons = [button for row in rows for button in row["buttons"]]

    assert len(rows) <= 5
    assert all(len(row["buttons"]) <= 5 for row in rows)
    assert len(buttons) <= 25
    assert all(button["action"]["type"] == 2 for button in buttons)
    assert rows[0]["buttons"][0]["action"]["data"] == "轮盘开枪 自己"
    assert rows[1]["buttons"][0]["action"]["data"] == "轮盘开枪 2"
    assert not any(button["action"]["data"] == "轮盘开枪 1" for button in buttons)
    assert any(button["action"]["data"] == "轮盘道具 啤酒" for button in buttons)


def test_roulette_keyboard_waiting_room_join_leave_start():
    module = load_plugin_module()
    game = module.RouletteGame(group_openid="group-openid", owner_id="u1")
    game.add_player("u1", "\u73a9\u5bb61")

    keyboard = module._build_roulette_keyboard(game)
    buttons = [button for row in keyboard["content"]["rows"] for button in row["buttons"]]

    assert [button["action"]["data"] for button in buttons] == [
        "轮盘加入",
        "轮盘退出",
        "轮盘开始",
    ]
    assert [button["render_data"]["label"] for button in buttons] == [
        "加入",
        "退出",
        "开始",
    ]
    assert not any(button["id"].startswith("roulette_item_") for button in buttons)
    assert not any(button["action"]["data"] == "轮盘状态" for button in buttons)


def test_roulette_keyboard_only_shows_owned_item_buttons():
    module = load_plugin_module()
    game = make_started_game(module, count=2)
    game.current_player().items = [module.ITEM_BEER]

    keyboard = module._build_roulette_keyboard(game)
    item_buttons = [
        button
        for row in keyboard["content"]["rows"]
        for button in row["buttons"]
        if button["id"].startswith("roulette_item_")
    ]

    assert [button["action"]["data"] for button in item_buttons] == ["轮盘道具 啤酒"]


def test_roulette_payload_requires_non_empty_markdown():
    module = load_plugin_module()

    payload = module._build_roulette_message_payload("", None, with_keyboard=False)

    assert payload["msg_type"] == 2
    assert payload["markdown"]["content"] == "轮盘"
    assert payload["keyboard"] is None


def test_roulette_payload_formats_text_as_markdown():
    module = load_plugin_module()
    text = "\u6076\u9b54\u8f6e\u76d8\u72b6\u6001\n\u5f53\u524d\u5f39\u961f\u5217\uff1a\u5b9e\u5f39 1 / \u7a7a\u5f39 2\n1. Alice | \u5b58\u6d3b"

    payload = module._build_roulette_message_payload(text, None, with_keyboard=False)
    content = payload["markdown"]["content"]

    assert content.startswith("## ")
    assert "**\u5f53\u524d\u5f39\u961f\u5217**" in content
    assert "- `1` Alice" in content


def test_roulette_settings_keyboard_uses_placeholders_and_target_state():
    module = load_plugin_module()
    settings = module.RouletteSettings(random_shell_count=False, random_hp=True)

    keyboard = module._build_roulette_settings_keyboard(settings)
    buttons = [button for row in keyboard["content"]["rows"] for button in row["buttons"]]

    assert any(button["action"]["data"] == "轮盘设置 子弹上限 [数量]" for button in buttons)
    assert any(button["action"]["data"] == "轮盘设置 道具数量 [数量]" for button in buttons)
    assert any(button["render_data"]["label"] == "随机子弹：是" for button in buttons)
    assert any(button["render_data"]["label"] == "随机血量：否" for button in buttons)


def test_roulette_settings_command_works_without_room_and_updates_defaults():
    module = load_plugin_module()
    plugin = object.__new__(module.QQOfficialUtilPlugin)
    plugin.roulette_games = {}
    plugin.roulette_settings = module.RouletteSettings()
    plugin.config = {}
    session_id = "qq_official:group-openid"
    event = FakeEvent(
        module,
        text=f"{module.ROULETTE_COMMAND_PREFIX}\u8bbe\u7f6e \u5b50\u5f39\u4e0a\u9650 6",
    )

    message, returned_game, with_keyboard = __import__("asyncio").run(
        plugin._handle_roulette_command(
            f"{module.ROULETTE_COMMAND_PREFIX}\u8bbe\u7f6e \u5b50\u5f39\u4e0a\u9650 6",
            group_openid="group-openid",
            platform_user_id="member-openid",
            session_id=session_id,
            event=event,
        )
    )

    assert "\u5b50\u5f39\u4e0a\u9650" in message
    assert plugin.roulette_settings.shell_count_max == 6
    assert plugin.config["roulette_settings"]["shell_count_max"] == 6
    assert returned_game is None
    assert with_keyboard is True


def test_roulette_create_copies_public_default_settings():
    module = load_plugin_module()
    plugin = object.__new__(module.QQOfficialUtilPlugin)
    plugin.roulette_games = {}
    plugin.roulette_settings = module.RouletteSettings(shell_count_max=7, hp_max=4)

    class FakeRepo:
        async def resolve_display_name(self, group_openid, platform_user_id):
            return "\u73a9\u5bb6"

    plugin.roulette_user_repo = FakeRepo()
    session_id = "qq_official:group-openid"
    event = FakeEvent(module, text=f"{module.ROULETTE_COMMAND_PREFIX}\u521b\u5efa")

    message, game, with_keyboard = __import__("asyncio").run(
        plugin._handle_roulette_command(
            f"{module.ROULETTE_COMMAND_PREFIX}\u521b\u5efa",
            group_openid="group-openid",
            platform_user_id="member-openid",
            session_id=session_id,
            event=event,
        )
    )

    assert "\u521b\u5efa" in message
    assert game is plugin.roulette_games[session_id]
    assert game.settings.shell_count_max == 7
    assert game.settings.hp_max == 4
    assert game.settings is not plugin.roulette_settings
    assert with_keyboard is True


def test_roulette_command_requires_bot_mention_and_prefix():
    module = load_plugin_module()
    plugin = object.__new__(module.QQOfficialUtilPlugin)
    event = FakeEvent(module, text=f"{module.ROULETTE_COMMAND_PREFIX}\u72b6\u6001")

    assert plugin._extract_roulette_command_text(event) == f"{module.ROULETTE_COMMAND_PREFIX}\u72b6\u6001"

    event._messages = [module.Comp.Plain("轮盘状态")]
    assert plugin._extract_roulette_command_text(event) is None

    event = FakeEvent(module, text="\u76d2 123456789")
    assert plugin._extract_roulette_command_text(event) is None


def test_roulette_identity_prefers_member_openid_and_group_openid():
    module = load_plugin_module()
    plugin = object.__new__(module.QQOfficialUtilPlugin)
    event = FakeEvent(module, raw_message=FakeRawMessage())

    assert plugin._extract_roulette_group_context(event) == (
        "group-openid",
        "member-openid",
    )


def test_roulette_bind_does_not_return_keyboard_when_room_exists():
    module = load_plugin_module()
    plugin = object.__new__(module.QQOfficialUtilPlugin)
    session_id = "qq_official:group-openid"
    game = module.RouletteGame(group_openid="group-openid", owner_id="member-openid")
    game.add_player("member-openid", "\u65e7\u540d")
    plugin.roulette_games = {session_id: game}

    class FakeRepo:
        async def upsert_profile(self, group_openid, platform_user_id, display_name):
            return SimpleNamespace(display_name=display_name)

    plugin.roulette_user_repo = FakeRepo()
    event = FakeEvent(
        module,
        text=f"{module.ROULETTE_COMMAND_PREFIX}\u7ed1\u5b9a \u65b0\u540d",
    )

    message, returned_game, with_keyboard = __import__("asyncio").run(
        plugin._handle_roulette_command(
            f"{module.ROULETTE_COMMAND_PREFIX}\u7ed1\u5b9a \u65b0\u540d",
            group_openid="group-openid",
            platform_user_id="member-openid",
            session_id=session_id,
            event=event,
        )
    )

    assert "\u65b0\u540d" in message
    assert returned_game is game
    assert with_keyboard is False


def test_roulette_profile_commands_are_keyboardless_on_errors():
    module = load_plugin_module()
    plugin = object.__new__(module.QQOfficialUtilPlugin)

    assert plugin._is_roulette_keyboardless_error_command(
        f"{module.ROULETTE_COMMAND_PREFIX}\u7ed1\u5b9a"
    )
    assert plugin._is_roulette_keyboardless_error_command(
        f"{module.ROULETTE_COMMAND_PREFIX}\u6539\u540d \u65b0\u540d"
    )
    assert plugin._is_roulette_keyboardless_error_command(
        f"{module.ROULETTE_COMMAND_PREFIX}\u9000\u51fa"
    )
    assert not plugin._is_roulette_keyboardless_error_command(
        f"{module.ROULETTE_COMMAND_PREFIX}\u52a0\u5165"
    )


def test_roulette_leave_removes_player_from_waiting_room():
    module = load_plugin_module()
    plugin = object.__new__(module.QQOfficialUtilPlugin)
    session_id = "qq_official:group-openid"
    game = module.RouletteGame(group_openid="group-openid", owner_id="u1")
    game.add_player("u1", "\u623f\u4e3b")
    game.add_player("u2", "\u73a9\u5bb62")
    plugin.roulette_games = {session_id: game}
    plugin.roulette_user_repo = SimpleNamespace()
    event = FakeEvent(
        module,
        text=f"{module.ROULETTE_COMMAND_PREFIX}\u9000\u51fa",
    )

    message, returned_game, with_keyboard = __import__("asyncio").run(
        plugin._handle_roulette_command(
            f"{module.ROULETTE_COMMAND_PREFIX}\u9000\u51fa",
            group_openid="group-openid",
            platform_user_id="u2",
            session_id=session_id,
            event=event,
        )
    )

    assert "\u9000\u51fa\u4e86\u623f\u95f4" in message
    assert returned_game is game
    assert with_keyboard is True
    assert [player.user_id for player in game.players] == ["u1"]


def test_non_owner_start_message_has_no_keyboard():
    module = load_plugin_module()
    plugin = object.__new__(module.QQOfficialUtilPlugin)
    session_id = "qq_official:group-openid"
    game = module.RouletteGame(group_openid="group-openid", owner_id="u1")
    game.add_player("u1", "\u623f\u4e3b")
    game.add_player("u2", "\u73a9\u5bb62")
    plugin.roulette_games = {session_id: game}
    plugin.roulette_user_repo = SimpleNamespace()
    event = FakeEvent(
        module,
        text=f"{module.ROULETTE_COMMAND_PREFIX}\u5f00\u59cb",
    )

    message, returned_game, with_keyboard = __import__("asyncio").run(
        plugin._handle_roulette_command(
            f"{module.ROULETTE_COMMAND_PREFIX}\u5f00\u59cb",
            group_openid="group-openid",
            platform_user_id="u2",
            session_id=session_id,
            event=event,
        )
    )

    assert message == "\u53ea\u6709\u623f\u4e3b\u53ef\u4ee5\u5f00\u59cb\u672c\u5c40\u3002"
    assert returned_game is game
    assert with_keyboard is False


def test_leave_after_start_error_has_no_keyboard():
    module = load_plugin_module()
    plugin = object.__new__(module.QQOfficialUtilPlugin)
    session_id = "qq_official:group-openid"
    game = module.RouletteGame(group_openid="group-openid", owner_id="u1")
    game.add_player("u1", "\u623f\u4e3b")
    game.add_player("u2", "\u73a9\u5bb62")
    game.start("u1")
    plugin.roulette_games = {session_id: game}
    plugin.roulette_user_repo = SimpleNamespace()
    event = FakeEvent(
        module,
        text=f"{module.ROULETTE_COMMAND_PREFIX}\u9000\u51fa",
    )

    try:
        __import__("asyncio").run(
            plugin._handle_roulette_command(
                f"{module.ROULETTE_COMMAND_PREFIX}\u9000\u51fa",
                group_openid="group-openid",
                platform_user_id="u2",
                session_id=session_id,
                event=event,
            )
        )
    except module.RouletteGameError as exc:
        message = str(exc)
        with_keyboard = False
    else:
        raise AssertionError("expected RouletteGameError")

    assert message == "\u672c\u5c40\u5df2\u7ecf\u5f00\u59cb\uff0c\u4e0d\u80fd\u9000\u51fa\u623f\u95f4\u3002"
    assert with_keyboard is False


def test_not_joined_action_error_has_no_keyboard():
    module = load_plugin_module()
    plugin = object.__new__(module.QQOfficialUtilPlugin)
    session_id = "qq_official:group-openid"
    game = module.RouletteGame(group_openid="group-openid", owner_id="u1")
    game.add_player("u1", "\u623f\u4e3b")
    game.add_player("u2", "\u73a9\u5bb62")
    game.start("u1")
    plugin.roulette_games = {session_id: game}
    plugin.roulette_user_repo = SimpleNamespace()
    event = FakeEvent(
        module,
        text=f"{module.ROULETTE_COMMAND_PREFIX}\u5f00\u67aa \u81ea\u5df1",
    )

    try:
        __import__("asyncio").run(
            plugin._handle_roulette_command(
                f"{module.ROULETTE_COMMAND_PREFIX}\u5f00\u67aa \u81ea\u5df1",
                group_openid="group-openid",
                platform_user_id="u3",
                session_id=session_id,
                event=event,
            )
        )
    except module.RouletteGameError as exc:
        message = str(exc)
        with_keyboard = False
    else:
        raise AssertionError("expected RouletteGameError")

    assert message == "\u4f60\u8fd8\u6ca1\u6709\u52a0\u5165\u672c\u5c40\u3002"
    assert with_keyboard is False
