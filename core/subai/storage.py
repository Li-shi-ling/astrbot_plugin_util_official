from __future__ import annotations

import asyncio
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import ModelChange, ModelSnapshot


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class PersistedBatch:
    batch_id: int | None
    sync_id: int
    session_ids: list[str]


class SubAIStorage:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)

    async def initialize(self) -> None:
        await asyncio.to_thread(self._initialize_sync)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize_sync(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS subscriptions (
                    session_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sync_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS snapshot_meta (
                    snapshot_name TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    model_count INTEGER NOT NULL,
                    snapshot_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS current_models (
                    model_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    slug TEXT NOT NULL,
                    creator TEXT NOT NULL,
                    release_date TEXT NOT NULL,
                    intelligence_score REAL,
                    coding_score REAL,
                    agentic_score REAL,
                    intelligence_rank INTEGER,
                    coding_rank INTEGER,
                    agentic_rank INTEGER,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sync_runs (
                    sync_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trigger_source TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    model_count INTEGER NOT NULL,
                    page_count INTEGER NOT NULL DEFAULT 0,
                    index_version TEXT,
                    rate_limit_limit INTEGER,
                    rate_limit_remaining INTEGER,
                    rate_limit_reset TEXT,
                    error_message TEXT
                );
                CREATE TABLE IF NOT EXISTS change_batches (
                    batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sync_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    trigger_source TEXT NOT NULL,
                    event_count INTEGER NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS delivery_status (
                    batch_id INTEGER NOT NULL,
                    session_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (batch_id, session_id)
                );
                """
            )
            self._ensure_column(conn, "sync_runs", "page_count", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "sync_runs", "index_version", "TEXT")
            self._ensure_column(conn, "sync_runs", "rate_limit_limit", "INTEGER")
            self._ensure_column(conn, "sync_runs", "rate_limit_remaining", "INTEGER")
            self._ensure_column(conn, "sync_runs", "rate_limit_reset", "TEXT")
            conn.commit()

    def _ensure_column(self, conn: sqlite3.Connection, table_name: str, column_name: str, definition: str) -> None:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        existing = {str(row["name"]) for row in rows}
        if column_name in existing:
            return
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")

    async def add_subscription(self, session_id: str) -> bool:
        return await asyncio.to_thread(self._add_subscription_sync, session_id)

    def _add_subscription_sync(self, session_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO subscriptions(session_id, created_at) VALUES(?, ?)",
                (session_id, utc_now_iso()),
            )
            conn.commit()
            return cursor.rowcount > 0

    async def remove_subscription(self, session_id: str) -> bool:
        return await asyncio.to_thread(self._remove_subscription_sync, session_id)

    def _remove_subscription_sync(self, session_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM subscriptions WHERE session_id = ?", (session_id,))
            conn.commit()
            return cursor.rowcount > 0

    async def list_subscriptions(self) -> list[str]:
        return await asyncio.to_thread(self._list_subscriptions_sync)

    def _list_subscriptions_sync(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT session_id FROM subscriptions ORDER BY session_id").fetchall()
        return [str(row["session_id"]) for row in rows]

    async def get_snapshot(self, snapshot_name: str) -> list[ModelSnapshot]:
        return await asyncio.to_thread(self._get_snapshot_sync, snapshot_name)

    def _get_snapshot_sync(self, snapshot_name: str) -> list[ModelSnapshot]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT snapshot_json FROM snapshot_meta WHERE snapshot_name = ?",
                (snapshot_name,),
            ).fetchone()
        if row is None:
            return []
        payload = json.loads(row["snapshot_json"])
        return [ModelSnapshot.from_dict(item) for item in payload]

    async def get_last_success_summary(self) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._get_last_success_summary_sync)

    def _get_last_success_summary_sync(self) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT completed_at, model_count, page_count, index_version,
                       rate_limit_limit, rate_limit_remaining, rate_limit_reset
                FROM sync_runs
                WHERE status = 'success'
                ORDER BY sync_id DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            return None
        return {
            "completed_at": row["completed_at"],
            "model_count": int(row["model_count"]),
            "page_count": int(row["page_count"] or 0),
            "index_version": row["index_version"],
            "rate_limit_limit": row["rate_limit_limit"],
            "rate_limit_remaining": row["rate_limit_remaining"],
            "rate_limit_reset": row["rate_limit_reset"],
        }

    async def get_manual_check_cooldown_remaining(self, cooldown_minutes: int) -> int:
        return await asyncio.to_thread(self._get_manual_check_cooldown_remaining_sync, cooldown_minutes)

    def _get_manual_check_cooldown_remaining_sync(self, cooldown_minutes: int) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM sync_state WHERE key = 'manual_check_last_at'"
            ).fetchone()
        if row is None:
            return 0
        last_check = datetime.fromisoformat(str(row["value"]))
        elapsed = (datetime.now(timezone.utc) - last_check).total_seconds()
        remaining = cooldown_minutes * 60 - int(elapsed)
        return max(0, remaining)

    async def save_failed_sync(self, trigger_source: str, error_message: str) -> None:
        await asyncio.to_thread(self._save_failed_sync_sync, trigger_source, error_message)

    def _save_failed_sync_sync(self, trigger_source: str, error_message: str) -> None:
        now = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sync_runs(
                    trigger_source, started_at, completed_at, status, model_count,
                    page_count, index_version, rate_limit_limit, rate_limit_remaining,
                    rate_limit_reset, error_message
                )
                VALUES(?, ?, ?, 'failed', 0, 0, NULL, NULL, NULL, NULL, ?)
                """,
                (trigger_source, now, now, error_message),
            )
            conn.commit()

    async def save_successful_sync(
        self,
        *,
        trigger_source: str,
        models: list[ModelSnapshot],
        changes: list[ModelChange],
        update_manual_check_at: bool,
        page_count: int,
        index_version: str,
        rate_limit_limit: int | None,
        rate_limit_remaining: int | None,
        rate_limit_reset: str | None,
    ) -> PersistedBatch:
        return await asyncio.to_thread(
            self._save_successful_sync_sync,
            trigger_source,
            models,
            changes,
            update_manual_check_at,
            page_count,
            index_version,
            rate_limit_limit,
            rate_limit_remaining,
            rate_limit_reset,
        )

    def _save_successful_sync_sync(
        self,
        trigger_source: str,
        models: list[ModelSnapshot],
        changes: list[ModelChange],
        update_manual_check_at: bool,
        page_count: int,
        index_version: str,
        rate_limit_limit: int | None,
        rate_limit_remaining: int | None,
        rate_limit_reset: str | None,
    ) -> PersistedBatch:
        now = utc_now_iso()
        snapshot_json = json.dumps([model.to_dict() for model in models], ensure_ascii=False)
        sessions: list[str] = []
        with self._connect() as conn:
            try:
                conn.execute("BEGIN")
                cursor = conn.execute(
                    """
                    INSERT INTO sync_runs(
                        trigger_source, started_at, completed_at, status, model_count,
                        page_count, index_version, rate_limit_limit, rate_limit_remaining,
                        rate_limit_reset, error_message
                    )
                    VALUES(?, ?, ?, 'success', ?, ?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        trigger_source,
                        now,
                        now,
                        len(models),
                        page_count,
                        index_version,
                        rate_limit_limit,
                        rate_limit_remaining,
                        rate_limit_reset,
                    ),
                )
                sync_id = int(cursor.lastrowid)
                conn.execute("DELETE FROM current_models")
                conn.executemany(
                    """
                    INSERT INTO current_models(
                        model_id, name, slug, creator, release_date,
                        intelligence_score, coding_score, agentic_score,
                        intelligence_rank, coding_rank, agentic_rank, payload_json
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            model.model_id,
                            model.name,
                            model.slug,
                            model.creator,
                            model.release_date,
                            model.intelligence,
                            model.coding,
                            model.agentic,
                            model.ranks.intelligence,
                            model.ranks.coding,
                            model.ranks.agentic,
                            json.dumps(model.to_dict(), ensure_ascii=False),
                        )
                        for model in models
                    ],
                )
                conn.execute(
                    """
                    INSERT INTO snapshot_meta(snapshot_name, created_at, model_count, snapshot_json)
                    VALUES('current', ?, ?, ?)
                    ON CONFLICT(snapshot_name) DO UPDATE SET
                        created_at=excluded.created_at,
                        model_count=excluded.model_count,
                        snapshot_json=excluded.snapshot_json
                    """,
                    (now, len(models), snapshot_json),
                )
                conn.execute(
                    """
                    INSERT INTO snapshot_meta(snapshot_name, created_at, model_count, snapshot_json)
                    VALUES('baseline', ?, ?, ?)
                    ON CONFLICT(snapshot_name) DO UPDATE SET
                        created_at=excluded.created_at,
                        model_count=excluded.model_count,
                        snapshot_json=excluded.snapshot_json
                    """,
                    (now, len(models), snapshot_json),
                )
                if update_manual_check_at:
                    conn.execute(
                        """
                        INSERT INTO sync_state(key, value) VALUES('manual_check_last_at', ?)
                        ON CONFLICT(key) DO UPDATE SET value=excluded.value
                        """,
                        (now,),
                    )
                sessions = [
                    str(row["session_id"])
                    for row in conn.execute(
                        "SELECT session_id FROM subscriptions ORDER BY session_id"
                    ).fetchall()
                ]
                batch_id: int | None = None
                if changes and sessions:
                    batch_cursor = conn.execute(
                        """
                        INSERT INTO change_batches(sync_id, created_at, trigger_source, event_count, payload_json)
                        VALUES(?, ?, ?, ?, ?)
                        """,
                        (
                            sync_id,
                            now,
                            trigger_source,
                            len(changes),
                            json.dumps([change.to_dict() for change in changes], ensure_ascii=False),
                        ),
                    )
                    batch_id = int(batch_cursor.lastrowid)
                    conn.executemany(
                        """
                        INSERT INTO delivery_status(batch_id, session_id, status, error_message, updated_at)
                        VALUES(?, ?, 'pending', NULL, ?)
                        """,
                        [(batch_id, session_id, now) for session_id in sessions],
                    )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return PersistedBatch(batch_id=batch_id, sync_id=sync_id, session_ids=sessions)

    async def list_ranked_models(self, metric: str, limit: int) -> list[ModelSnapshot]:
        return await asyncio.to_thread(self._list_ranked_models_sync, metric, limit)

    async def list_current_models(self) -> list[ModelSnapshot]:
        return await asyncio.to_thread(self._list_current_models_sync)

    def _list_current_models_sync(self) -> list[ModelSnapshot]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload_json FROM current_models
                ORDER BY name ASC, slug ASC
                """
            ).fetchall()
        return [ModelSnapshot.from_dict(json.loads(row["payload_json"])) for row in rows]

    def _list_ranked_models_sync(self, metric: str, limit: int) -> list[ModelSnapshot]:
        rank_column = {
            "intelligence": "intelligence_rank",
            "coding": "coding_rank",
            "agentic": "agentic_rank",
        }[metric]
        score_column = {
            "intelligence": "intelligence_score",
            "coding": "coding_score",
            "agentic": "agentic_score",
        }[metric]
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT payload_json FROM current_models
                WHERE {score_column} IS NOT NULL
                ORDER BY {rank_column} ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [ModelSnapshot.from_dict(json.loads(row["payload_json"])) for row in rows]

    async def count_watched_models(self, threshold: float) -> int:
        return await asyncio.to_thread(self._count_watched_models_sync, threshold)

    def _count_watched_models_sync(self, threshold: float) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(1) AS count_value
                FROM current_models
                WHERE intelligence_score IS NOT NULL AND intelligence_score >= ?
                """,
                (threshold,),
            ).fetchone()
        return int(row["count_value"] if row is not None else 0)

    async def load_pending_batches(self) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._load_pending_batches_sync)

    def _load_pending_batches_sync(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT cb.batch_id, cb.payload_json
                FROM change_batches cb
                JOIN delivery_status ds ON ds.batch_id = cb.batch_id
                WHERE ds.status IN ('pending', 'failed')
                ORDER BY cb.batch_id ASC
                """
            ).fetchall()
            payloads: list[dict[str, Any]] = []
            for row in rows:
                targets = conn.execute(
                    """
                    SELECT session_id, status, error_message
                    FROM delivery_status
                    WHERE batch_id = ? AND status IN ('pending', 'failed')
                    ORDER BY session_id
                    """,
                    (row["batch_id"],),
                ).fetchall()
                payloads.append(
                    {
                        "batch_id": int(row["batch_id"]),
                        "changes": [ModelChange.from_dict(item) for item in json.loads(row["payload_json"])],
                        "targets": [
                            {
                                "session_id": str(target["session_id"]),
                                "status": str(target["status"]),
                                "error_message": target["error_message"],
                            }
                            for target in targets
                        ],
                    }
                )
        return payloads

    async def mark_delivery(self, batch_id: int, session_id: str, status: str, error_message: str | None = None) -> None:
        await asyncio.to_thread(self._mark_delivery_sync, batch_id, session_id, status, error_message)

    def _mark_delivery_sync(self, batch_id: int, session_id: str, status: str, error_message: str | None) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE delivery_status
                SET status = ?, error_message = ?, updated_at = ?
                WHERE batch_id = ? AND session_id = ?
                """,
                (status, error_message, utc_now_iso(), batch_id, session_id),
            )
            conn.commit()
