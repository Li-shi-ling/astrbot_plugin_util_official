from __future__ import annotations

import asyncio
import re
from difflib import SequenceMatcher
from pathlib import Path

from astrbot.api import logger
from astrbot.api.star import StarTools

from .cards import card_theme_label, format_rank_text, render_rank_card
from .client import ArtificialAnalysisClient
from .config import MANUAL_CHECK_COOLDOWN_MINUTES, SubAIConfig
from .models import RenderedMessage
from .notifications import NotificationService
from .storage import SubAIStorage
from .sync import SyncService

VALID_RANK_METRICS = {"intelligence": "Intelligence", "coding": "Coding", "agentic": "Agentic"}
RANK_USAGE = "用法：subai榜单 intelligence|coding|agentic [5-50]。省略数量时默认返回前 10 名。"
PLUGIN_NAME = "astrbot_plugin_util_official"
MODEL_MATCH_THRESHOLD = 0.6


def _normalize_rank_limit(limit: object) -> int | None:
    if limit is None:
        return 10
    if isinstance(limit, str):
        stripped = limit.strip()
        if not stripped:
            return 10
        limit = stripped
    try:
        parsed = int(limit)
    except (TypeError, ValueError):
        return None
    if parsed < 5 or parsed > 50:
        return None
    return parsed


def _fmt_score(value: float | None) -> str:
    return "-" if value is None else f"{value:.1f}"


def _fmt_rank(value: int | None) -> str:
    return "-" if value is None else str(value)


def _fmt_price(value: float | None) -> str:
    return "-" if value is None else f"${value:.2f}"


def _fmt_seconds(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}s"


def _fmt_speed(value: float | None) -> str:
    return "-" if value is None else f"{value:.1f} tok/s"


def _match_score(query: str, candidate: str) -> float:
    query_norm = query.strip().casefold()
    candidate_norm = candidate.strip().casefold()
    if not query_norm or not candidate_norm:
        return 0.0
    ratio = SequenceMatcher(None, query_norm, candidate_norm).ratio()
    if query_norm in candidate_norm:
        ratio = max(ratio, min(1.0, len(query_norm) / len(candidate_norm) + 0.35))
    query_tokens = [token for token in re.split(r"[\s/_-]+", query_norm) if token]
    candidate_tokens = [token for token in re.split(r"[\s/_-]+", candidate_norm) if token]
    if query_tokens and candidate_tokens:
        token_hits = sum(
            1
            for query_token in query_tokens
            if any(query_token in candidate_token for candidate_token in candidate_tokens)
        )
        token_ratio = token_hits / len(query_tokens)
        if token_ratio == 1.0:
            ratio = max(ratio, min(0.95, 0.55 + 0.4 * len(query_norm) / len(candidate_norm)))
        elif token_ratio >= 0.5:
            ratio = max(ratio, 0.45 + 0.25 * token_ratio)
    return ratio


