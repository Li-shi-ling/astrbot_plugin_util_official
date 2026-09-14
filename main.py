import asyncio
import dataclasses
import hashlib
import json
import os
import random
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import aiosqlite
import botpy.message as botpy_message
from botpy.interaction import Interaction
from botpy.types import inline as qinline
from botpy.types.message import MarkdownPayload

import astrbot.api.message_components as Comp
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.star import Context, Star, StarTools, register
from astrbot.core.config import AstrBotConfig

try:
    from .core.open_room_parser import parse_create_payload
    from .core.open_room_storage import OpenRoomEntry, OpenRoomStore
    from .core.subai import SubAIConfig, SubAIRuntime
    from .core.subai.runtime import VALID_RANK_METRICS
except ImportError:
    import sys

    plugin_dir = Path(__file__).resolve().parent
    if str(plugin_dir) not in sys.path:
        sys.path.insert(0, str(plugin_dir))
    from core.open_room_parser import parse_create_payload
    from core.open_room_storage import OpenRoomEntry, OpenRoomStore
    from core.subai import SubAIConfig, SubAIRuntime
    from core.subai.runtime import VALID_RANK_METRICS

QQOFFICIAL_PLATFORMS = {"qq_official", "qq_official_webhook"}
QQOFFICIAL_MESSAGE_EVENT_NAMES = {
    "QQOfficialMessageEvent",
    "QQOfficialWebhookMessageEvent",
}
QQOFFICIAL_MESSAGE_EVENT_MODULE_PREFIXES = (
    "astrbot.core.platform.sources.qqofficial.",
    "astrbot.core.platform.sources.qqofficial_webhook.",
)
BOT_AT_MARKER = "qq_official"
BOX_COMMAND_PATTERN = re.compile(r"^\s*盒\s+(\d+)\s*$")
BUTTON_A_ID = "qqofficial_btn_a"
BUTTON_B_ID = "qqofficial_btn_b"
BUTTON_A_DATA = "qqofficial_button_a"
BUTTON_B_DATA = "qqofficial_button_b"
CALLBACK_BUTTON_A_ID = "qqofficial_callback_btn_a"
CALLBACK_BUTTON_B_ID = "qqofficial_callback_btn_b"
CALLBACK_BUTTON_A_DATA = "callback_button_a"
CALLBACK_BUTTON_B_DATA = "callback_button_b"
RESTRICTED_BUTTON_A_ID = "qqofficial_restricted_btn_a"
RESTRICTED_BUTTON_B_ID = "qqofficial_restricted_btn_b"
BUTTON_PROMPT = "请选择一个按钮"
CALLBACK_BUTTON_PROMPT = "请选择一个回调按钮"
RESTRICTED_BUTTON_PROMPT = "请选择一个仅发送者可操作的按钮"
BUTTON_A_LABEL = "按钮 A"
BUTTON_B_LABEL = "按钮 B"
CALLBACK_BUTTON_A_LABEL = "回调 A"
CALLBACK_BUTTON_B_LABEL = "回调 B"
RESTRICTED_BUTTON_A_LABEL = "仅本人 A"
RESTRICTED_BUTTON_B_LABEL = "仅本人 B"
BUTTON_A_VISITED_LABEL = "已按下 A"
BUTTON_B_VISITED_LABEL = "已按下 B"
CALLBACK_BUTTON_A_VISITED_LABEL = "已回调 A"
CALLBACK_BUTTON_B_VISITED_LABEL = "已回调 B"
RESTRICTED_BUTTON_A_VISITED_LABEL = "本人已按 A"
RESTRICTED_BUTTON_B_VISITED_LABEL = "本人已按 B"
QQOFFICIAL_INTERACTION_INTENT = 1 << 26
OPEN_ROOM_COMMAND_PREFIX = "开房"
OPEN_ROOM_CREATE_TEMPLATE = "开房创建 房间码或邀请链接｜游戏/平台｜备注=玩法时间｜初始=1｜上限=4"
OPEN_ROOM_LONG_TERM_TEMPLATE = "开房创建 好友码或服务器地址｜游戏/平台｜备注=长期可加｜长期"
OPEN_ROOM_JOIN_TEMPLATE = "开房加入 #RM0001"
OPEN_ROOM_DELETE_TEMPLATE = "开房删除 #RM0001"
SUBAI_COMMAND_PREFIX = "subai"
SUBAI_MENU_TEXT = "subai菜单"
SUBAI_STATUS_TEXT = "subai状态"
SUBAI_SUBSCRIBE_TEXT = "subai订阅"
SUBAI_UNSUBSCRIBE_TEXT = "subai取消订阅"
SUBAI_CHECK_TEXT = "subai检查"
SUBAI_RANK_INTELLIGENCE_TEXT = "subai榜单 intelligence 10"
SUBAI_RANK_CODING_TEXT = "subai榜单 coding 10"
SUBAI_RANK_AGENTIC_TEXT = "subai榜单 agentic 10"
SUBAI_MODEL_DETAIL_TEMPLATE = "subai模型 [模型名称]"
TENCENT_MAP_API_BASE = "https://apis.map.qq.com"
TENCENT_MAP_PLACE_SEARCH_PATH = "/ws/place/v1/search"
TENCENT_MAP_STATIC_PATH = "/ws/staticmap/v2/"
DEFAULT_PLACE_KEYWORDS = [
    "公园",
    "商场",
    "酒店",
    "学校",
    "医院",
    "景点",
    "美食",
    "超市",
]

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


@dataclass(frozen=True)
class GeneratedLocation:
    address: str
    map_url: str | None = None


@dataclass(frozen=True)
class QQOfficialButtonSpec:
    button_id: str
    label: str
    visited_label: str
    data: str


@dataclass(frozen=True)
class QQOfficialInteractionContext:
    interaction_id: str
    scene: str | None
    chat_type: int | None
    user_openid: str | None = None
    group_openid: str | None = None
    group_member_openid: str | None = None
    guild_id: str | None = None
    channel_id: str | None = None
    button_id: str | None = None
    button_data: str | None = None
    message_id: str | None = None


class QQOfficialEventPlatformProxy:
    def __init__(self, client: Any, platform_name: str | None):
        self.client = client
        self._platform_name = platform_name

    def meta(self) -> Any:
        return SimpleNamespace(name=self._platform_name)


def _build_button_keyboard() -> qinline.Keyboard:
    return {
        "content": {
            "rows": [
                {
                    "buttons": [
                        _build_button_payload(
                            QQOfficialButtonSpec(
                                button_id=BUTTON_A_ID,
                                label=BUTTON_A_LABEL,
                                visited_label=BUTTON_A_VISITED_LABEL,
                                data=BUTTON_A_DATA,
                            )
                        ),
                        _build_button_payload(
                            QQOfficialButtonSpec(
                                button_id=BUTTON_B_ID,
                                label=BUTTON_B_LABEL,
                                visited_label=BUTTON_B_VISITED_LABEL,
                                data=BUTTON_B_DATA,
                            )
                        ),
                    ]
                }
            ]
        }
    }


def _build_button_payload(spec: QQOfficialButtonSpec) -> qinline.Button:
    return _build_command_button_payload(spec, permission={"type": 2})


def _build_command_button_payload(
    spec: QQOfficialButtonSpec,
    *,
    permission: dict[str, Any],
) -> qinline.Button:
    return {
        "id": spec.button_id,
        "render_data": {
            "label": spec.label,
            "visited_label": spec.visited_label,
            "style": 1,
        },
        "action": {
            "type": 2,
            "permission": dict(permission),
            "data": spec.data,
            "reply": True,
            "enter": False,
            "unsupport_tips": "当前客户端不支持该按钮",
        },
    }


def _build_restricted_button_keyboard(allowed_user_id: str) -> qinline.Keyboard:
    permission = {
        "type": 0,
        "specify_user_ids": [allowed_user_id],
    }
    return {
        "content": {
            "rows": [
                {
                    "buttons": [
                        _build_command_button_payload(
                            QQOfficialButtonSpec(
                                button_id=RESTRICTED_BUTTON_A_ID,
                                label=RESTRICTED_BUTTON_A_LABEL,
                                visited_label=RESTRICTED_BUTTON_A_VISITED_LABEL,
                                data=BUTTON_A_DATA,
                            ),
                            permission=permission,
                        ),
                        _build_command_button_payload(
                            QQOfficialButtonSpec(
                                button_id=RESTRICTED_BUTTON_B_ID,
                                label=RESTRICTED_BUTTON_B_LABEL,
                                visited_label=RESTRICTED_BUTTON_B_VISITED_LABEL,
                                data=BUTTON_B_DATA,
                            ),
                            permission=permission,
                        ),
                    ]
                }
            ]
        }
    }


