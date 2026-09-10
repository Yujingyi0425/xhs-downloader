"""C7C 浏览器任务边界遥测的服务端白名单。"""

from typing import Any

from pydantic import JsonValue

_MANIFEST_VERSION = "3.0.0"
_DIAGNOSTIC_SCHEMA_VERSION = "C7C-1"
_DETAIL_WAIT_RESULTS = frozenset({"PASS", "FAIL", "NOT_APPLICABLE", "NOT_REACHED"})
_PAGE_RESPONSE_CLASSES = frozenset(
    {"SUCCESS", "PAGE_TASK_ERROR", "INVALID_RESPONSE", "NO_RESPONSE", "NOT_REACHED"}
)
_SEND_MESSAGE_FAILURE_CLASSES = frozenset(
    {
        "NO_RECEIVER",
        "PORT_CLOSED",
        "RUNTIME_ERROR",
        "TAB_REMOVED",
        "UNKNOWN",
        "NOT_APPLICABLE",
    }
)
_LAST_COMPLETED_BOUNDARIES = frozenset(
    {
        "TASK_CLAIMED",
        "TARGET_TAB_CREATED",
        "DETAIL_WAIT_STARTED",
        "DETAIL_READY",
        "SEND_MESSAGE_ATTEMPTED",
        "SEND_MESSAGE_RESOLVED",
        "CONTENT_SCRIPT_RESPONSE_RECEIVED",
        "PAGE_RESPONSE_PARSED",
        "EXTENSION_RESULT_BUILT",
        "RESULT_SUBMIT_ATTEMPTED",
        "RESULT_SUBMITTED",
    }
)
_BOOLEAN_FIELDS = (
    "target_tab_created",
    "detail_wait_started",
    "send_message_attempted",
    "send_message_resolved",
    "send_message_rejected",
    "content_script_message_received",
    "page_task_started",
    "parser_invocation_started",
    "content_script_response_received",
    "extension_result_built",
    "result_submit_attempted",
    "result_submit_resolved",
    "result_submit_rejected",
)


def sanitize_browser_runtime_telemetry(
    value: dict[str, Any] | None,
) -> dict[str, JsonValue] | None:
    """裁剪 C7C 遥测，只保留固定版本、枚举和布尔值。

    Args:
        value: 扩展提交的原始遥测对象。

    Returns:
        通过白名单校验的遥测对象，或 ``None``。
    """
    if not isinstance(value, dict):
        return None
    if (
        value.get("extension_manifest_version") != _MANIFEST_VERSION
        or value.get("diagnostic_schema_version") != _DIAGNOSTIC_SCHEMA_VERSION
    ):
        return None
    result: dict[str, JsonValue] = {
        "extension_manifest_version": _MANIFEST_VERSION,
        "diagnostic_schema_version": _DIAGNOSTIC_SCHEMA_VERSION,
    }
    for field in _BOOLEAN_FIELDS:
        if type(value.get(field)) is bool:
            result[field] = value[field]
    for field, allowed in (
        ("detail_wait_result", _DETAIL_WAIT_RESULTS),
        ("page_response_class", _PAGE_RESPONSE_CLASSES),
        ("send_message_failure_class", _SEND_MESSAGE_FAILURE_CLASSES),
        ("last_completed_runtime_boundary", _LAST_COMPLETED_BOUNDARIES),
    ):
        item = value.get(field)
        if isinstance(item, str) and item in allowed:
            result[field] = item
    return result if len(result) > 2 else None


def mark_browser_runtime_telemetry_submitted(
    diagnostics: dict[str, JsonValue] | None,
) -> dict[str, JsonValue] | None:
    """在服务端接受失败 envelope 后标记 result submit 已完成。

    Args:
        diagnostics: 终态结果中的诊断对象。

    Returns:
        带有服务端提交完成标记的诊断对象。
    """
    if not isinstance(diagnostics, dict):
        return None
    telemetry = sanitize_browser_runtime_telemetry(
        diagnostics.get("browser_runtime_telemetry")
    )
    if telemetry is None:
        return diagnostics
    telemetry["result_submit_resolved"] = True
    telemetry["result_submit_rejected"] = False
    telemetry["last_completed_runtime_boundary"] = "RESULT_SUBMITTED"
    return {**diagnostics, "browser_runtime_telemetry": telemetry}
