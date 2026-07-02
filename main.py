import dataclasses
import json
from enum import Enum
from pathlib import Path
from typing import Any

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register


MAX_DUMP_DEPTH = 8
MAX_TEXT_CHUNK_SIZE = 1800
SENSITIVE_KEYWORDS = (
    "secret",
    "token",
    "authorization",
    "password",
    "passwd",
    "cookie",
    "session_key",
)
SKIPPED_EVENT_FIELDS = {
    "bot",
    "context",
    "ctx",
    "message_obj",
    "platform",
    "platform_meta",
    "session",
    "span",
    "trace",
}


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(word in lowered for word in SENSITIVE_KEYWORDS)


def _safe_repr(value: Any) -> str:
    try:
        text = repr(value)
    except Exception as exc:
        return f"<repr failed: {exc}>"
    if len(text) > 500:
        return text[:500] + "...<truncated>"
    return text


def _iter_object_fields(obj: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    if hasattr(obj, "__dict__"):
        try:
            fields.update(vars(obj))
        except Exception:
            pass

    for cls in type(obj).__mro__:
        slots = getattr(cls, "__slots__", ())
        if isinstance(slots, str):
            slots = (slots,)
        for slot in slots:
            if not isinstance(slot, str) or slot.startswith("__") or slot in fields:
                continue
            try:
                fields[slot] = getattr(obj, slot)
            except Exception as exc:
                fields[slot] = f"<getattr failed: {exc}>"
    return fields


def _json_safe(value: Any, *, depth: int = 0, seen: set[int] | None = None) -> Any:
    if seen is None:
        seen = set()
    if depth > MAX_DUMP_DEPTH:
        return f"<max depth {MAX_DUMP_DEPTH} reached: {type(value).__module__}.{type(value).__name__}>"

    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, bytes):
        return {"__type__": "bytes", "length": len(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)

    value_id = id(value)
    if value_id in seen:
        return f"<circular reference: {type(value).__module__}.{type(value).__name__}>"

    if isinstance(value, dict):
        seen.add(value_id)
        result = {}
        for key, item in value.items():
            key_text = str(key)
            result[key_text] = (
                "<redacted>"
                if _is_sensitive_key(key_text)
                else _json_safe(item, depth=depth + 1, seen=seen)
            )
        seen.discard(value_id)
        return result

    if isinstance(value, list | tuple | set | frozenset):
        seen.add(value_id)
        result = [_json_safe(item, depth=depth + 1, seen=seen) for item in value]
        seen.discard(value_id)
        return result

    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        seen.add(value_id)
        result = {}
        for field in dataclasses.fields(value):
            result[field.name] = (
                "<redacted>"
                if _is_sensitive_key(field.name)
                else _json_safe(getattr(value, field.name), depth=depth + 1, seen=seen)
            )
        seen.discard(value_id)
        return result

    if hasattr(value, "model_dump"):
        try:
            return _json_safe(value.model_dump(), depth=depth + 1, seen=seen)
        except Exception:
            pass
    if hasattr(value, "dict"):
        try:
            return _json_safe(value.dict(), depth=depth + 1, seen=seen)
        except Exception:
            pass

    fields = _iter_object_fields(value)
    if fields:
        seen.add(value_id)
        result: dict[str, Any] = {
            "__class__": f"{type(value).__module__}.{type(value).__name__}",
            "__repr__": _safe_repr(value),
        }
        for key, item in fields.items():
            if key.startswith("_api") or key in {"_connection", "_http", "api", "http"}:
                result[key] = f"<skipped: {type(item).__module__}.{type(item).__name__}>"
            elif _is_sensitive_key(key):
                result[key] = "<redacted>"
            else:
                result[key] = _json_safe(item, depth=depth + 1, seen=seen)
        seen.discard(value_id)
        return result

    return {
        "__class__": f"{type(value).__module__}.{type(value).__name__}",
        "__repr__": _safe_repr(value),
    }


def _event_getters(event: AstrMessageEvent) -> dict[str, Any]:
    getter_names = [
        "get_platform_name",
        "get_platform_id",
        "get_message_str",
        "get_message_outline",
        "get_message_type",
        "get_session_id",
        "get_group_id",
        "get_self_id",
        "get_sender_id",
        "get_sender_name",
        "is_private_chat",
        "is_wake_up",
        "is_admin",
        "is_stopped",
    ]
    values: dict[str, Any] = {}
    for name in getter_names:
        try:
            values[name] = _json_safe(getattr(event, name)())
        except Exception as exc:
            values[name] = f"<call failed: {exc}>"
    return values


def _event_public_attrs(event: AstrMessageEvent) -> dict[str, Any]:
    attrs = {}
    for key, value in _iter_object_fields(event).items():
        if key in SKIPPED_EVENT_FIELDS:
            continue
        if key.startswith("_") and key not in {"_extras", "_result", "_has_send_oper"}:
            continue
        attrs[key] = _json_safe(value)
    return attrs


def _component_dump(event: AstrMessageEvent) -> list[Any]:
    dumped = []
    for component in event.get_messages():
        item = _json_safe(component)
        if not isinstance(item, dict):
            item = {"value": item}
        try:
            item["toDict"] = component.toDict()
        except Exception as exc:
            item["toDict"] = f"<toDict failed: {exc}>"
        dumped.append(item)
    return dumped


def _build_event_dump(event: AstrMessageEvent) -> dict[str, Any]:
    message_obj = event.message_obj
    raw_message = getattr(message_obj, "raw_message", None)
    bot = getattr(event, "bot", None)

    return {
        "notice": "bot/client internals and secret-like fields are skipped or redacted to avoid leaking credentials in chat.",
        "event_class": f"{type(event).__module__}.{type(event).__name__}",
        "event_repr": _safe_repr(event),
        "platform_name": event.get_platform_name(),
        "platform_id": event.get_platform_id(),
        "unified_msg_origin": event.unified_msg_origin,
        "getters": _event_getters(event),
        "event_attrs": _event_public_attrs(event),
        "event_extra": _json_safe(event.get_extra()),
        "platform_meta": _json_safe(event.platform_meta),
        "session": _json_safe(event.session),
        "message_obj": _json_safe(message_obj),
        "message_components": _component_dump(event),
        "raw_message_class": f"{type(raw_message).__module__}.{type(raw_message).__name__}",
        "raw_message": _json_safe(raw_message),
        "bot_client": {
            "class": f"{type(bot).__module__}.{type(bot).__name__}" if bot else None,
            "repr": _safe_repr(bot) if bot else None,
            "skipped": True,
        },
    }


def _chunk_text(text: str, size: int = MAX_TEXT_CHUNK_SIZE) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)] or [""]


@register("helloworld", "YourName", "一个简单的 Hello World 插件", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    async def initialize(self):
        pass

    @filter.command("helloworld")
    async def helloworld(self, event: AstrMessageEvent):
        user_name = event.get_sender_name()
        message_str = event.message_str
        message_chain = event.get_messages()
        logger.info(message_chain)
        yield event.plain_result(f"Hello, {user_name}, 你发了 {message_str}!")

    @filter.command("qqofficial_debug")
    async def qqofficial_debug(self, event: AstrMessageEvent):
        if event.get_platform_name() not in {"qq_official", "qq_official_webhook"}:
            yield event.plain_result(
                f"Current platform is {event.get_platform_name()}, not qq_official/qq_official_webhook."
            )
            return

        payload = _build_event_dump(event)
        dump_text = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        chunks = _chunk_text(dump_text)
        total = len(chunks)

        for index, chunk in enumerate(chunks, start=1):
            result = event.plain_result(
                f"QQOfficial event dump {index}/{total}\n```json\n{chunk}\n```"
            )
            result.use_markdown(False)
            yield result

    async def terminate(self):
        pass