def _build_callback_button_keyboard() -> qinline.Keyboard:
    return {
        "content": {
            "rows": [
                {
                    "buttons": [
                        _build_callback_button_payload(
                            QQOfficialButtonSpec(
                                button_id=CALLBACK_BUTTON_A_ID,
                                label=CALLBACK_BUTTON_A_LABEL,
                                visited_label=CALLBACK_BUTTON_A_VISITED_LABEL,
                                data=CALLBACK_BUTTON_A_DATA,
                            )
                        ),
                        _build_callback_button_payload(
                            QQOfficialButtonSpec(
                                button_id=CALLBACK_BUTTON_B_ID,
                                label=CALLBACK_BUTTON_B_LABEL,
                                visited_label=CALLBACK_BUTTON_B_VISITED_LABEL,
                                data=CALLBACK_BUTTON_B_DATA,
                            )
                        ),
                    ]
                }
            ]
        }
    }


def _build_callback_button_payload(spec: QQOfficialButtonSpec) -> qinline.Button:
    return {
        "id": spec.button_id,
        "render_data": {
            "label": spec.label,
            "visited_label": spec.visited_label,
            "style": 1,
        },
        "action": {
            "type": 1,
            "permission": {
                "type": 2,
                "specify_user_ids": [],
                "specify_role_ids": [],
            },
            "data": spec.data,
            "click_limit": 0,
            "at_bot_show_channel_list": False,
            "unsupport_tips": "当前客户端不支持该按钮",
        },
    }


def _button_display_text(button_id: str | None, button_data: str | None) -> str:
    if button_id in {BUTTON_A_ID, CALLBACK_BUTTON_A_ID} or button_data in {
        BUTTON_A_DATA,
        CALLBACK_BUTTON_A_DATA,
    }:
        return "A"
    if button_id in {BUTTON_B_ID, CALLBACK_BUTTON_B_ID} or button_data in {
        BUTTON_B_DATA,
        CALLBACK_BUTTON_B_DATA,
    }:
        return "B"
    return "未知"


def _build_button_message_payload() -> dict[str, Any]:
    return {
        "msg_type": 2,
        "markdown": MarkdownPayload(content=BUTTON_PROMPT),
        "keyboard": _build_button_keyboard(),
    }


def _build_callback_button_message_payload() -> dict[str, Any]:
    return {
        "msg_type": 2,
        "markdown": MarkdownPayload(content=CALLBACK_BUTTON_PROMPT),
        "keyboard": _build_callback_button_keyboard(),
    }


def _build_restricted_button_message_payload(allowed_user_id: str) -> dict[str, Any]:
    return {
        "msg_type": 2,
        "markdown": MarkdownPayload(content=RESTRICTED_BUTTON_PROMPT),
        "keyboard": _build_restricted_button_keyboard(allowed_user_id),
    }


def _build_open_room_button(button_id: str, label: str, data: str) -> qinline.Button:
    return _build_button_payload(
        QQOfficialButtonSpec(
            button_id=button_id,
            label=label,
            visited_label=label,
            data=data,
        )
    )


def _build_open_room_keyboard(
    entries: list[OpenRoomEntry] | None = None,
    *,
    kind: str = "menu",
) -> qinline.Keyboard:
    rows: list[dict[str, list[qinline.Button]]] = []
    entries = entries or []
    if kind in {"menu", "create"}:
        rows.extend(
            [
                {
                    "buttons": [
                        _build_open_room_button(
                            "open_room_create_short",
                            "创建短期房",
                            OPEN_ROOM_CREATE_TEMPLATE,
                        ),
                        _build_open_room_button(
                            "open_room_create_long",
                            "创建长期房",
                            OPEN_ROOM_LONG_TERM_TEMPLATE,
                        ),
                    ]
                },
                {
                    "buttons": [
                        _build_open_room_button("open_room_find", "查找房间", "开房查找"),
                        _build_open_room_button("open_room_join", "输入加入", OPEN_ROOM_JOIN_TEMPLATE),
                        _build_open_room_button("open_room_delete", "删除房间", OPEN_ROOM_DELETE_TEMPLATE),
                    ]
                },
            ]
        )
    elif kind in {"entry", "entries"}:
        join_buttons = [
            _build_open_room_button(
                f"open_room_join_{entry.code}",
                f"加入 {entry.code}",
                f"开房加入 #{entry.code}",
            )
            for entry in entries[:10]
            if not entry.is_full
        ]
        for offset in range(0, len(join_buttons), 5):
            rows.append({"buttons": join_buttons[offset : offset + 5]})
        rows.append(
            {
                "buttons": [
                    _build_open_room_button("open_room_refresh", "刷新列表", "开房查找"),
                    _build_open_room_button("open_room_menu", "菜单", "开房"),
                ]
            }
        )
    return {"content": {"rows": rows[:5]}}


def _build_open_room_message_payload(
    text: str,
    *,
    entries: list[OpenRoomEntry] | None = None,
    kind: str = "menu",
) -> dict[str, Any]:
    return {
        "msg_type": 2,
        "markdown": MarkdownPayload(content=_format_open_room_markdown(text)),
        "keyboard": _build_open_room_keyboard(entries, kind=kind),
    }



def _build_subai_button(button_id: str, label: str, data: str) -> qinline.Button:
    return _build_button_payload(
        QQOfficialButtonSpec(
            button_id=button_id,
            label=label,
            visited_label=label,
            data=data,
        )
    )


def _build_subai_keyboard(kind: str = "menu") -> qinline.Keyboard:
    if kind == "rank":
        rows = [
            {
                "buttons": [
                    _build_subai_button("subai_rank_intelligence", "智力榜", SUBAI_RANK_INTELLIGENCE_TEXT),
                    _build_subai_button("subai_rank_coding", "编程榜", SUBAI_RANK_CODING_TEXT),
                    _build_subai_button("subai_rank_agentic", "代理榜", SUBAI_RANK_AGENTIC_TEXT),
                ]
            },
            {
                "buttons": [
                    _build_subai_button("subai_model_detail", "查看模型", SUBAI_MODEL_DETAIL_TEMPLATE),
                    _build_subai_button("subai_status", "状态", SUBAI_STATUS_TEXT),
                    _build_subai_button("subai_menu", "菜单", SUBAI_MENU_TEXT),
                ]
            },
        ]
    else:
        rows = [
            {
                "buttons": [
                    _build_subai_button("subai_status", "状态", SUBAI_STATUS_TEXT),
                    _build_subai_button("subai_check", "手动检查", SUBAI_CHECK_TEXT),
                    _build_subai_button("subai_rank_menu", "榜单", SUBAI_RANK_INTELLIGENCE_TEXT),
                    _build_subai_button("subai_model_detail", "查看模型", SUBAI_MODEL_DETAIL_TEMPLATE),
                ]
            },
            {
                "buttons": [
                    _build_subai_button("subai_subscribe", "订阅", SUBAI_SUBSCRIBE_TEXT),
                    _build_subai_button("subai_unsubscribe", "取消订阅", SUBAI_UNSUBSCRIBE_TEXT),
                ]
            },
            {
                "buttons": [
                    _build_subai_button("subai_rank_intelligence", "智力榜", SUBAI_RANK_INTELLIGENCE_TEXT),
                    _build_subai_button("subai_rank_coding", "编程榜", SUBAI_RANK_CODING_TEXT),
                    _build_subai_button("subai_rank_agentic", "代理榜", SUBAI_RANK_AGENTIC_TEXT),
                ]
            },
        ]
    return {"content": {"rows": rows[:5]}}


def _build_subai_message_payload(text: str, *, kind: str = "menu") -> dict[str, Any]:
    return {
        "msg_type": 2,
        "markdown": MarkdownPayload(content=_format_subai_markdown(text)),
        "keyboard": _build_subai_keyboard(kind=kind),
    }


def _build_button_reply_payload(text: str) -> dict[str, Any]:
    return {
        "content": text,
        "msg_type": 0,
        "markdown": None,
        "keyboard": None,
    }


def _build_button_reply_text(button_id: str | None, button_data: str | None) -> str:
    return f"你按了 {_button_display_text(button_id, button_data)}"


def _first_non_empty_str(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value)
        if text:
            return text
    return None


