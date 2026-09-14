from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

EVALUATION_FIELDS = ("intelligence", "coding", "agentic")
PRICING_FIELDS = ("input", "output", "cache_hit", "cache_write")
PERFORMANCE_FIELDS = ("output_tps", "ttft", "first_answer", "end_to_end")


def _nested_get(payload: dict[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _coerce_float(value: Any) -> float | None:
    if value in (None, "", "null"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _metric_from_payload(payload: dict[str, Any], field: str) -> float | None:
    aliases = (
        (field,),
        (f"{field}_index",),
        (f"artificial_analysis_{field}_index",),
        ("evaluations", field),
        ("evaluations", f"{field}_index"),
        ("evaluations", f"artificial_analysis_{field}_index"),
    )
    for alias in aliases:
        value = _nested_get(payload, *alias)
        score = _coerce_float(value)
        if score is not None:
            return score
    return None


def _bundle_from_payload(
    payload: dict[str, Any],
    bundle_name: str,
    aliases: dict[str, tuple[tuple[str, ...], ...]],
) -> dict[str, float | None]:
    bundle: dict[str, float | None] = {}
    for key, paths in aliases.items():
        score = None
        for path in paths:
            value = _nested_get(payload, *path)
            score = _coerce_float(value)
            if score is not None:
                break
        bundle[key] = score
    return bundle


PRICING_ALIASES: dict[str, tuple[tuple[str, ...], ...]] = {
    "input": (
        ("pricing", "price_1m_input_tokens"),
        ("pricing", "input"),
        ("price_1m_input_tokens",),
        ("input_price",),
    ),
    "output": (
        ("pricing", "price_1m_output_tokens"),
        ("pricing", "output"),
        ("price_1m_output_tokens",),
        ("output_price",),
    ),
    "cache_hit": (
        ("pricing", "price_1m_cache_hit_tokens"),
        ("pricing", "cache_hit"),
        ("price_1m_cache_hit_tokens",),
        ("cache_hit_price",),
        ("cache_read_price",),
    ),
    "cache_write": (
        ("pricing", "price_1m_cache_write_tokens"),
        ("pricing", "cache_write"),
        ("price_1m_cache_write_tokens",),
        ("cache_write_price",),
    ),
}


PERFORMANCE_ALIASES: dict[str, tuple[tuple[str, ...], ...]] = {
    "output_tps": (
        ("performance", "median_output_tokens_per_second"),
        ("performance", "output_tokens_per_second"),
        ("performance", "throughput"),
        ("median_output_tokens_per_second",),
        ("output_tokens_per_second",),
        ("throughput",),
    ),
    "ttft": (
        ("performance", "median_time_to_first_token_seconds"),
        ("performance", "time_to_first_token_seconds"),
        ("performance", "time_to_first_token"),
        ("median_time_to_first_token_seconds",),
        ("time_to_first_token_seconds",),
        ("time_to_first_token",),
    ),
    "first_answer": (
        ("performance", "median_time_to_first_answer_token_seconds"),
        ("performance", "first_answer"),
        ("median_time_to_first_answer_token_seconds",),
        ("first_answer",),
    ),
    "end_to_end": (
        ("performance", "median_end_to_end_response_time_seconds"),
        ("performance", "end_to_end"),
        ("median_end_to_end_response_time_seconds",),
        ("end_to_end",),
        ("latency",),
        ("latency_ms",),
    ),
}


@dataclass(frozen=True)
class ModelRanks:
    intelligence: int | None = None
    coding: int | None = None
    agentic: int | None = None


@dataclass(frozen=True)
class ModelSnapshot:
    model_id: str
    name: str
    slug: str
    creator_id: str
    creator: str
    release_date: str
    intelligence: float | None
    coding: float | None
    agentic: float | None
    pricing: dict[str, float | None] = field(default_factory=dict)
    performance: dict[str, float | None] = field(default_factory=dict)
    ranks: ModelRanks = field(default_factory=ModelRanks)
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> ModelSnapshot:
        model_id = _coerce_text(
            payload.get("id") or payload.get("uuid") or payload.get("model_id")
        )
        if not model_id:
            raise ValueError("模型缺少 id/uuid")
        name = _coerce_text(payload.get("name") or payload.get("model_name") or model_id)
        slug = _coerce_text(payload.get("slug") or payload.get("model_slug") or model_id)
        creator_payload = payload.get("model_creator")
        if not isinstance(creator_payload, dict):
            creator_payload = {}
        creator_id = _coerce_text(
            creator_payload.get("id") or payload.get("creator_id") or payload.get("provider_id")
        )
        creator = _coerce_text(
            creator_payload.get("name") or payload.get("creator") or payload.get("provider")
        )
        release_date = _coerce_text(
            payload.get("release_date") or payload.get("releaseDate")
        )
        return cls(
            model_id=model_id,
            name=name,
            slug=slug,
            creator_id=creator_id,
            creator=creator,
            release_date=release_date,
            intelligence=_metric_from_payload(payload, "intelligence"),
            coding=_metric_from_payload(payload, "coding"),
            agentic=_metric_from_payload(payload, "agentic"),
            pricing=_bundle_from_payload(payload, "pricing", PRICING_ALIASES),
            performance=_bundle_from_payload(payload, "performance", PERFORMANCE_ALIASES),
            raw=dict(payload),
        )

    def above_threshold(self, threshold: float) -> bool:
        return self.intelligence is not None and self.intelligence >= threshold

    def with_ranks(self, *, intelligence: int | None, coding: int | None, agentic: int | None) -> ModelSnapshot:
        return ModelSnapshot(
            model_id=self.model_id,
            name=self.name,
            slug=self.slug,
            creator_id=self.creator_id,
            creator=self.creator,
            release_date=self.release_date,
            intelligence=self.intelligence,
            coding=self.coding,
            agentic=self.agentic,
            pricing=dict(self.pricing),
            performance=dict(self.performance),
            ranks=ModelRanks(intelligence=intelligence, coding=coding, agentic=agentic),
            raw=dict(self.raw),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["id"] = payload.pop("model_id")
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ModelSnapshot:
        ranks_payload = payload.get("ranks") or {}
        return cls(
            model_id=str(payload.get("id") or payload.get("model_id") or ""),
            name=str(payload.get("name") or ""),
            slug=str(payload.get("slug") or ""),
            creator_id=str(payload.get("creator_id") or ""),
            creator=str(payload.get("creator") or ""),
            release_date=str(payload.get("release_date") or ""),
            intelligence=_coerce_float(payload.get("intelligence")),
            coding=_coerce_float(payload.get("coding")),
            agentic=_coerce_float(payload.get("agentic")),
            pricing=dict(payload.get("pricing") or {}),
            performance=dict(payload.get("performance") or {}),
            ranks=ModelRanks(
                intelligence=ranks_payload.get("intelligence"),
                coding=ranks_payload.get("coding"),
                agentic=ranks_payload.get("agentic"),
            ),
            raw=dict(payload.get("raw") or {}),
        )


@dataclass(frozen=True)
class ModelChange:
    event_type: str
    transition: str
    model: ModelSnapshot
    previous_model: ModelSnapshot | None
    changed_fields: list[str]
    index_version: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "transition": self.transition,
            "model": self.model.to_dict(),
            "previous_model": self.previous_model.to_dict() if self.previous_model else None,
            "changed_fields": list(self.changed_fields),
            "index_version": self.index_version,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ModelChange:
        previous_model = payload.get("previous_model")
        return cls(
            event_type=str(payload.get("event_type") or ""),
            transition=str(payload.get("transition") or ""),
            model=ModelSnapshot.from_dict(payload.get("model") or {}),
            previous_model=ModelSnapshot.from_dict(previous_model) if previous_model else None,
            changed_fields=list(payload.get("changed_fields") or []),
            index_version=str(payload.get("index_version") or ""),
        )


@dataclass(frozen=True)
class SyncResult:
    baseline_created: bool
    model_count: int
    change_count: int
    delivered_count: int
    failed_delivery_count: int
    message: str


@dataclass(frozen=True)
class RenderedMessage:
    text: str
    image_path: str | None = None
