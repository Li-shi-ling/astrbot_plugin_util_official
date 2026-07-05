from __future__ import annotations

import pytest
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from core.roulette_game import (
    ITEM_BEER,
    ITEM_CIGARETTE,
    ITEM_INVERTER,
    ITEM_POOL,
    ITEM_SAW,
    MAX_PLAYERS,
    RouletteGame,
    RouletteGameError,
    RouletteSettings,
    SHELL_BLANK,
    SHELL_LIVE,
)


def make_started_game() -> RouletteGame:
    game = RouletteGame(group_openid="group", owner_id="u1")
    game.add_player("u1", "玩家1")
    game.add_player("u2", "玩家2")
    game.start("u1")
    return game


def test_room_limits_and_start_requirements():
    game = RouletteGame(group_openid="group", owner_id="u1")
    game.add_player("u1", "玩家1")

    with pytest.raises(RouletteGameError, match="至少需要 2"):
        game.start("u1")

    for index in range(2, MAX_PLAYERS + 1):
        game.add_player(f"u{index}", f"玩家{index}")

    assert len(game.players) == MAX_PLAYERS
    with pytest.raises(RouletteGameError, match="房间已满"):
        game.add_player("u11", "玩家11")


def test_shooting_self_blank_keeps_turn_and_live_advances_or_ends():
    game = make_started_game()
    game.shell_queue = [SHELL_BLANK, SHELL_LIVE]

    result = game.shoot("u1", "自己")

    assert "空弹" in result.message
    assert game.current_player().user_id == "u1"

    game.next_live_damage = 2
    result = game.shoot("u1", "自己")

    assert result.ended is True
    assert game.players[0].hp == 0
    assert game.phase == "ended"
    assert "玩家2 获胜" in result.message


def test_shooting_other_player_always_advances_turn():
    game = make_started_game()
    game.shell_queue = [SHELL_BLANK, SHELL_LIVE]

    result = game.shoot("u1", "2")

    assert "空弹" in result.message
    assert game.current_player().user_id == "u2"


def test_eliminated_players_are_skipped():
    game = RouletteGame(group_openid="group", owner_id="u1")
    game.add_player("u1", "玩家1")
    game.add_player("u2", "玩家2")
    game.add_player("u3", "玩家3")
    game.start("u1")
    game.players[1].hp = 0
    game.shell_queue = [SHELL_BLANK, SHELL_LIVE]

    game.shoot("u1", "3")

    assert game.current_player().user_id == "u3"


def test_items_mvp_effects():
    game = make_started_game()
    actor = game.current_player()

    actor.items = [ITEM_BEER]
    game.shell_queue = [SHELL_LIVE, SHELL_BLANK]
    result = game.use_item("u1", ITEM_BEER)
    assert "退掉了一发实弹" in result.message
    assert game.shell_queue == [SHELL_BLANK]

    actor.items = [ITEM_CIGARETTE]
    actor.hp = 1
    result = game.use_item("u1", ITEM_CIGARETTE)
    assert actor.hp == 2
    assert "恢复 1 点血" in result.message

    actor.items = [ITEM_SAW]
    result = game.use_item("u1", ITEM_SAW)
    assert game.next_live_damage == 2
    assert "下一发实弹伤害变为 2" in result.message

    actor.items = [ITEM_INVERTER]
    game.shell_queue = [SHELL_LIVE]
    result = game.use_item("u1", ITEM_INVERTER)
    assert "当前弹已反转" in result.message
    assert game.shell_queue[0] == SHELL_BLANK


def test_status_does_not_reveal_current_shell_type():
    game = make_started_game()
    game.shell_queue = [SHELL_LIVE, SHELL_BLANK]

    status = game.format_status()

    assert "实弹 1 / 空弹 1" in status
    assert "实弹\n" not in status
    assert "空弹\n" not in status


def test_handcuffs_are_not_in_item_pool():
    assert "手铐" not in ITEM_POOL


def test_settings_control_shells_items_and_starting_hp():
    game = RouletteGame(
        group_openid="group",
        owner_id="u1",
        settings=RouletteSettings(
            shell_count_max=6,
            shell_count_min=5,
            random_shell_count=False,
            item_count_per_reload=2,
            hp_max=3,
            hp_min=1,
            random_hp=False,
        ),
    )
    game.add_player("u1", "玩家1")
    game.add_player("u2", "玩家2")

    game.start("u1")

    assert len(game.shell_queue) == 6
    assert all(player.hp == 3 and player.max_hp == 3 for player in game.players)
    assert all(len(player.items) == 2 for player in game.players)