def _extract_message_reference_id(raw_message: Any, message_obj: Any) -> str | None:
    return _first_non_empty_str(
        getattr(raw_message, "id", None),
        getattr(message_obj, "message_id", None),
    )


def _add_passive_reply_context(
    payload: dict[str, Any],
    *,
    msg_id: str | None = None,
    event_id: str | None = None,
    msg_seq: int | None = None,
) -> dict[str, Any]:
    if msg_id:
        payload["msg_id"] = msg_id
    elif event_id:
        payload["event_id"] = event_id
    if payload.get("msg_id") or payload.get("event_id"):
        payload["msg_seq"] = msg_seq if msg_seq is not None else random.randint(1, 10000)
    return payload


def _debug_json(value: Any) -> str:
    return json.dumps(_json_safe(value), ensure_ascii=False, default=str)


def _build_button_debug_context(raw_message: Any, message_obj: Any) -> dict[str, Any]:
    author = getattr(raw_message, "author", None)
    return {
        "raw_message_class": f"{type(raw_message).__module__}.{type(raw_message).__name__}",
        "raw_id": getattr(raw_message, "id", None),
        "raw_msg_seq": getattr(raw_message, "msg_seq", None),
        "raw_event_id": getattr(raw_message, "event_id", None),
        "message_obj_message_id": getattr(message_obj, "message_id", None),
        "group_openid": getattr(raw_message, "group_openid", None),
        "author_user_openid": getattr(author, "user_openid", None),
        "author_member_openid": getattr(author, "member_openid", None),
    }


def _extract_interaction_context(raw_event: Any) -> QQOfficialInteractionContext | None:
    if raw_event is None:
        return None

    interaction: Any
    if isinstance(raw_event, Interaction):
        interaction = raw_event
    else:
        interaction = raw_event

    data = getattr(interaction, "data", None)
    resolved = getattr(data, "resolved", None)
    button_id = getattr(resolved, "button_id", None)
    button_data = getattr(resolved, "button_data", None)
    message_id = getattr(resolved, "message_id", None)
    return QQOfficialInteractionContext(
        interaction_id=str(getattr(interaction, "id", "") or ""),
        scene=getattr(interaction, "scene", None),
        chat_type=getattr(interaction, "chat_type", None),
        user_openid=getattr(interaction, "user_openid", None),
        group_openid=getattr(interaction, "group_openid", None),
        group_member_openid=getattr(interaction, "group_member_openid", None),
        guild_id=getattr(interaction, "guild_id", None),
        channel_id=getattr(interaction, "channel_id", None),
        button_id=str(button_id) if button_id is not None else None,
        button_data=str(button_data) if button_data is not None else None,
        message_id=str(message_id) if message_id is not None else None,
    )


def _interaction_to_debug_dict(context: QQOfficialInteractionContext) -> dict[str, Any]:
    return {
        "interaction_id": context.interaction_id,
        "scene": context.scene,
        "chat_type": context.chat_type,
        "user_openid": context.user_openid,
        "group_openid": context.group_openid,
        "group_member_openid": context.group_member_openid,
        "guild_id": context.guild_id,
        "channel_id": context.channel_id,
        "button_id": context.button_id,
        "button_data": context.button_data,
        "message_id": context.message_id,
    }


def _is_qqofficial_message_event(event: AstrMessageEvent) -> bool:
    event_type = type(event)
    module_name = event_type.__module__.lower()
    return (
        event_type.__name__ in QQOFFICIAL_MESSAGE_EVENT_NAMES
        and module_name.startswith(QQOFFICIAL_MESSAGE_EVENT_MODULE_PREFIXES)
    )


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


def _open_room_help_text() -> str:
    return (
        "开房菜单\n"
        "点按钮生成指令后，把模板里的房间码、游戏名、人数改成自己的内容。\n"
        "也可以直接发送：开房查找 / 开房加入 #RM0001 / 开房删除 #RM0001"
    )


def _open_room_create_help_text() -> str:
    return (
        "创建房间\n"
        f"短期模板：{OPEN_ROOM_CREATE_TEMPLATE}\n"
        f"长期模板：{OPEN_ROOM_LONG_TERM_TEMPLATE}\n"
        "字段用 ｜ 分隔；可选字段：备注=、初始=、上限=、长期。"
    )


def _render_open_room_entry(entry: OpenRoomEntry) -> str:
    limit = str(entry.max_count) if entry.max_count is not None else "∞"
    lifetime = "长期" if entry.is_long_term else "短期"
    if entry.is_full:
        lifetime += "，已满"
    elif entry.expires_at:
        lifetime += f"，至 {entry.expires_at.astimezone().strftime('%m-%d %H:%M')}"
    return "\n".join(
        [
            f"[#{entry.code}] {entry.game_or_platform}",
            entry.note or "（无备注）",
            f"{entry.current_count} / {limit} 人｜{lifetime}",
            f"房间信息：{entry.locator_text}",
        ]
    )


def _format_open_room_markdown(text: str) -> str:
    lines: list[str] = []
    for raw in (text or "开房").splitlines():
        stripped = raw.strip()
        if stripped in {"开房菜单", "创建房间"}:
            lines.append(f"## {stripped}")
        elif stripped.startswith("[#"):
            lines.append(f"### {stripped}")
        elif stripped.startswith("房间信息："):
            lines.append(f"**房间信息**：{stripped.removeprefix('房间信息：')}")
        elif stripped:
            lines.append(stripped)
        else:
            lines.append("")
    return "\n".join(lines).strip() or "开房"


def _subai_menu_text() -> str:
    return (
        "SubAI 菜单\n"
        "追踪 Artificial Analysis 免费模型榜单变化。\n\n"
        "可用操作：\n"
        "subai状态\n"
        "subai订阅\n"
        "subai取消订阅\n"
        "subai检查\n"
        "subai模型 [模型名称]\n"
        "subai榜单 intelligence|coding|agentic [5-50]"
    )


def _format_subai_markdown(text: str) -> str:
    lines: list[str] = []
    for raw in (text or "SubAI").splitlines():
        stripped = raw.strip()
        if stripped in {"SubAI 菜单", "SubAI 状态"}:
            lines.append(f"## {stripped}")
        elif stripped.startswith("SubAI "):
            lines.append(f"## {stripped}")
        elif stripped.startswith("#"):
            lines.append(stripped)
        elif stripped.startswith("Top "):
            lines.append(f"### {stripped}")
        elif "：" in stripped and not stripped.startswith("http"):
            name, value = stripped.split("：", 1)
            lines.append(f"**{name}**：{value}")
        elif stripped:
            lines.append(stripped)
        else:
            lines.append("")
    return "\n".join(lines).strip() or "SubAI"


