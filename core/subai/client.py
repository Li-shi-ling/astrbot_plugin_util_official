from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import aiohttp

from .models import ModelSnapshot

FREE_MODELS_ENDPOINT = "https://artificialanalysis.ai/api/v2/language/models/free"


@dataclass(frozen=True)
class RateLimitInfo:
    limit: int | None
    remaining: int | None
    reset: str | None


@dataclass(frozen=True)
class FetchModelsResult:
    models: list[ModelSnapshot]
    page_count: int
    intelligence_index_version: str
    rate_limit: RateLimitInfo


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _coerce_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _header_value(headers: dict[str, str], name: str) -> str | None:
    """Read HTTP headers without depending on server-specific casing."""
    wanted = name.casefold()
    for key, value in headers.items():
        if key.casefold() == wanted:
            return value
    return None


class ArtificialAnalysisClient:
    def __init__(
        self,
        *,
        api_key: str,
        timeout_seconds: int,
        max_retries: int,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self._session = session

    async def fetch_all_models(self) -> FetchModelsResult:
        payloads: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        page = 1
        page_count = 0
        intelligence_index_version = ""
        rate_limit = RateLimitInfo(limit=None, remaining=None, reset=None)
        while True:
            page_payload, response_headers = await self._fetch_page(page)
            if not isinstance(page_payload, dict):
                raise ValueError("Artificial Analysis 页面响应无效")
            items = page_payload.get("data")
            pagination = page_payload.get("pagination")
            if not isinstance(items, list) or not isinstance(pagination, dict):
                raise ValueError("Artificial Analysis 响应结构无效")
            page_version = _coerce_text(page_payload.get("intelligence_index_version"))
            if not page_version:
                raise ValueError("Artificial Analysis 响应缺少 intelligence_index_version")
            if not intelligence_index_version:
                intelligence_index_version = page_version
            elif intelligence_index_version != page_version:
                raise ValueError("Artificial Analysis Index 版本不一致")
            has_more = pagination.get("has_more")
            if not isinstance(has_more, bool):
                raise ValueError("Artificial Analysis 分页信息无效")
            page_count += 1
            rate_limit = RateLimitInfo(
                limit=_coerce_int(_header_value(response_headers, "X-RateLimit-Limit")),
                remaining=_coerce_int(
                    _header_value(response_headers, "X-RateLimit-Remaining")
                ),
                reset=_coerce_text(_header_value(response_headers, "X-RateLimit-Reset"))
                or None,
            )
            for raw_item in items:
                if not isinstance(raw_item, dict):
                    raise ValueError("Artificial Analysis 模型数据无效")
                snapshot = ModelSnapshot.from_payload(raw_item)
                if snapshot.model_id in seen_ids:
                    raise ValueError(f"Artificial Analysis 返回重复模型 UUID: {snapshot.model_id}")
                seen_ids.add(snapshot.model_id)
                payloads.append(raw_item)
            if not has_more:
                break
            page += 1
        return FetchModelsResult(
            models=[ModelSnapshot.from_payload(item) for item in payloads],
            page_count=page_count,
            intelligence_index_version=intelligence_index_version,
            rate_limit=rate_limit,
        )

    async def _fetch_page(self, page: int) -> tuple[dict[str, Any], dict[str, str]]:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                return await self._request_page(page)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt >= self.max_retries:
                    break
                await asyncio.sleep(min(2 ** attempt, 5))
        assert last_error is not None
        raise last_error

    async def _request_page(self, page: int) -> tuple[dict[str, Any], dict[str, str]]:
        headers = {"x-api-key": self.api_key}
        params = {"page": page}
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        if self._session is not None:
            return await self._request_with_session(self._session, headers, params, timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            return await self._request_with_session(session, headers, params, timeout)

    async def _request_with_session(
        self,
        session: aiohttp.ClientSession,
        headers: dict[str, str],
        params: dict[str, int],
        timeout: aiohttp.ClientTimeout,
    ) -> tuple[dict[str, Any], dict[str, str]]:
        async with session.get(FREE_MODELS_ENDPOINT, headers=headers, params=params, timeout=timeout) as response:
            response.raise_for_status()
            payload = await response.json()
            response_headers = dict(response.headers)
        if not isinstance(payload, dict):
            raise ValueError("Artificial Analysis 响应不是 JSON 对象")
        return payload, response_headers
