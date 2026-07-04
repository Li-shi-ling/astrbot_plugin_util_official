from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest
from sqlalchemy import text

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from core.roulette_db import RouletteDBManager, RouletteUserRepo, validate_display_name


def test_validate_display_name_rejects_invalid_names():
    assert validate_display_name("  \u73a9\u5bb6A  ") == "\u73a9\u5bb6A"

    for name in (
        "",
        "   ",
        "\u592a" * 13,
        "\u73a9\u5bb6\nA",
        "\x01\u574f\u540d",
        "@\u5168\u4f53\u6210\u5458",
    ):
        with pytest.raises(ValueError):
            validate_display_name(name)


def test_user_profile_db_init_and_repo(tmp_path):
    async def run_case():
        db = RouletteDBManager(tmp_path / "roulette.db")
        await db.init_db()
        repo = RouletteUserRepo(db)

        async with db.get_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table' AND name = 'roulette_user_profile'
                    """
                )
            )
            assert result.scalar_one() == "roulette_user_profile"

        profile = await repo.upsert_profile("group-a", "member-1", "\u963f\u7532")
        assert profile.display_name == "\u963f\u7532"
        assert await repo.resolve_display_name("group-a", "member-1") == "\u963f\u7532"

        with pytest.raises(ValueError):
            await repo.upsert_profile("group-a", "member-2", "\u963f\u7532")

        same_name_other_group = await repo.upsert_profile("group-b", "member-2", "\u963f\u7532")
        assert same_name_other_group.display_name == "\u963f\u7532"

        renamed = await repo.upsert_profile("group-a", "member-1", "\u963f\u4e59")
        assert renamed.display_name == "\u963f\u4e59"
        assert await repo.resolve_display_name("group-a", "unknown-openid") == "玩家_openid"

        await db.close()

    asyncio.run(run_case())
