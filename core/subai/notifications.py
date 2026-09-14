from __future__ import annotations

from astrbot.api import logger
from astrbot.api.event import MessageChain
from astrbot.api.star import StarTools

from .cards import (
    format_change_list_text,
    format_change_text,
    render_detail_card,
    render_summary_card,
)
from .storage import SubAIStorage


class NotificationService:
    def __init__(
        self,
        *,
        star,
        storage: SubAIStorage,
        card_theme: str = "analytics",
    ) -> None:
        self.star = star
        self.storage = storage
        self.card_theme = card_theme

    async def deliver_pending_batches(self) -> tuple[int, int]:
        delivered = 0
        failed = 0
        for batch in await self.storage.load_pending_batches():
            changes = batch["changes"]
            for target in batch["targets"]:
                session_id = target["session_id"]
                try:
                    await self._send_changes(session_id, changes)
                except Exception as exc:  # noqa: BLE001
                    failed += 1
                    await self.storage.mark_delivery(
                        batch["batch_id"],
                        session_id,
                        "failed",
                        str(exc),
                    )
                    continue
                delivered += 1
                await self.storage.mark_delivery(batch["batch_id"], session_id, "sent", None)
        return delivered, failed

    async def _send_changes(self, session_id: str, changes: list) -> None:
        text = format_change_text(changes[0]) if len(changes) == 1 else format_change_list_text(changes)
        image_path = None
        try:
            image_path = (
                await render_detail_card(self.star, changes[0], self.card_theme)
                if len(changes) == 1
                else await render_summary_card(self.star, changes, self.card_theme)
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("SubAI 卡片渲染失败，已回退文字消息: %s", exc)
            image_path = None

        if image_path:
            try:
                await self._send_message(session_id, MessageChain().file_image(image_path))
                return
            except Exception as exc:  # noqa: BLE001
                logger.warning("SubAI 图片消息发送失败，已回退文字消息: %s", exc)

        await self._send_message(session_id, MessageChain().message(text))

    async def _send_message(self, session_id: str, chain: MessageChain) -> None:
        try:
            sent = await self.star.context.send_message(session_id, chain)
            if sent is False:
                raise RuntimeError(f"未找到会话对应的平台: {session_id}")
            return
        except Exception:
            send_message = getattr(StarTools, "send_message", None)
            if callable(send_message):
                sent = await send_message(session_id, chain)
                if sent is False:
                    raise RuntimeError(f"未找到会话对应的平台: {session_id}")
                return
            raise
