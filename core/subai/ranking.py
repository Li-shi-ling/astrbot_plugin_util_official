from __future__ import annotations

from collections.abc import Iterable

from .models import ModelSnapshot


def _sort_key(model: ModelSnapshot, metric: str) -> tuple[float, str, str, str]:
    score = getattr(model, metric)
    return (
        -(score if score is not None else -1.0),
        model.name.casefold(),
        model.slug.casefold(),
        model.model_id,
    )


def _metric_ranks(models: Iterable[ModelSnapshot], metric: str) -> dict[str, int | None]:
    ranked_models = [model for model in models if getattr(model, metric) is not None]
    ranked_models.sort(key=lambda model: _sort_key(model, metric))
    ranks: dict[str, int | None] = {model.model_id: None for model in models}
    for index, model in enumerate(ranked_models, start=1):
        ranks[model.model_id] = index
    return ranks


def apply_rankings(models: list[ModelSnapshot]) -> list[ModelSnapshot]:
    intelligence_ranks = _metric_ranks(models, "intelligence")
    coding_ranks = _metric_ranks(models, "coding")
    agentic_ranks = _metric_ranks(models, "agentic")
    return [
        model.with_ranks(
            intelligence=intelligence_ranks.get(model.model_id),
            coding=coding_ranks.get(model.model_id),
            agentic=agentic_ranks.get(model.model_id),
        )
        for model in models
    ]


def rank_top(models: list[ModelSnapshot], metric: str, limit: int) -> list[ModelSnapshot]:
    eligible = [model for model in models if getattr(model, metric) is not None]
    eligible.sort(key=lambda model: _sort_key(model, metric))
    return eligible[:limit]