class SubAIRuntime:
    def __init__(self, *, star, context, config: SubAIConfig) -> None:
        self.star = star
        self.context = context
        self.config = config
        # This call lives in a submodule, so caller-based plugin detection cannot
        # resolve the @register metadata reliably.
        self.data_dir = Path(StarTools.get_data_dir(PLUGIN_NAME))
        self.storage = SubAIStorage(self.data_dir / "subai.sqlite3")
        self.client = ArtificialAnalysisClient(
            api_key=config.api_key,
            timeout_seconds=config.request_timeout_seconds,
            max_retries=config.max_retries,
        )
        self.notifier = NotificationService(
            star=star,
            storage=self.storage,
            card_theme=config.card_theme,
        )
        self.sync_service = SyncService(
            client=self.client,
            storage=self.storage,
            notifier=self.notifier,
            config=config,
        )
        self._poller_task: asyncio.Task | None = None
        self._running = False

    async def initialize(self) -> str:
        await self.storage.initialize()
        if not self.config.has_api_key:
            logger.warning(self.config.missing_api_key_message())
            return self.config.missing_api_key_message()
        self._running = True
        self._poller_task = asyncio.create_task(self._poll_loop())
        return "SubAI 自动轮询已启动。"

    async def terminate(self) -> None:
        self._running = False
        if self._poller_task and not self._poller_task.done():
            self._poller_task.cancel()
            try:
                await self._poller_task
            except asyncio.CancelledError:
                pass

    async def _poll_loop(self) -> None:
        while self._running:
            try:
                await self.sync_service.sync(trigger_source="auto", respect_manual_cooldown=False)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.error("SubAI 自动同步失败: %s", exc)
            await asyncio.sleep(self.config.poll_interval_minutes * 60)

    async def subscribe(self, session_id: str) -> str:
        created = await self.storage.add_subscription(session_id)
        if created:
            return "已为当前会话开启 SubAI 高分模型订阅。"
        return "当前会话已经在 SubAI 订阅列表中。"

    async def unsubscribe(self, session_id: str) -> str:
        removed = await self.storage.remove_subscription(session_id)
        if removed:
            return "已取消当前会话的 SubAI 订阅。"
        return "当前会话原本就没有开启 SubAI 订阅。"

    async def status(self, session_id: str) -> str:
        subscriptions = await self.storage.list_subscriptions()
        subscribed = session_id in subscriptions
        summary = await self.storage.get_last_success_summary()
        watched_count = await self.storage.count_watched_models(self.config.intelligence_threshold)
        lines = [
            "SubAI 状态",
            f"当前会话订阅：{'是' if subscribed else '否'}",
            f"订阅会话总数：{len(subscriptions)}",
            f"Intelligence 门槛：{self.config.intelligence_threshold:.1f}",
            f"当前关注模型数：{watched_count}",
            f"自动轮询间隔：{self.config.poll_interval_minutes} 分钟",
            f"卡片主题：{card_theme_label(self.config.card_theme)}（{self.config.card_theme}）",
        ]
        if not self.config.has_api_key:
            lines.append("自动轮询：未启动（缺少 API Key）")
        elif self._poller_task and not self._poller_task.done():
            lines.append("自动轮询：运行中")
        else:
            lines.append("自动轮询：未运行")
        if summary:
            lines.append(
                f"最近成功同步：{summary['completed_at']}，共 {summary['model_count']} 个模型 / {summary['page_count']} 页"
            )
            lines.append(f"Index 版本：{summary['index_version'] or '未知'}")
            limit_value = summary["rate_limit_limit"]
            remaining_value = summary["rate_limit_remaining"]
            reset_value = summary["rate_limit_reset"] or "未知"
            if limit_value is None or remaining_value is None:
                lines.append(f"API 额度：未知（Reset {reset_value}）")
            else:
                lines.append(f"API 额度：{remaining_value}/{limit_value}（Reset {reset_value}）")
        else:
            lines.append("最近成功同步：暂无")
            lines.append("Index 版本：暂无")
            lines.append("API 额度：暂无")
        return "\n".join(lines)

    async def manual_check(self) -> str:
        if not self.config.has_api_key:
            return self.config.missing_api_key_message()
        result = await self.sync_service.sync(trigger_source="manual", respect_manual_cooldown=True)
        if result.change_count and result.failed_delivery_count:
            return (
                f"{result.message} 已向 {result.delivered_count} 个会话推送，"
                f"{result.failed_delivery_count} 个会话发送失败，后续会继续重试。"
            )
        if result.change_count:
            return f"{result.message} 已向 {result.delivered_count} 个会话推送。"
        return result.message

    async def rank(self, metric: str, limit: object) -> RenderedMessage:
        if metric not in VALID_RANK_METRICS:
            return RenderedMessage(text=f"可用榜单：intelligence、coding、agentic。\n{RANK_USAGE}")
        safe_limit = _normalize_rank_limit(limit)
        if safe_limit is None:
            return RenderedMessage(text=f"榜单数量必须是 5 到 50 之间的整数。\n{RANK_USAGE}")
        models = await self.storage.list_ranked_models(metric, safe_limit)
        if not models:
            return RenderedMessage(text="暂无可用榜单数据，请先等待一次成功同步。")
        summary = await self.storage.get_last_success_summary()
        title = VALID_RANK_METRICS[metric]
        text = format_rank_text(
            metric=metric,
            title=title,
            limit=safe_limit,
            models=models,
            index_version=(summary or {}).get("index_version"),
        )
        try:
            image_path = await render_rank_card(
                self.star,
                metric=metric,
                title=title,
                limit=safe_limit,
                models=models,
                index_version=(summary or {}).get("index_version"),
                theme=self.config.card_theme,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("SubAI 榜单卡片渲染失败: %s", exc)
            return RenderedMessage(text=text)
        return RenderedMessage(text=text, image_path=image_path)

    async def model_detail(self, query: str) -> str:
        query = str(query or "").strip()
        if not query or query == "[模型名称]":
            return "请把按钮里的 [模型名称] 替换成要查询的模型名，例如：subai模型 Gemini 2.5 Pro"
        models = await self.storage.list_current_models()
        if not models:
            return "暂无可用模型数据，请先等待或执行一次成功同步。"

        best_model = None
        best_score = 0.0
        best_field = ""
        for model in models:
            candidates = [
                model.name,
                model.slug,
                model.model_id,
                f"{model.creator} {model.name}".strip(),
            ]
            for candidate in candidates:
                score = _match_score(query, candidate)
                if score > best_score:
                    best_model = model
                    best_score = score
                    best_field = candidate

        if best_model is None or best_score < MODEL_MATCH_THRESHOLD:
            return (
                f"没有找到足够接近“{query}”的模型。\n"
                f"当前最高匹配度：{best_score:.2f}，需要不低于 {MODEL_MATCH_THRESHOLD:.2f}。\n"
                "可以换一个更完整的模型名称或 slug 再试。"
            )

        summary = await self.storage.get_last_success_summary()
        lines = [
            f"SubAI 模型详情：{best_model.name}",
            f"匹配：{best_field}（{best_score:.2f}）",
            f"厂商：{best_model.creator or '未知'}",
            f"Slug：{best_model.slug or '-'}",
            f"模型 ID：{best_model.model_id}",
        ]
        if best_model.release_date:
            lines.append(f"发布日期：{best_model.release_date}")
        if summary and summary.get("index_version"):
            lines.append(f"Index 版本：{summary['index_version']}")
        lines.extend(
            [
                (
                    "评分："
                    f"Intelligence {_fmt_score(best_model.intelligence)} / "
                    f"Coding {_fmt_score(best_model.coding)} / "
                    f"Agentic {_fmt_score(best_model.agentic)}"
                ),
                (
                    "排名："
                    f"Intelligence {_fmt_rank(best_model.ranks.intelligence)} / "
                    f"Coding {_fmt_rank(best_model.ranks.coding)} / "
                    f"Agentic {_fmt_rank(best_model.ranks.agentic)}"
                ),
                (
                    "价格："
                    f"输入 {_fmt_price(best_model.pricing.get('input'))} / "
                    f"输出 {_fmt_price(best_model.pricing.get('output'))} / "
                    f"Cache Hit {_fmt_price(best_model.pricing.get('cache_hit'))} / "
                    f"Cache Write {_fmt_price(best_model.pricing.get('cache_write'))}"
                ),
                (
                    "性能："
                    f"输出速度 {_fmt_speed(best_model.performance.get('output_tps'))} / "
                    f"TTFT {_fmt_seconds(best_model.performance.get('ttft'))} / "
                    f"首答案 {_fmt_seconds(best_model.performance.get('first_answer'))} / "
                    f"完整响应 {_fmt_seconds(best_model.performance.get('end_to_end'))}"
                ),
            ]
        )
        return "\n".join(lines)

    async def manual_cooldown_hint(self) -> str:
        remaining = await self.storage.get_manual_check_cooldown_remaining(
            MANUAL_CHECK_COOLDOWN_MINUTES
        )
        if remaining <= 0:
            return "手动检查可立即执行。"
        minutes, seconds = divmod(remaining, 60)
        return f"手动检查仍在冷却中：{minutes} 分 {seconds} 秒。"
