"""视频定位器结构诊断的服务端安全白名单。"""

from typing import Any

from pydantic import JsonValue

_KNOWN_MEDIA_LOCATOR_SOURCES = frozenset(
    {
        "NONE",
        "STATIC_STATE",
        "REALTIME_STATE",
        "VIDEO_ELEMENT_CURRENT_SRC",
        "VIDEO_ELEMENT_SRC",
        "SOURCE_ELEMENT_SRC",
    }
)
_KNOWN_MEDIA_URL_HOST_CLASSES = frozenset({"XHS_MEDIA_HOST", "OTHER", "UNKNOWN"})
_KNOWN_MEDIA_URL_PATH_CLASSES = frozenset(
    {"VIDEO_FILE", "VIDEO_STREAM", "XHS_VIDEO_PATH", "UNKNOWN"}
)
_KNOWN_MEDIA_REJECTIONS = frozenset(
    {
        "NO_VIDEO_OBJECT",
        "VIDEO_OBJECT_SCHEMA_UNSUPPORTED",
        "STREAM_OBJECT_MISSING",
        "STREAM_VARIANTS_EMPTY",
        "KNOWN_FIELDS_EMPTY",
        "DOM_VIDEO_ELEMENT_MISSING",
        "DOM_VIDEO_SRC_EMPTY",
        "DOM_SOURCE_SRC_EMPTY",
        "CANDIDATE_REJECTED",
        "UNEXPECTED_MEDIA_SCHEMA",
        "BLOB_ONLY_SOURCE",
        "UNKNOWN",
    }
)
_KNOWN_VIDEO_KEYS_CLASSES = frozenset(
    {"EMPTY", "CONSUMER", "MEDIA", "KNOWN_FIELDS", "OTHER"}
)
_KNOWN_MANAGED_ADAPTER_GENERATIONS = frozenset({"v2"})
_KNOWN_DIAGNOSTIC_SCHEMA_VERSIONS = frozenset({"C7C-1", "MANAGED-2", "SERVER-1"})


def sanitize_managed_runtime_identity(value: Any) -> dict[str, JsonValue] | None:
    """保留受管适配器的固定运行时身份。

    Args:
        value: 扩展返回的未知运行时身份。

    Returns:
        通过白名单的安全身份，或空结果。
    """
    if not isinstance(value, dict):
        return None
    identity: dict[str, JsonValue] = {}
    generation = _known_text(
        value.get("managed_adapter_generation"), _KNOWN_MANAGED_ADAPTER_GENERATIONS
    )
    if generation is None:
        return None
    identity["managed_adapter_generation"] = generation
    schema = _known_text(
        value.get("diagnostic_schema_version"), _KNOWN_DIAGNOSTIC_SCHEMA_VERSIONS
    )
    if schema is not None:
        identity["diagnostic_schema_version"] = schema
    return identity or None


def sanitize_video_parser_diagnostics(value: Any) -> dict[str, JsonValue] | None:
    """保留视频定位器的固定结构字段，不保留地址或页面原文。

    Args:
        value: 扩展返回的未知视频定位诊断。

    Returns:
        通过白名单的安全诊断，或空结果。
    """
    if not isinstance(value, dict):
        return None
    diagnostics: dict[str, JsonValue] = {}
    enum_fields = {
        "initial_state_video_keys_class": _KNOWN_VIDEO_KEYS_CLASSES,
        "locator_candidate_source": _KNOWN_MEDIA_LOCATOR_SOURCES,
        "url_host_class": _KNOWN_MEDIA_URL_HOST_CLASSES,
        "url_path_shape_class": _KNOWN_MEDIA_URL_PATH_CLASSES,
        "locator_rejection_reason": _KNOWN_MEDIA_REJECTIONS,
        "signed_query_present": frozenset({"YES", "NO"}),
    }
    for field, allowed in enum_fields.items():
        parsed = _known_text(value.get(field), allowed)
        if parsed is not None:
            diagnostics[field] = parsed
    for field in (
        "video_src_present",
        "video_current_src_present",
        "source_src_present",
        "initial_state_video_object_present",
        "video_stream_object_present",
        "page_has_initial_state_script",
    ):
        parsed = _known_text(value.get(field), frozenset({"YES", "NO"}))
        if parsed is not None:
            diagnostics[field] = parsed
    for field in ("video_element_count", "source_element_count", "video_variant_count"):
        parsed = value.get(field)
        if type(parsed) is int and 0 <= parsed <= 64:
            diagnostics[field] = parsed
    return diagnostics or None


def _known_text(value: Any, allowed: frozenset[str]) -> str | None:
    if not isinstance(value, str):
        return None
    return value if value in allowed else None