@register(
    "astrbot_plugin_util_official",
    "Codex",
    "QQOfficial 适配版娱乐、调试、开房组队与 SubAI 实验插件",
    "1.4.1",
)
class QQOfficialUtilPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig | None = None):
        super().__init__(context)
        self.config = config or {}
        self.location_data: dict = {}
        self.location_pool: list[str] = []
        self.search_region_pool: list[dict[str, str]] = []
        self._interaction_hook_installed = False
        self.open_room_store = OpenRoomStore(Path(StarTools.get_data_dir()) / "open_room.db")
        self.subai_config = self._build_subai_config()
        self.subai_runtime = SubAIRuntime(
            star=self,
            context=context,
            config=self.subai_config,
        )
        self._background_tasks: set[asyncio.Task[None]] = set()
        self._load_location_data()

    async def initialize(self):
        await self.open_room_store.initialize()
        await self.subai_runtime.initialize()
        self._install_interaction_hook()
        self._spawn_background_task(self._cleanup_open_room_loop())

    @filter.on_platform_loaded()
    async def _on_platform_loaded(self):
        self._install_interaction_hook()

    async def _cleanup_open_room_loop(self) -> None:
        while True:
            await asyncio.sleep(60 * 60)
            try:
                deleted = await self.open_room_store.delete_expired()
                if deleted:
                    logger.info("[QQOfficialUtil] 清理过期开房条目 %s 个。", deleted)
            except Exception:
                logger.exception("[QQOfficialUtil] 清理过期开房条目失败。")

    def _spawn_background_task(self, coroutine) -> None:
        task = asyncio.create_task(coroutine)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    def _install_interaction_hook(self) -> None:
        patched = False
        seen_platforms = 0
        for platform in self.context.platform_manager.platform_insts:
            if platform.meta().name not in QQOFFICIAL_PLATFORMS:
                continue
            seen_platforms += 1
            client = getattr(platform, "client", None)
            if client is None:
                continue
            self._ensure_interaction_intent(client)
            if self._patch_qqofficial_client(platform, client):
                patched = True
        if patched:
            self._interaction_hook_installed = True
        elif seen_platforms == 0:
            logger.warning("[QQOfficialUtil] 未发现已加载的 QQOfficial 平台，暂无法安装按钮回调 hook。")

    def _install_interaction_hook_from_event(self, event: AstrMessageEvent) -> None:
        client = getattr(event, "bot", None)
        if client is None:
            logger.warning("[QQOfficialUtil] 当前事件缺少 bot client，无法兜底安装按钮回调 hook。")
            return

        self._ensure_interaction_intent(client)
        platform = QQOfficialEventPlatformProxy(
            client,
            event.get_platform_name() if hasattr(event, "get_platform_name") else None,
        )
        if self._patch_qqofficial_client(platform, client):
            self._interaction_hook_installed = True

    def _ensure_interaction_intent(self, client: Any) -> None:
        current_intents = getattr(client, "intents", None)
        if not isinstance(current_intents, int):
            logger.warning(
                "[QQOfficialUtil] 无法确认 interaction intent: client=%s, intents=%r",
                type(client).__name__,
                current_intents,
            )
            return
        if current_intents & QQOFFICIAL_INTERACTION_INTENT:
            logger.info(
                "[QQOfficialUtil] QQOfficial client 已包含 interaction intent: intents=%s",
                current_intents,
            )
            return
        client.intents = current_intents | QQOFFICIAL_INTERACTION_INTENT
        logger.warning(
            "[QQOfficialUtil] 已为 QQOfficial client 补充 interaction intent: %s -> %s。"
            "如果 websocket 已连接，需要重启/重连 QQOfficial 平台后才会收到按钮点击事件。",
            current_intents,
            client.intents,
        )

    def _patch_qqofficial_client(self, platform: Any, client: Any) -> bool:
        if (
            getattr(client, "_codex_button_hook_installed", False)
            and getattr(client, "_codex_button_hook_owner", None) == id(self)
        ):
            logger.info(
                "[QQOfficialUtil] QQOfficial interaction hook 已安装在当前插件实例: client=%s",
                type(client).__name__,
            )
            return False

        plugin = self
        original = getattr(
            client,
            "_codex_button_hook_original",
            getattr(client, "on_interaction_create", None),
        )

        async def on_interaction_create(interaction: Interaction):
            logger.info(
                "[QQOfficialUtil] 收到按钮回调原始事件: %s",
                _debug_json(interaction),
            )
            await plugin._handle_qqofficial_interaction(platform, interaction)
            if original and original is not on_interaction_create:
                maybe = original(interaction)
                if asyncio.iscoroutine(maybe):
                    await maybe

        client.on_interaction_create = on_interaction_create
        client._codex_button_hook_installed = True
        client._codex_button_hook_owner = id(self)
        client._codex_button_hook_original = original
        logger.info(
            "[QQOfficialUtil] 已安装 QQOfficial interaction hook: platform=%r, client=%s, original_handler=%s",
            platform.meta().name if hasattr(platform, "meta") else None,
            type(client).__name__,
            bool(original),
        )
        return True

    async def _handle_qqofficial_interaction(
        self,
        platform: Any,
        interaction: Interaction,
    ) -> None:
        context = _extract_interaction_context(interaction)
        if not context or not context.interaction_id:
            logger.warning("[QQOfficialUtil] 忽略按钮回调：缺少 interaction_id。")
            return
        logger.info(
            "[QQOfficialUtil] 解析按钮回调上下文: %s",
            _debug_json(_interaction_to_debug_dict(context)),
        )
        if context.button_id not in {
            BUTTON_A_ID,
            BUTTON_B_ID,
            CALLBACK_BUTTON_A_ID,
            CALLBACK_BUTTON_B_ID,
        } and context.button_data not in {
            BUTTON_A_DATA,
            BUTTON_B_DATA,
            CALLBACK_BUTTON_A_DATA,
            CALLBACK_BUTTON_B_DATA,
        }:
            logger.info(
                "[QQOfficialUtil] 忽略非本插件按钮回调: button_id=%r, button_data=%r",
                context.button_id,
                context.button_data,
            )
            return

        try:
            ack_ret = await platform.client.api.on_interaction_result(context.interaction_id, 0)
            logger.info(
                "[QQOfficialUtil] 按钮回调 ACK 成功: interaction_id=%s, ret=%s",
                context.interaction_id,
                _debug_json(ack_ret),
            )
        except Exception as exc:
            logger.warning(f"[QQOfficialUtil] interaction ACK 失败: {exc}")

        await self._reply_button_press(platform, context)

    async def _reply_button_press(self, platform: Any, context: QQOfficialInteractionContext) -> None:
        text = _build_button_reply_text(context.button_id, context.button_data)
        payload = _build_button_reply_payload(text)
        raw_scene = (context.scene or "").lower()
        try:
            _add_passive_reply_context(payload, event_id=context.interaction_id)
            if raw_scene == "group" and context.group_openid:
                logger.info(
                    "[QQOfficialUtil] 准备回复按钮回调(group): group_openid=%s, payload=%s",
                    context.group_openid,
                    _debug_json(payload),
                )
                ret = await platform.client.api.post_group_message(
                    group_openid=context.group_openid,
                    **payload,
                )
                logger.info("[QQOfficialUtil] 按钮回调回复成功(group): ret=%s", _debug_json(ret))
                return
            if raw_scene == "c2c" and context.user_openid:
                logger.info(
                    "[QQOfficialUtil] 准备回复按钮回调(c2c): openid=%s, payload=%s",
                    context.user_openid,
                    _debug_json(payload),
                )
                ret = await platform.client.api.post_c2c_message(
                    openid=context.user_openid,
                    **payload,
                )
                logger.info("[QQOfficialUtil] 按钮回调回复成功(c2c): ret=%s", _debug_json(ret))
                return
            logger.warning(
                f"[QQOfficialUtil] 按钮回调场景不受支持: scene={context.scene!r}, chat_type={context.chat_type!r}"
            )
        except Exception as exc:
            logger.warning(f"[QQOfficialUtil] 回复按钮回调失败: {exc}")

    @filter.platform_adapter_type(
        filter.PlatformAdapterType.QQOFFICIAL
        | filter.PlatformAdapterType.QQOFFICIAL_WEBHOOK
    )
    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def qqofficial_box(self, event: AstrMessageEvent):
        command_text = self._extract_box_command_text(event)
        if command_text is None:
            return

        qq = self._parse_box_target(command_text)
        if not qq:
            if command_text.strip().startswith("盒"):
                yield event.plain_result("格式错误，请使用：@机器人 盒 123456789")
                event.stop_event()
            return

        sender_id = event.get_sender_id()
        if sender_id and not self._is_user_allowed(str(sender_id)):
            yield event.plain_result("当前账号未启用该功能")
            event.stop_event()
            return

        yield event.plain_result(f"正在生成 {qq} 的虚拟信息...")
        output_text, map_url = await self.generate_fake_dox(qq)
        chain = [
            Comp.Plain(output_text),
            Comp.Image.fromURL(f"https://q4.qlogo.cn/headimg_dl?dst_uin={qq}&spec=640"),
        ]
        if map_url:
            chain.append(Comp.Image.fromURL(map_url))
        yield event.chain_result(chain)
        event.stop_event()

    @filter.command("qqofficial_debug")
    async def qqofficial_debug(self, event: AstrMessageEvent):
        if not _is_qqofficial_message_event(event):
            yield event.plain_result(
                "该指令仅支持 QQOfficialMessageEvent / QQOfficialWebhookMessageEvent。"
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

    @filter.command("qqofficial_buttons")
    async def qqofficial_buttons(self, event: AstrMessageEvent):
        async for result in self._send_qqofficial_button_message(
            event,
            command_name="qqofficial_buttons",
            payload=_build_button_message_payload(),
        ):
            yield result

    @filter.command("qqofficial_callback_buttons")
    async def qqofficial_callback_buttons(self, event: AstrMessageEvent):
        async for result in self._send_qqofficial_button_message(
            event,
            command_name="qqofficial_callback_buttons",
            payload=_build_callback_button_message_payload(),
        ):
            yield result

    @filter.command("qqofficial_restricted_buttons")
    async def qqofficial_restricted_buttons(self, event: AstrMessageEvent):
        allowed_user_id = self._extract_button_sender_openid(event)
        if not allowed_user_id:
            logger.warning(
                "[QQOfficialUtil] qqofficial_restricted_buttons 拒绝：无法提取发送者 openid。event_class=%s.%s",
                type(event).__module__,
                type(event).__name__,
            )
            yield event.plain_result("未找到发送者 openid/member_openid，无法发送指定用户按钮。")
            return

        logger.info(
            "[QQOfficialUtil] qqofficial_restricted_buttons 使用发送者 ID 限制按钮: allowed_user_id=%s",
            allowed_user_id,
        )
        async for result in self._send_qqofficial_button_message(
            event,
            command_name="qqofficial_restricted_buttons",
            payload=_build_restricted_button_message_payload(allowed_user_id),
        ):
            yield result

    def _extract_button_sender_openid(self, event: AstrMessageEvent) -> str:
        raw_message = getattr(event.message_obj, "raw_message", None)
        author = getattr(raw_message, "author", None)
        return _first_non_empty_str(
            getattr(author, "member_openid", None),
            getattr(raw_message, "group_member_openid", None),
            getattr(author, "user_openid", None),
            getattr(raw_message, "user_openid", None),
            event.get_sender_id() if hasattr(event, "get_sender_id") else None,
        ) or ""

    async def _send_qqofficial_button_message(
        self,
        event: AstrMessageEvent,
        *,
        command_name: str,
        payload: dict[str, Any],
    ):
        logger.info(
            "[QQOfficialUtil] %s 触发: event_class=%s.%s, platform=%r, message=%r",
            command_name,
            type(event).__module__,
            type(event).__name__,
            event.get_platform_name() if hasattr(event, "get_platform_name") else None,
            event.get_message_str() if hasattr(event, "get_message_str") else None,
        )
        if not _is_qqofficial_message_event(event):
            logger.warning(
                "[QQOfficialUtil] %s 拒绝：非 QQOfficial 事件 event_class=%s.%s",
                command_name,
                type(event).__module__,
                type(event).__name__,
            )
            yield event.plain_result("该指令仅支持 QQOfficialMessageEvent / QQOfficialWebhookMessageEvent。")
            return

        self._install_interaction_hook_from_event(event)

        raw_message = getattr(event.message_obj, "raw_message", None)
        if raw_message is None:
            logger.warning(
                "[QQOfficialUtil] %s 拒绝：message_obj 缺少 raw_message。message_obj=%s",
                command_name,
                _debug_json(getattr(event, "message_obj", None)),
            )
            yield event.plain_result("未找到 QQOfficial 原始消息对象，无法发送按钮。")
            return

        debug_context = _build_button_debug_context(raw_message, event.message_obj)
        _add_passive_reply_context(
            payload,
            msg_id=_extract_message_reference_id(raw_message, event.message_obj),
            msg_seq=getattr(raw_message, "msg_seq", None),
        )
        logger.info(
            "[QQOfficialUtil] %s 原始上下文: %s",
            command_name,
            _debug_json(debug_context),
        )
        logger.info(
            "[QQOfficialUtil] %s 最终发送 payload: %s",
            command_name,
            _debug_json(payload),
        )
        if not payload.get("msg_id") and not payload.get("event_id"):
            logger.warning(
                "[QQOfficialUtil] %s 未找到 msg_id/event_id，平台可能按主动消息处理。",
                command_name,
            )
        try:
            if isinstance(raw_message, botpy_message.GroupMessage):
                logger.info(
                    "[QQOfficialUtil] %s 使用 group 接口发送: group_openid=%s",
                    command_name,
                    raw_message.group_openid,
                )
                ret = await event.bot.api.post_group_message(
                    group_openid=raw_message.group_openid,
                    **payload,
                )
                logger.info(
                    "[QQOfficialUtil] %s group API 返回: %s",
                    command_name,
                    _debug_json(ret),
                )
            elif isinstance(raw_message, botpy_message.C2CMessage):
                logger.info(
                    "[QQOfficialUtil] %s 使用 c2c 接口发送: openid=%s",
                    command_name,
                    raw_message.author.user_openid,
                )
                ret = await event.bot.api.post_c2c_message(
                    openid=raw_message.author.user_openid,
                    **payload,
                )
                logger.info(
                    "[QQOfficialUtil] %s c2c API 返回: %s",
                    command_name,
                    _debug_json(ret),
                )
            else:
                logger.warning(
                    "[QQOfficialUtil] %s 不支持的 raw_message 类型: %s",
                    command_name,
                    debug_context["raw_message_class"],
                )
                yield event.plain_result(
                    "该指令仅支持群聊和 C2C 消息类型。"
                )
                return
        except Exception as exc:
            logger.exception("[QQOfficialUtil] %s 发送按钮消息失败: %s", command_name, exc)
            yield event.plain_result(f"发送按钮消息失败：{exc}")
            return

        logger.info("[QQOfficialUtil] %s 发送流程结束，停止事件传播。", command_name)
        event.stop_event()

    @filter.command("qqofficial_button_a")
    async def qqofficial_button_a(self, event: AstrMessageEvent):
        logger.info(
            "[QQOfficialUtil] qqofficial_button_a 触发: event_class=%s.%s, platform=%r",
            type(event).__module__,
            type(event).__name__,
            event.get_platform_name() if hasattr(event, "get_platform_name") else None,
        )
        yield event.plain_result("你按了 A")
        event.stop_event()

    @filter.command("qqofficial_button_b")
    async def qqofficial_button_b(self, event: AstrMessageEvent):
        logger.info(
            "[QQOfficialUtil] qqofficial_button_b 触发: event_class=%s.%s, platform=%r",
            type(event).__module__,
            type(event).__name__,
            event.get_platform_name() if hasattr(event, "get_platform_name") else None,
        )
        yield event.plain_result("你按了 B")
        event.stop_event()

    @filter.command("开房")
    async def open_room_menu_command(self, event: AstrMessageEvent):
        """打开开房按钮菜单。"""
        async for result in self._handle_open_room(event):
            yield result

    @filter.command("开房菜单")
    async def open_room_named_menu_command(self, event: AstrMessageEvent):
        """打开开房按钮菜单。"""
        async for result in self._handle_open_room(event):
            yield result

    @filter.command("开房创建")
    async def open_room_create_command(self, event: AstrMessageEvent):
        """创建当前群可见的开房条目。"""
        async for result in self._handle_open_room(event):
            yield result

    @filter.command("开房查找")
    async def open_room_find_command(self, event: AstrMessageEvent):
        """查找当前群未过期的开房条目。"""
        async for result in self._handle_open_room(event):
            yield result

    @filter.command("开房加入")
    async def open_room_join_command(self, event: AstrMessageEvent):
        """加入指定识别码的开房条目。"""
        async for result in self._handle_open_room(event):
            yield result

    @filter.command("开房删除")
    async def open_room_delete_command(self, event: AstrMessageEvent):
        """删除自己创建的开房条目。"""
        async for result in self._handle_open_room(event):
            yield result

    @filter.command("subai")
    async def subai_menu_command(self, event: AstrMessageEvent):
        """打开 SubAI 按钮菜单。"""
        async for result in self._handle_subai(event):
            yield result

    @filter.command("SubAI")
    async def subai_capital_menu_command(self, event: AstrMessageEvent):
        """打开 SubAI 按钮菜单。"""
        async for result in self._handle_subai(event):
            yield result

    @filter.command("subai菜单")
    async def subai_named_menu_command(self, event: AstrMessageEvent):
        """打开 SubAI 按钮菜单。"""
        async for result in self._handle_subai(event):
            yield result

    @filter.command("subai状态")
    async def subai_status_command(self, event: AstrMessageEvent):
        """查看 SubAI 同步和订阅状态。"""
        async for result in self._handle_subai(event):
            yield result

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("subai订阅")
    async def subai_subscribe_command(self, event: AstrMessageEvent):
        """订阅当前会话的 SubAI 高分模型变化。"""
        async for result in self._handle_subai(event):
            yield result

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("subai取消订阅")
    async def subai_unsubscribe_command(self, event: AstrMessageEvent):
        """取消当前会话的 SubAI 高分模型变化订阅。"""
        async for result in self._handle_subai(event):
            yield result

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("subai检查")
    async def subai_check_command(self, event: AstrMessageEvent):
        """手动同步一次 Artificial Analysis 免费模型榜单。"""
        async for result in self._handle_subai(event):
            yield result

    @filter.command("subai榜单")
    async def subai_rank_command(self, event: AstrMessageEvent):
        """查看 SubAI 模型榜单。"""
        async for result in self._handle_subai(event):
            yield result

    @filter.command("subai模型")
    async def subai_model_command(self, event: AstrMessageEvent):
        """按名称模糊查看单个 SubAI 模型。"""
        async for result in self._handle_subai(event):
            yield result

    async def _handle_open_room(self, event: AstrMessageEvent):
        command_text = self._extract_open_room_command_text(event)
        if command_text is None:
            return
        group_id, user_id = self._open_room_group_and_user(event)
        if not group_id or not user_id:
            yield event.plain_result("开房插件只能在 QQOfficial 群聊中使用。")
            event.stop_event()
            return
        try:
            message, entries, keyboard_kind = await self._dispatch_open_room_command(
                command_text,
                group_id,
                user_id,
            )
        except ValueError as exc:
            message, entries, keyboard_kind = f"操作失败：{exc}", [], "menu"
        except (aiosqlite.Error, OSError):
            logger.exception("[QQOfficialUtil] 开房数据库操作失败。")
            message, entries, keyboard_kind = "数据库暂时不可用，请稍后重试。", [], "menu"

        payload = _build_open_room_message_payload(
            message,
            entries=entries,
            kind=keyboard_kind,
        )
        async for result in self._send_open_room_group_markdown(event, payload=payload):
            yield result
        event.stop_event()

    async def _dispatch_open_room_command(
        self,
        command_text: str,
        group_id: str,
        user_id: str,
    ) -> tuple[str, list[OpenRoomEntry], str]:
        action, payload = self._split_open_room_action(command_text)
        if action in {"", "菜单", "帮助"}:
            return _open_room_help_text(), [], "menu"
        if action == "创建":
            if not payload:
                return _open_room_create_help_text(), [], "create"
            entry = await self.open_room_store.create_entry(
                group_id=group_id,
                owner_id=user_id,
                **parse_create_payload(payload),
            )
            return "开房创建成功。\n\n" + _render_open_room_entry(entry), [entry], "entry"
        if action in {"查找", "搜索", "列表"}:
            entries = await self.open_room_store.find_entries(group_id, payload)
            if not entries:
                return "没有找到可用房间。\n\n可以点“创建短期房”发起一个。", [], "menu"
            lines = [f"找到 {len(entries)} 个房间："]
            lines.extend(_render_open_room_entry(entry) for entry in entries)
            return "\n\n".join(lines), entries, "entries"
        if action == "加入":
            code = payload.split(maxsplit=1)[0] if payload else ""
            if not code:
                raise ValueError(f"请提供房间识别码，例如：{OPEN_ROOM_JOIN_TEMPLATE}")
            entry = await self.open_room_store.join_entry(group_id, code, user_id)
            return "加入成功。\n\n" + _render_open_room_entry(entry), [entry], "entry"
        if action == "删除":
            code = payload.split(maxsplit=1)[0] if payload else ""
            if not code:
                raise ValueError(f"请提供房间识别码，例如：{OPEN_ROOM_DELETE_TEMPLATE}")
            deleted = await self.open_room_store.delete_entry(group_id, code, user_id)
            if not deleted:
                raise ValueError("房间不存在，或你不是房主。")
            return "房间已删除。", [], "menu"
        raise ValueError("未知开房指令。发送“开房”查看按钮菜单。")

    async def _send_open_room_group_markdown(
        self,
        event: AstrMessageEvent,
        *,
        payload: dict[str, Any],
    ):
        if not _is_qqofficial_message_event(event):
            yield event.plain_result("该指令仅支持 QQOfficial 群聊。")
            return
        raw_message = getattr(event.message_obj, "raw_message", None)
        group_openid = self._extract_open_room_group_openid(event)
        if raw_message is None or not group_openid:
            yield event.plain_result(payload["markdown"].content)
            return
        _add_passive_reply_context(
            payload,
            msg_id=_extract_message_reference_id(raw_message, event.message_obj),
            msg_seq=getattr(raw_message, "msg_seq", None),
        )
        logger.info("[QQOfficialUtil] 开房最终发送 payload: %s", _debug_json(payload))
        try:
            await event.bot.api.post_group_message(group_openid=group_openid, **payload)
        except Exception as exc:
            logger.exception("[QQOfficialUtil] 发送开房按钮消息失败: %s", exc)
            yield event.plain_result(f"发送开房按钮失败：{exc}\n\n{payload['markdown'].content}")

    def _extract_open_room_command_text(self, event: AstrMessageEvent) -> str | None:
        if event.get_platform_name() not in QQOFFICIAL_PLATFORMS:
            return None
        if not self._starts_with_bot_mention(event):
            return None
        text = (event.get_message_str() or "").strip()
        if text.startswith(OPEN_ROOM_COMMAND_PREFIX):
            return text
        return None

    def _split_open_room_action(self, command_text: str) -> tuple[str, str]:
        remainder = command_text[len(OPEN_ROOM_COMMAND_PREFIX) :].strip()
        if not remainder:
            return "", ""
        parts = remainder.split(maxsplit=1)
        return parts[0], parts[1].strip() if len(parts) > 1 else ""

    def _open_room_group_and_user(self, event: AstrMessageEvent) -> tuple[str, str]:
        return self._extract_open_room_group_openid(event), self._extract_open_room_user_openid(event)

    def _extract_open_room_group_openid(self, event: AstrMessageEvent) -> str:
        raw_message = getattr(event.message_obj, "raw_message", None)
        return _first_non_empty_str(
            getattr(raw_message, "group_openid", None),
            getattr(raw_message, "group_id", None),
            event.get_group_id() if hasattr(event, "get_group_id") else None,
        ) or ""

    def _extract_open_room_user_openid(self, event: AstrMessageEvent) -> str:
        raw_message = getattr(event.message_obj, "raw_message", None)
        author = getattr(raw_message, "author", None)
        return _first_non_empty_str(
            getattr(author, "member_openid", None),
            getattr(raw_message, "group_member_openid", None),
            event.get_sender_id() if hasattr(event, "get_sender_id") else None,
        ) or ""

    async def _handle_subai(self, event: AstrMessageEvent):
        command_text = self._extract_subai_command_text(event)
        if command_text is None:
            return
        if not _is_qqofficial_message_event(event):
            yield event.plain_result("SubAI 实验入口仅支持 QQOfficial 群聊。")
            event.stop_event()
            return
        group_openid = self._extract_open_room_group_openid(event)
        if not group_openid:
            yield event.plain_result("SubAI 实验入口只能在 QQOfficial 群聊中使用。")
            event.stop_event()
            return
        try:
            message, keyboard_kind, image_path = await self._dispatch_subai_command(
                command_text,
                event,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("[QQOfficialUtil] SubAI 指令处理失败: %s", exc)
            message, keyboard_kind, image_path = f"SubAI 操作失败：{exc}", "menu", None

        if image_path:
            try:
                yield event.chain_result(MessageChain().file_image(image_path).chain)
                event.stop_event()
                return
            except Exception as exc:  # noqa: BLE001
                logger.warning("[QQOfficialUtil] SubAI 图片回复失败，回退 Markdown: %s", exc)

        payload = _build_subai_message_payload(message, kind=keyboard_kind)
        async for result in self._send_subai_group_markdown(event, payload=payload):
            yield result
        event.stop_event()

    async def _dispatch_subai_command(
        self,
        command_text: str,
        event: AstrMessageEvent,
    ) -> tuple[str, str, str | None]:
        action, payload = self._split_subai_action(command_text)
        if action in {"", "菜单", "帮助", "help", "menu"}:
            return _subai_menu_text(), "menu", None
        if action in {"状态", "status"}:
            return await self.subai_runtime.status(event.unified_msg_origin), "menu", None
        if action in {"订阅", "subscribe"}:
            return await self.subai_runtime.subscribe(event.unified_msg_origin), "menu", None
        if action in {"取消订阅", "unsubscribe"}:
            return await self.subai_runtime.unsubscribe(event.unified_msg_origin), "menu", None
        if action in {"检查", "check"}:
            return await self.subai_runtime.manual_check(), "menu", None
        if action in {"冷却", "cooldown"}:
            return await self.subai_runtime.manual_cooldown_hint(), "menu", None
        if action in {"榜单", "rank"}:
            metric, limit = self._parse_subai_rank_payload(payload)
            result = await self.subai_runtime.rank(metric, limit)
            return result.text, "rank", result.image_path
        if action in {"模型", "model"}:
            return await self.subai_runtime.model_detail(payload), "rank", None
        return "未知 SubAI 指令。发送“subai”查看按钮菜单。", "menu", None

    def _parse_subai_rank_payload(self, payload: str) -> tuple[str, str | None]:
        parts = payload.split()
        metric = parts[0].strip().lower() if parts else "intelligence"
        if metric not in VALID_RANK_METRICS:
            metric = parts[0].strip().lower() if parts else "intelligence"
        limit = parts[1].strip() if len(parts) > 1 else None
        return metric, limit

    async def _send_subai_group_markdown(
        self,
        event: AstrMessageEvent,
        *,
        payload: dict[str, Any],
    ):
        raw_message = getattr(event.message_obj, "raw_message", None)
        group_openid = self._extract_open_room_group_openid(event)
        if raw_message is None or not group_openid:
            yield event.plain_result(payload["markdown"].content)
            return
        _add_passive_reply_context(
            payload,
            msg_id=_extract_message_reference_id(raw_message, event.message_obj),
            msg_seq=getattr(raw_message, "msg_seq", None),
        )
        logger.info("[QQOfficialUtil] SubAI 最终发送 payload: %s", _debug_json(payload))
        try:
            await event.bot.api.post_group_message(group_openid=group_openid, **payload)
        except Exception as exc:
            logger.exception("[QQOfficialUtil] 发送 SubAI 按钮消息失败: %s", exc)
            yield event.plain_result(f"发送 SubAI 按钮失败：{exc}\n\n{payload['markdown'].content}")

    def _extract_subai_command_text(self, event: AstrMessageEvent) -> str | None:
        if event.get_platform_name() not in QQOFFICIAL_PLATFORMS:
            return None
        if not self._starts_with_bot_mention(event):
            return None
        text = (event.get_message_str() or "").strip()
        if text.casefold().startswith(SUBAI_COMMAND_PREFIX):
            return text
        return None

    def _split_subai_action(self, command_text: str) -> tuple[str, str]:
        remainder = command_text[len(SUBAI_COMMAND_PREFIX) :].strip()
        if not remainder:
            return "", ""
        parts = remainder.split(maxsplit=1)
        return parts[0], parts[1].strip() if len(parts) > 1 else ""

    def _extract_box_command_text(self, event: AstrMessageEvent) -> str | None:
        if event.get_platform_name() not in QQOFFICIAL_PLATFORMS:
            return None
        if not self._starts_with_bot_mention(event):
            return None
        return event.get_message_str() or ""

    def _starts_with_bot_mention(self, event: AstrMessageEvent) -> bool:
        for component in event.get_messages():
            if isinstance(component, Comp.Plain) and not component.text.strip():
                continue
            return self._is_bot_at(component, event)
        return False

    def _is_bot_at(self, component: Any, event: AstrMessageEvent) -> bool:
        if not isinstance(component, Comp.At):
            return False
        mentioned_id = str(component.qq).strip()
        if mentioned_id.lower() == BOT_AT_MARKER:
            return True
        return mentioned_id in self._get_bot_self_ids(event)

    def _parse_box_target(self, command_text: str) -> str | None:
        match = BOX_COMMAND_PATTERN.fullmatch(command_text)
        if not match:
            return None
        qq = match.group(1).strip()
        if not self._validate_qq(qq):
            return None
        return qq

    async def generate_fake_dox(self, target_qq: str) -> tuple[str, str | None]:
        location = await self._generate_location()
        output = (
            "身份检索完成\n"
            f"账号：{target_qq}\n"
            f"手机：{self._generate_phone()}\n"
            f"IP地址：{self._generate_ip()}\n"
            f"物理地址：{location.address}\n"
            "说明：以上信息均为随机生成，仅供娱乐。"
        )
        return output, location.map_url

    def _load_location_data(self) -> None:
        data_path = Path(__file__).resolve().parent / "china_clean_v2.json"
        try:
            if not data_path.exists():
                logger.warning(f"[QQOfficialUtil] 未找到地理位置文件：{data_path}")
                return

            with data_path.open("r", encoding="utf-8") as file:
                self.location_data = json.load(file)

            if not isinstance(self.location_data, dict):
                logger.warning("[QQOfficialUtil] 地理位置数据格式无效，应为字典")
                self.location_data = {}
                return

            self.location_pool = self._flatten_locations(self.location_data)
            self.search_region_pool = self._flatten_search_regions(self.location_data)
            logger.info(
                f"[QQOfficialUtil] 已加载 {len(self.location_pool)} 条地理位置数据"
            )
        except json.JSONDecodeError as exc:
            logger.error(f"[QQOfficialUtil] 解析地理位置 JSON 失败：{exc}")
            self.location_data = {}
            self.location_pool = []
            self.search_region_pool = []
        except Exception as exc:
            logger.error(f"[QQOfficialUtil] 加载地理位置数据失败：{exc}")
            self.location_data = {}
            self.location_pool = []
            self.search_region_pool = []

    def _flatten_locations(self, data: dict) -> list[str]:
        locations: list[str] = []
        for provinces in data.values():
            if not isinstance(provinces, dict):
                continue

            for province_name, cities in provinces.items():
                if not isinstance(cities, dict):
                    locations.append(str(province_name))
                    continue

                for city_name, districts in cities.items():
                    if not isinstance(districts, dict) or not districts:
                        locations.append(f"{province_name}{city_name}")
                        continue

                    for district_name, streets in districts.items():
                        if not isinstance(streets, dict) or not streets:
                            locations.append(
                                f"{province_name}{city_name}{district_name}"
                            )
                            continue

                        for street_name in streets.keys():
                            locations.append(
                                f"{province_name}{city_name}{district_name}{street_name}"
                            )

        return locations

    def _flatten_search_regions(self, data: dict) -> list[dict[str, str]]:
        regions: list[dict[str, str]] = []
        for provinces in data.values():
            if not isinstance(provinces, dict):
                continue

            for province_name, cities in provinces.items():
                if not isinstance(cities, dict):
                    continue

                for city_name, districts in cities.items():
                    if not isinstance(districts, dict) or not districts:
                        regions.append(
                            {
                                "region": str(city_name),
                                "prefix": f"{province_name}{city_name}",
                            }
                        )
                        continue

                    for district_name, streets in districts.items():
                        street_name = self._pick_street_name(streets)
                        prefix = f"{province_name}{city_name}{district_name}"
                        if street_name:
                            prefix += street_name
                        regions.append(
                            {
                                "region": str(city_name),
                                "prefix": prefix,
                            }
                        )

        return regions

    def _pick_street_name(self, streets: object) -> str:
        if not isinstance(streets, dict) or not streets:
            return ""
        return str(random.choice(list(streets.keys())))

    def _get_bot_self_ids(self, event: AstrMessageEvent) -> set[str]:
        self_ids = {BOT_AT_MARKER}
        raw_message = getattr(event.message_obj, "raw_message", None)
        if isinstance(raw_message, dict):
            self_id = raw_message.get("self_id")
            if self_id:
                self_ids.add(str(self_id))

        message_self_id = getattr(event.message_obj, "self_id", None)
        if message_self_id:
            self_ids.add(str(message_self_id))

        try:
            self_id = event.get_self_id()
        except Exception as exc:
            logger.debug(f"[QQOfficialUtil] 读取 event.get_self_id 失败：{exc}")
        else:
            if self_id:
                self_ids.add(str(self_id))
        return self_ids

    def _validate_qq(self, qq: str) -> bool:
        if not qq or not isinstance(qq, str):
            return False
        if not qq.isdigit():
            logger.warning(f"[QQOfficialUtil] 检测到无效 QQ 格式：{qq}")
            return False
        return True

    def _is_user_allowed(self, user_id: str | None) -> bool:
        if not user_id:
            return True

        mode = str(self.config.get("user_list_mode", "none")).lower()
        if mode not in {"whitelist", "blacklist", "none"}:
            mode = "none"
        if mode == "none":
            return True

        user_list = {str(item) for item in self.config.get("user_list", [])}
        is_in_list = str(user_id) in user_list
        if mode == "whitelist":
            return is_in_list
        if mode == "blacklist":
            return not is_in_list
        return True

    def _generate_phone(self) -> str:
        prefixes = [
            "130",
            "131",
            "132",
            "133",
            "135",
            "136",
            "137",
            "138",
            "139",
            "150",
            "151",
            "152",
            "155",
            "156",
            "157",
            "158",
            "159",
            "166",
            "177",
            "180",
            "181",
            "182",
            "183",
            "184",
            "185",
            "186",
            "187",
            "188",
            "189",
            "198",
            "199",
        ]
        prefix = random.choice(prefixes)
        suffix = "".join(str(random.randint(0, 9)) for _ in range(8))
        return f"{prefix}{suffix}"

    def _generate_ip(self) -> str:
        first = random.choice(
            [
                58,
                61,
                110,
                112,
                113,
                114,
                115,
                116,
                117,
                118,
                119,
                120,
                121,
                122,
                123,
                124,
                125,
                126,
                127,
                172,
                192,
            ]
        )
        second = random.randint(1, 255)
        third = random.randint(0, 255)
        fourth = random.randint(1, 254)
        return f"{first}.{second}.{third}.{fourth}"

    async def _generate_location(self) -> GeneratedLocation:
        if not self._is_map_enrichment_enabled():
            return GeneratedLocation(self._generate_fallback_location())

        api_key = self._get_tencent_map_key()
        if not api_key:
            logger.warning("[QQOfficialUtil] 已启用地图增强，但未配置 tencent_map_key")
            return GeneratedLocation(self._generate_fallback_location())

        region = self._pick_search_region()
        if not region:
            logger.warning("[QQOfficialUtil] 未加载到可搜索地区，回退本地随机地址")
            return GeneratedLocation(self._generate_fallback_location())

        poi = await self._search_random_poi(api_key, region["region"])
        if not poi:
            return GeneratedLocation(region["prefix"])

        address = self._format_poi_address(region["prefix"], poi)
        map_url = self._build_static_map_url(api_key, poi)
        return GeneratedLocation(address, map_url)

    def _generate_fallback_location(self) -> str:
        if self.location_pool:
            return random.choice(self.location_pool)
        return "四川省成都市金牛区"

    def _is_map_enrichment_enabled(self) -> bool:
        return bool(self._get_map_config("enable_static_map", False))

    def _get_tencent_map_key(self) -> str:
        return str(
            self._get_map_config("tencent_map_key", "")
            or os.getenv("TENCENT_MAP_KEY")
            or ""
        ).strip()

    def _get_tencent_map_sk(self) -> str:
        return str(
            self._get_map_config("tencent_map_sk", "")
            or os.getenv("TENCENT_MAP_SK")
            or ""
        ).strip()

    def _pick_search_region(self) -> dict[str, str] | None:
        if not self.search_region_pool:
            return None
        return random.choice(self.search_region_pool)

    async def _search_random_poi(
        self, api_key: str, region_name: str
    ) -> dict | None:
        page_size = self._get_int_config("place_search_page_size", 10, 1, 20)
        keywords = self._pick_place_keywords_for_search()
        for keyword in keywords:
            params = {
                "key": api_key,
                "keyword": keyword,
                "boundary": f"region({region_name},1)",
                "page_size": str(page_size),
                "page_index": "1",
                "output": "json",
            }
            url = self._build_tencent_get_url(TENCENT_MAP_PLACE_SEARCH_PATH, params)
            try:
                payload = await self._http_get_json(url)
            except Exception as exc:
                logger.warning(f"[QQOfficialUtil] 腾讯地图地点搜索失败：{exc}")
                return None

            if not isinstance(payload, dict) or payload.get("status") != 0:
                logger.warning(
                    "[QQOfficialUtil] 腾讯地图地点搜索返回异常："
                    f"{self._summarize_api_payload(payload)}"
                )
                return None

            pois = payload.get("data")
            if not isinstance(pois, list) or not pois:
                continue
            valid_pois = [poi for poi in pois if isinstance(poi, dict)]
            if valid_pois:
                return random.choice(valid_pois)
        return None

    def _pick_place_keywords_for_search(self) -> list[str]:
        keywords = self._get_map_config("place_search_keywords", DEFAULT_PLACE_KEYWORDS)
        if not isinstance(keywords, list):
            keywords = DEFAULT_PLACE_KEYWORDS
        normalized = [str(item).strip() for item in keywords if str(item).strip()]
        if not normalized:
            normalized = DEFAULT_PLACE_KEYWORDS
        random.shuffle(normalized)
        retry_count = self._get_int_config(
            "place_search_retry_keywords", 4, 1, len(normalized)
        )
        return normalized[:retry_count]

    async def _http_get_json(self, url: str) -> dict:
        timeout = self._get_int_config("tencent_api_timeout", 5, 1, 30)

        def _request() -> dict:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "astrbot-plugin-util-official/1.1"},
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                body = response.read().decode(charset)
            return json.loads(body)

        return await asyncio.to_thread(_request)

    def _format_poi_address(self, region_prefix: str, poi: dict) -> str:
        title = str(poi.get("title") or "").strip()
        address = str(poi.get("address") or "").strip()
        if address and title:
            return f"{address}（{title}）"
        if title:
            return f"{region_prefix}{title}"
        return address or region_prefix

    def _build_static_map_url(self, api_key: str, poi: dict) -> str | None:
        location = poi.get("location")
        if not isinstance(location, dict):
            return None
        lat = location.get("lat")
        lng = location.get("lng")
        if lat is None or lng is None:
            return None

        zoom = self._get_int_config("static_map_zoom", 17, 4, 18)
        size = str(self._get_map_config("static_map_size", "500x400")).strip() or "500x400"
        marker_style = (
            str(self._get_map_config("static_map_marker_style", "size:large|color:red"))
            .strip()
            .strip("|")
        )
        params = {
            "key": api_key,
            "center": f"{lat},{lng}",
            "zoom": str(zoom),
            "size": size,
        }
        if marker_style:
            params["markers"] = f"{marker_style}|{lat},{lng}"
        return self._build_tencent_get_url(TENCENT_MAP_STATIC_PATH, params)

    def _build_tencent_get_url(self, path: str, params: dict[str, str]) -> str:
        request_params = dict(params)
        secret_key = self._get_tencent_map_sk()
        if secret_key:
            request_params["sig"] = self._sign_tencent_get(path, params, secret_key)
        query = urllib.parse.urlencode(request_params)
        return f"{TENCENT_MAP_API_BASE}{path}?{query}"

    def _sign_tencent_get(
        self, path: str, params: dict[str, str], secret_key: str
    ) -> str:
        raw_query = "&".join(f"{key}={params[key]}" for key in sorted(params.keys()))
        source = f"{path}?{raw_query}{secret_key}"
        return hashlib.md5(source.encode("utf-8")).hexdigest()

    def _get_map_config(self, key: str, default=None):
        tencent_map = self.config.get("tencent_map", {})
        if hasattr(tencent_map, "get"):
            value = tencent_map.get(key, None)
            if value is not None:
                return value
        return self.config.get(key, default)

    def _get_subai_config(self, key: str, default=None):
        subai = self.config.get("subai", {})
        if hasattr(subai, "get"):
            value = subai.get(key, None)
            if value is not None:
                return value
        prefixed_key = f"subai_{key}"
        return self.config.get(prefixed_key, self.config.get(key, default))

    def _build_subai_config(self) -> SubAIConfig:
        return SubAIConfig.from_mapping(
            {
                "api_key": self._get_subai_config("api_key", ""),
                "poll_interval_minutes": self._get_subai_config("poll_interval_minutes", 120),
                "intelligence_threshold": self._get_subai_config("intelligence_threshold", 47.0),
                "request_timeout_seconds": self._get_subai_config("request_timeout_seconds", 20),
                "max_retries": self._get_subai_config("max_retries", 2),
                "card_theme": self._get_subai_config("card_theme", "analytics"),
            }
        )

    def _summarize_api_payload(self, payload) -> str:
        if not isinstance(payload, dict):
            return repr(payload)[:300]
        summary = {
            "status": payload.get("status"),
            "message": payload.get("message"),
            "count": payload.get("count"),
            "request_id": payload.get("request_id"),
        }
        return json.dumps(summary, ensure_ascii=False)

    def _get_int_config(
        self, key: str, default: int, minimum: int, maximum: int
    ) -> int:
        try:
            value = int(self._get_map_config(key, default))
        except (TypeError, ValueError):
            return default
        return max(minimum, min(maximum, value))

    async def terminate(self):
        await self.subai_runtime.terminate()
        tasks = list(getattr(self, "_background_tasks", set()))
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
