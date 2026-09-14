from __future__ import annotations

import asyncio
from dataclasses import replace

from .config import MANUAL_CHECK_COOLDOWN_MINUTES, SubAIConfig
from .diff import detect_changes
from .models import SyncResult
from .notifications import NotificationService
from .ranking import apply_rankings
from .storage import SubAIStorage


class SyncService:
    def __init__(
        self,
        *,
        client,
        storage: SubAIStorage,
        notifier: NotificationService,
        config: SubAIConfig,
    ) -> None:
        self.client = client
        self.storage = storage
        self.notifier = notifier
        self.config = config
        self._sync_lock = asyncio.Lock()

    async def sync(self, *, trigger_source: str, respect_manual_cooldown: bool) -> SyncResult:
        async with self._sync_lock:
            # Check the cooldown after acquiring the lock so two simultaneous
            # manual commands cannot both pass the preflight check.
            if trigger_source == "manual" and respect_manual_cooldown:
                remaining = await self.storage.get_manual_check_cooldown_remaining(
                    MANUAL_CHECK_COOLDOWN_MINUTES
                )
                if remaining > 0:
                    minutes, seconds = divmod(remaining, 60)
                    return SyncResult(
                        baseline_created=False,
                        model_count=0,
                        change_count=0,
                        delivered_count=0,
                        failed_delivery_count=0,
                        message=f"手动检查冷却中，请在 {minutes} 分 {seconds} 秒后再试。",
                    )

            previous_models = await self.storage.get_snapshot("baseline")
            try:
                fetched = await self.client.fetch_all_models()
                models = apply_rankings(fetched.models)
            except Exception as exc:  # noqa: BLE001
                await self.storage.save_failed_sync(trigger_source, str(exc))
                raise

            baseline_created = not previous_models
            changes = (
                []
                if baseline_created
                else detect_changes(previous_models, models, self.config.intelligence_threshold)
            )
            changes = [
                replace(change, index_version=fetched.intelligence_index_version)
                for change in changes
            ]
            await self.storage.save_successful_sync(
                trigger_source=trigger_source,
                models=models,
                changes=changes,
                update_manual_check_at=(trigger_source == "manual"),
                page_count=fetched.page_count,
                index_version=fetched.intelligence_index_version,
                rate_limit_limit=fetched.rate_limit.limit,
                rate_limit_remaining=fetched.rate_limit.remaining,
                rate_limit_reset=fetched.rate_limit.reset,
            )
            delivered_count, failed_delivery_count = await self.notifier.deliver_pending_batches()
            if baseline_created:
                message = f"首次成功同步 {len(models)} 个模型，已建立静默基线。"
            else:
                message = f"本轮同步 {len(models)} 个模型，检测到 {len(changes)} 个高分变化。"
            return SyncResult(
                baseline_created=baseline_created,
                model_count=len(models),
                change_count=len(changes),
                delivered_count=delivered_count,
                failed_delivery_count=failed_delivery_count,
                message=message,
            )
