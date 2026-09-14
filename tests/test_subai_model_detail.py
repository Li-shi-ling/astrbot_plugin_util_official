from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from core.subai.models import ModelRanks, ModelSnapshot
from core.subai.runtime import SubAIRuntime


def _run(coro):
    return asyncio.run(coro)


def _model(
    name: str,
    slug: str,
    *,
    intelligence: float | None = None,
    coding: float | None = None,
    agentic: float | None = None,
) -> ModelSnapshot:
    return ModelSnapshot(
        model_id=f"id-{slug}",
        name=name,
        slug=slug,
        creator_id="creator",
        creator="Google",
        release_date="2026-01-01",
        intelligence=intelligence,
        coding=coding,
        agentic=agentic,
        pricing={"input": 0.1, "output": 0.2, "cache_hit": None, "cache_write": None},
        performance={"output_tps": 100.0, "ttft": 0.5, "first_answer": 1.2, "end_to_end": 3.4},
        ranks=ModelRanks(intelligence=1, coding=2, agentic=3),
    )


class FakeStorage:
    def __init__(self, models):
        self.models = models

    async def list_current_models(self):
        return self.models

    async def get_last_success_summary(self):
        return {"index_version": "2026-09-05"}


def test_subai_model_detail_returns_best_fuzzy_match():
    runtime = object.__new__(SubAIRuntime)
    runtime.storage = FakeStorage(
        [
            _model("Gemini 2.5 Flash", "gemini-2-5-flash", intelligence=44.0),
            _model("Gemini 2.5 Pro", "gemini-2-5-pro", intelligence=50.0),
        ]
    )

    result = _run(runtime.model_detail("gemini pro"))

    assert "SubAI 模型详情：Gemini 2.5 Pro" in result
    assert "匹配：" in result
    assert "评分：Intelligence 50.0" in result


def test_subai_model_detail_rejects_low_score_match():
    runtime = object.__new__(SubAIRuntime)
    runtime.storage = FakeStorage([_model("Gemini 2.5 Pro", "gemini-2-5-pro")])

    result = _run(runtime.model_detail("totally unrelated"))

    assert "没有找到足够接近" in result
    assert "需要不低于 0.60" in result


def test_subai_model_detail_rejects_placeholder():
    runtime = object.__new__(SubAIRuntime)
    runtime.storage = SimpleNamespace()

    result = _run(runtime.model_detail("[模型名称]"))

    assert "请把按钮里的 [模型名称] 替换" in result
