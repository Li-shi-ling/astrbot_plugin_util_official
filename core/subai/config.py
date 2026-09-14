from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

MANUAL_CHECK_COOLDOWN_MINUTES = 30


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class SubAIConfig:
    api_key: str
    poll_interval_minutes: int
    intelligence_threshold: float
    request_timeout_seconds: int
    max_retries: int
    card_theme: str

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key)

    @classmethod
    def from_mapping(cls, config: Mapping[str, Any] | None) -> SubAIConfig:
        source = config or {}
        api_key = str(source.get("api_key", "") or "").strip()
        poll_interval_minutes = max(15, _to_int(source.get("poll_interval_minutes", 120), 120))
        request_timeout_seconds = min(
            120,
            max(5, _to_int(source.get("request_timeout_seconds", 20), 20)),
        )
        max_retries = min(5, max(0, _to_int(source.get("max_retries", 2), 2)))
        intelligence_threshold = min(
            100.0,
            max(0.0, _to_float(source.get("intelligence_threshold", 47.0), 47.0)),
        )
        card_theme = str(source.get("card_theme", "analytics") or "analytics").strip().lower()
        if card_theme not in {"analytics", "brutalist", "paper"}:
            card_theme = "analytics"
        return cls(
            api_key=api_key,
            poll_interval_minutes=poll_interval_minutes,
            intelligence_threshold=intelligence_threshold,
            request_timeout_seconds=request_timeout_seconds,
            max_retries=max_retries,
            card_theme=card_theme,
        )

    def missing_api_key_message(self) -> str:
        return "SubAI 未配置 Artificial Analysis API Key，已跳过自动轮询。管理员可在插件配置中填写 `api_key` 后重载插件。"
