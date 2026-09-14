"""Parsing and validation helpers for open-room commands."""

from __future__ import annotations

import unicodedata

MAX_LOCATOR_LENGTH = 512
MAX_GAME_LENGTH = 120
MAX_NOTE_LENGTH = 1000
MAX_SEARCH_LENGTH = 500


def parse_create_payload(payload: str) -> dict[str, object]:
    parts = [part.strip() for part in _canonical_separators(payload).split("｜")]
    if len(parts) < 2 or not parts[0] or not parts[1]:
        raise ValueError("房间信息和游戏/平台为必填项。")
    _check_length(parts[0], MAX_LOCATOR_LENGTH, "房间信息")
    _check_length(parts[1], MAX_GAME_LENGTH, "游戏/平台")
    result: dict[str, object] = {
        "locator_text": parts[0],
        "game_or_platform": parts[1],
        "note": "",
        "initial_count": 1,
        "max_count": None,
        "is_long_term": False,
    }
    seen: set[str] = set()
    for part in parts[2:]:
        if not part:
            continue
        if part in {"长期", "长", "短期", "短"}:
            _set_once(seen, "有效期")
            result["is_long_term"] = part in {"长期", "长"}
            continue
        field, value = _split_named_field(part)
        if field == "备注":
            _set_once(seen, field)
            _check_length(value, MAX_NOTE_LENGTH, "备注")
            result["note"] = value
        elif field == "初始":
            _set_once(seen, field)
            result["initial_count"] = _parse_non_negative_int(value, "初始")
        elif field == "上限":
            _set_once(seen, field)
            result["max_count"] = _parse_limit(value)
        else:
            raise ValueError(f"无法识别字段“{part}”。可使用 备注=、初始=、上限=、长期。")
    initial = int(result["initial_count"])
    limit = result["max_count"]
    if isinstance(limit, int) and initial > limit:
        raise ValueError("初始人数不能大于上限。")
    return result


def parse_search_query(query: str) -> list[list[str]]:
    if len(query) > MAX_SEARCH_LENGTH:
        raise ValueError(f"搜索内容不能超过 {MAX_SEARCH_LENGTH} 个字符。")
    groups: list[list[str]] = []
    for block in _canonical_separators(query).split("｜"):
        alternatives = [
            normalize_search_text(term) for term in block.replace("／", "/").split("/")
        ]
        alternatives = [term for term in alternatives if term]
        if alternatives:
            groups.append(alternatives)
    return groups


def normalize_search_text(text: str) -> str:
    return "".join(unicodedata.normalize("NFKC", text).casefold().split())


def make_search_text(game_or_platform: str, note: str) -> str:
    return normalize_search_text(f"{game_or_platform} {note}")


def _canonical_separators(value: str) -> str:
    return value.replace("|", "｜")


def _split_named_field(part: str) -> tuple[str, str]:
    for separator in ("=", "＝", "：", ":"):
        if separator in part:
            field, value = part.split(separator, 1)
            return field.strip(), value.strip()
    raise ValueError(f"无法识别字段“{part}”。可使用 备注=、初始=、上限=、长期。")


def _set_once(seen: set[str], field: str) -> None:
    if field in seen:
        raise ValueError(f"字段“{field}”不能重复。")
    seen.add(field)


def _check_length(value: str, maximum: int, field_name: str) -> None:
    if not value:
        raise ValueError(f"{field_name}不能为空。")
    if len(value) > maximum:
        raise ValueError(f"{field_name}不能超过 {maximum} 个字符。")


def _parse_non_negative_int(value: str, field_name: str) -> int:
    try:
        number = int(value.strip())
    except ValueError as exc:
        raise ValueError(f"{field_name}必须是非负整数。") from exc
    if number < 0:
        raise ValueError(f"{field_name}必须是非负整数。")
    return number


def _parse_limit(value: str) -> int | None:
    normalized = value.strip().lower()
    if normalized in {"∞", "inf", "infinity", "无限"}:
        return None
    number = _parse_non_negative_int(normalized, "上限")
    if number == 0:
        raise ValueError("上限必须是正整数或∞。")
    return number
