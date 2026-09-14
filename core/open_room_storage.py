"""Persistent, group-scoped storage for open-room entries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import aiosqlite

from .open_room_parser import make_search_text, parse_search_query

SHORT_ENTRY_LIFETIME = timedelta(hours=24)


@dataclass(frozen=True)
class OpenRoomEntry:
    code: str
    group_id: str
    owner_id: str
    locator_text: str
    game_or_platform: str
    note: str
    initial_count: int
    max_count: int | None
    is_long_term: bool
    created_at: datetime
    expires_at: datetime | None
    joined_count: int

    @property
    def current_count(self) -> int:
        return self.initial_count + self.joined_count

    @property
    def is_full(self) -> bool:
        return self.max_count is not None and self.current_count >= self.max_count


class OpenRoomStore:
    def __init__(self, database_path: Path):
        self.database_path = database_path

    async def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        async with self._connect() as db:
            await db.execute("PRAGMA foreign_keys = ON")
            await db.execute("PRAGMA journal_mode = WAL")
            await db.executescript(
                """
                CREATE TABLE IF NOT EXISTS open_room_group_sequences (
                    group_id TEXT PRIMARY KEY,
                    next_value INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS open_room_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    code TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    locator_text TEXT NOT NULL,
                    game_or_platform TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    search_text TEXT NOT NULL DEFAULT '',
                    initial_count INTEGER NOT NULL,
                    max_count INTEGER,
                    is_long_term INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    UNIQUE(group_id, code),
                    CHECK(initial_count >= 0),
                    CHECK(max_count IS NULL OR max_count > 0),
                    CHECK(max_count IS NULL OR initial_count <= max_count)
                );

                CREATE TABLE IF NOT EXISTS open_room_signups (
                    entry_id INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    joined_at TEXT NOT NULL,
                    PRIMARY KEY(entry_id, user_id),
                    FOREIGN KEY(entry_id) REFERENCES open_room_entries(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_open_room_entries_group_expiry
                    ON open_room_entries(group_id, expires_at);
                """,
            )
            await db.commit()

    async def create_entry(
        self,
        *,
        group_id: str,
        owner_id: str,
        locator_text: str,
        game_or_platform: str,
        note: str,
        initial_count: int,
        max_count: int | None,
        is_long_term: bool,
    ) -> OpenRoomEntry:
        now = _now()
        expires_at = None if is_long_term else now + SHORT_ENTRY_LIFETIME
        async with self._connect() as db:
            await db.execute("PRAGMA foreign_keys = ON")
            await db.execute("BEGIN IMMEDIATE")
            try:
                await db.execute(
                    "INSERT OR IGNORE INTO open_room_group_sequences(group_id) VALUES (?)",
                    (group_id,),
                )
                await db.execute(
                    "UPDATE open_room_group_sequences SET next_value = next_value + 1 WHERE group_id = ?",
                    (group_id,),
                )
                cursor = await db.execute(
                    "SELECT next_value FROM open_room_group_sequences WHERE group_id = ?",
                    (group_id,),
                )
                sequence = int((await cursor.fetchone())[0])
                code = _format_code(sequence)
                await db.execute(
                    """
                    INSERT INTO open_room_entries(
                        group_id, sequence, code, owner_id, locator_text,
                        game_or_platform, note, search_text, initial_count, max_count,
                        is_long_term, created_at, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        group_id,
                        sequence,
                        code,
                        owner_id,
                        locator_text,
                        game_or_platform,
                        note,
                        make_search_text(game_or_platform, note),
                        initial_count,
                        max_count,
                        int(is_long_term),
                        _serialize_time(now),
                        _serialize_time(expires_at) if expires_at else None,
                    ),
                )
                await db.commit()
            except Exception:
                await db.rollback()
                raise
        entry = await self.get_entry(group_id, code)
        assert entry is not None
        return entry

    async def find_entries(self, group_id: str, query: str) -> list[OpenRoomEntry]:
        await self.delete_expired()
        groups = parse_search_query(query)
        async with self._connect() as db:
            sql = _entry_select() + " WHERE e.group_id = ?"
            params: list[object] = [group_id]
            for alternatives in groups:
                pieces: list[str] = []
                for term in alternatives:
                    pieces.append("e.search_text LIKE ? ESCAPE '\\'")
                    params.append(f"%{_escape_like(term)}%")
                sql += " AND (" + " OR ".join(pieces) + ")"
            sql += " GROUP BY e.id ORDER BY e.is_long_term ASC, e.created_at DESC"
            cursor = await db.execute(sql, params)
            return [_row_to_entry(row) for row in await cursor.fetchall()]

    async def get_entry(self, group_id: str, code: str) -> OpenRoomEntry | None:
        await self.delete_expired()
        async with self._connect() as db:
            cursor = await db.execute(
                _entry_select() + " WHERE e.group_id = ? AND e.code = ? GROUP BY e.id",
                (group_id, _normalize_code(code)),
            )
            row = await cursor.fetchone()
            return _row_to_entry(row) if row else None

    async def join_entry(self, group_id: str, code: str, user_id: str) -> OpenRoomEntry:
        await self.delete_expired()
        code = _normalize_code(code)
        async with self._connect() as db:
            await db.execute("PRAGMA foreign_keys = ON")
            await db.execute("BEGIN IMMEDIATE")
            try:
                cursor = await db.execute(
                    _entry_select() + " WHERE e.group_id = ? AND e.code = ? GROUP BY e.id",
                    (group_id, code),
                )
                row = await cursor.fetchone()
                if not row:
                    raise ValueError("房间不存在或已过期。")
                entry = _row_to_entry(row)
                if entry.owner_id == user_id:
                    raise ValueError("房主已计入初始人数，不能重复加入。")
                cursor = await db.execute(
                    "SELECT 1 FROM open_room_signups WHERE entry_id = ? AND user_id = ?",
                    (row[0], user_id),
                )
                if await cursor.fetchone():
                    raise ValueError("你已经加入过这个房间。")
                if entry.is_full:
                    raise ValueError("该房间人数已满。")
                await db.execute(
                    "INSERT INTO open_room_signups(entry_id, user_id, joined_at) VALUES (?, ?, ?)",
                    (row[0], user_id, _serialize_time(_now())),
                )
                await db.commit()
            except Exception:
                await db.rollback()
                raise
        updated = await self.get_entry(group_id, code)
        assert updated is not None
        return updated

    async def delete_entry(self, group_id: str, code: str, owner_id: str) -> bool:
        async with self._connect() as db:
            await db.execute("PRAGMA foreign_keys = ON")
            cursor = await db.execute(
                "DELETE FROM open_room_entries WHERE group_id = ? AND code = ? AND owner_id = ?",
                (group_id, _normalize_code(code), owner_id),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def delete_expired(self) -> int:
        now = _serialize_time(_now())
        async with self._connect() as db:
            await db.execute("PRAGMA foreign_keys = ON")
            cursor = await db.execute(
                "DELETE FROM open_room_entries WHERE expires_at IS NOT NULL AND expires_at <= ?",
                (now,),
            )
            await db.commit()
            return cursor.rowcount

    def _connect(self) -> aiosqlite.Connection:
        return aiosqlite.connect(self.database_path)


def _entry_select() -> str:
    return """
        SELECT e.id, e.code, e.group_id, e.owner_id, e.locator_text,
               e.game_or_platform, e.note, e.initial_count, e.max_count,
               e.is_long_term, e.created_at, e.expires_at,
               COUNT(s.user_id) AS joined_count
        FROM open_room_entries e
        LEFT JOIN open_room_signups s ON s.entry_id = e.id
    """


def _row_to_entry(row: aiosqlite.Row | tuple) -> OpenRoomEntry:
    return OpenRoomEntry(
        code=row[1],
        group_id=row[2],
        owner_id=row[3],
        locator_text=row[4],
        game_or_platform=row[5],
        note=row[6],
        initial_count=int(row[7]),
        max_count=int(row[8]) if row[8] is not None else None,
        is_long_term=bool(row[9]),
        created_at=_parse_time(row[10]),
        expires_at=_parse_time(row[11]) if row[11] else None,
        joined_count=int(row[12]),
    )


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _normalize_code(code: str) -> str:
    return code.strip().lstrip("#").upper()


def _format_code(sequence: int) -> str:
    return f"RM{sequence:04d}"


def _now() -> datetime:
    return datetime.now(UTC)


def _serialize_time(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value)
