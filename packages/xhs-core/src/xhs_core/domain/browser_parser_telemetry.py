"""浏览器详情 parser 遥测的服务端白名单。"""

from typing import Any

from pydantic import JsonValue

_MAX_PARSER_DIAGNOSTIC_COUNT = 1_000
_KNOWN_INITIAL_STATE_RESULTS = frozenset(
    {"PARSED", "MISSING", "INVALID", "UNEXPECTED_SHAPE"}
)
_KNOWN_WRAPPER_MATCH_MODES = frozenset(
    {"EXACT_KEY", "NOTE_ID_SCAN", "NONE", "NOT_REACHED"}
)
_KNOWN_NOTE_TYPES = frozenset({"IMAGE", "VIDEO", "UNKNOWN", "NOT_REACHED"})
_KNOWN_PARSER_BOUNDARIES = frozenset(
    {
        "NONE",
        "INITIAL_STATE_PARSED",
        "NOTE_ROOT_FOUND",
        "NOTE_DETAIL_MAP_FOUND",
        "TARGET_WRAPPER_FOUND",
        "TARGET_NOTE_FOUND",
        "TARGET_IDENTITY_MATCHED",
        "AUTHOR_VALIDATED",
        "MEDIA_FIELDS_VALIDATED",
        "PARSE_COMPLETE",
    }
)
_KNOWN_PARSER_FAILURE_SUBTYPES = frozenset(
    {
        "NONE",
        "INITIAL_STATE_MISSING",
        "INITIAL_STATE_PARSE_FAILED",
        "NOTE_ROOT_MISSING",
        "NOTE_DETAIL_MAP_MISSING",
        "TARGET_WRAPPER_NOT_FOUND",
        "TARGET_NOTE_MISSING",
        "TARGET_NOTE_ID_MISMATCH",
        "AUTHOR_MISSING",
        "AUTHOR_ID_MISSING",
        "UNEXPECTED_PARSER_EXCEPTION",
    }
)
_KNOWN_EXCEPTION_CLASSES = frozenset(
    {"TypeError", "Error", "SyntaxError", "Unknown", "NONE"}
)


def sanitize_parser_telemetry(value: Any) -> dict[str, JsonValue] | None:
    """只保留 parser 的固定枚举、布尔值和有界数量。

    Args:
        value: 扩展返回的未知 parser 遥测对象。

    Returns:
        通过白名单的遥测对象；没有安全字段时返回 ``None``。
    """
    if not isinstance(value, dict):
        return None
    diagnostics: dict[str, JsonValue] = {}
    text_fields = {
        "initial_state_parse_result": _KNOWN_INITIAL_STATE_RESULTS,
        "target_wrapper_match_mode": _KNOWN_WRAPPER_MATCH_MODES,
        "normalized_note_type": _KNOWN_NOTE_TYPES,
        "last_completed_parser_boundary": _KNOWN_PARSER_BOUNDARIES,
        "parser_failure_subtype": _KNOWN_PARSER_FAILURE_SUBTYPES,
        "safe_exception_class": _KNOWN_EXCEPTION_CLASSES,
    }
    for field, allowed in text_fields.items():
        parsed = _known_text(value.get(field), allowed)
        if parsed is not None:
            diagnostics[field] = parsed
    for field in (
        "initial_state_anchor_present",
        "note_root_present",
        "note_detail_map_present",
        "target_wrapper_found",
        "target_note_present",
        "target_note_id_match",
        "author_object_present",
        "author_id_present",
        "image_list_present",
    ):
        parsed = _known_boolean(value.get(field))
        if parsed is not None:
            diagnostics[field] = parsed
    for field in ("note_detail_map_count", "image_list_length"):
        parsed = value.get(field)
        if type(parsed) is int and 0 <= parsed <= _MAX_PARSER_DIAGNOSTIC_COUNT:
            diagnostics[field] = parsed
    return diagnostics or None


def _known_text(value: Any, allowed: frozenset[str]) -> str | None:
    if not isinstance(value, str):
        return None
    return value if value in allowed else None


def _known_boolean(value: Any) -> bool | None:
    if type(value) is bool:
        return value
    return None
