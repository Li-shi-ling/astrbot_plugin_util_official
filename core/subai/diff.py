from __future__ import annotations

from .models import PERFORMANCE_FIELDS, PRICING_FIELDS, ModelChange, ModelSnapshot

FIELD_LABELS = {
    "name": "名称",
    "slug": "Slug",
    "release_date": "发布日期",
    "creator_id": "厂商 ID",
    "creator": "厂商",
    "intelligence": "Intelligence",
    "coding": "Coding",
    "agentic": "Agentic",
    "pricing.input": "定价-输入",
    "pricing.output": "定价-输出",
    "pricing.cache_hit": "定价-Cache Hit",
    "pricing.cache_write": "定价-Cache Write",
    "performance.output_tps": "性能-输出速度",
    "performance.ttft": "性能-TTFT",
    "performance.first_answer": "性能-首答案",
    "performance.end_to_end": "性能-完整响应",
}


def _changes_for_visible_model(
    previous: ModelSnapshot,
    current: ModelSnapshot,
) -> list[str]:
    changed_fields: list[str] = []
    for field_name in (
        "name",
        "slug",
        "release_date",
        "creator_id",
        "creator",
        "intelligence",
        "coding",
        "agentic",
    ):
        if getattr(previous, field_name) != getattr(current, field_name):
            changed_fields.append(FIELD_LABELS[field_name])
    for key in PRICING_FIELDS:
        if previous.pricing.get(key) != current.pricing.get(key):
            changed_fields.append(FIELD_LABELS[f"pricing.{key}"])
    for key in PERFORMANCE_FIELDS:
        if previous.performance.get(key) != current.performance.get(key):
            changed_fields.append(FIELD_LABELS[f"performance.{key}"])
    return changed_fields


def detect_changes(
    previous_models: list[ModelSnapshot],
    current_models: list[ModelSnapshot],
    threshold: float,
) -> list[ModelChange]:
    previous_by_id = {model.model_id: model for model in previous_models}
    current_by_id = {model.model_id: model for model in current_models}
    changes: list[ModelChange] = []

    for current in current_models:
        previous = previous_by_id.get(current.model_id)
        current_visible = current.above_threshold(threshold)
        previous_visible = bool(previous and previous.above_threshold(threshold))
        if current_visible and not previous_visible:
            transition = "reenter" if previous is not None else "new"
            changes.append(
                ModelChange(
                    event_type="enter",
                    transition=transition,
                    model=current,
                    previous_model=previous,
                    changed_fields=["达到门槛"],
                )
            )
            continue
        if current_visible and previous_visible and previous is not None:
            changed_fields = _changes_for_visible_model(previous, current)
            if changed_fields:
                changes.append(
                    ModelChange(
                        event_type="update",
                        transition="update",
                        model=current,
                        previous_model=previous,
                        changed_fields=changed_fields,
                    )
                )

    for previous in previous_models:
        current = current_by_id.get(previous.model_id)
        if not previous.above_threshold(threshold):
            continue
        if current is None:
            continue
        if current.above_threshold(threshold):
            continue
        changes.append(
            ModelChange(
                event_type="exit",
                transition="exit",
                model=current,
                previous_model=previous,
                changed_fields=["跌破门槛"],
            )
        )

    changes.sort(
        key=lambda item: (
            item.model.ranks.intelligence or 10**9,
            item.model.name.casefold(),
            item.model.slug.casefold(),
            item.model.model_id,
        )
    )
    return changes
