"""浏览器页面失败诊断的服务端白名单规则。"""

from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import JsonValue

from .browser_failure_diagnostics import (
    KNOWN_FAILURE_CLASSES,
    failure_class_for_code,
    missing_browser_failure_diagnostics,
)
from .browser_parser_telemetry import sanitize_parser_telemetry
from .browser_runtime_telemetry import sanitize_browser_runtime_telemetry
from .browser_tasks import BrowserTask, BrowserTaskStatus

_MAX_ADAPTER_VERSION_LENGTH = 32
_MAX_ANCHOR_COUNT = 8
_MAX_INSPECTED_ANCHORS = 16
_KNOWN_ADAPTER_VERSIONS = frozenset({"xhs-web-2026.07"})
_KNOWN_SELECTOR_PROFILES = frozenset(
    {
        "initial-state-v1",
        "semantic-dom-v1",
        "unknown",
    }
)
_KNOWN_PAGE_KINDS = frozenset(
    {
        "home",
        "search",
        "feed_detail",
        "profile",
        "unknown",
    }
)
_KNOWN_ANCHORS = frozenset(
    {
        "initial_state",
        "main_container",
        "feed_container",
        "filter_control",
        "comment_container",
        "detail_container",
        "profile_container",
    }
)
_KNOWN_FAILURE_STAGES = frozenset({"background", "page_parser", "unknown"})
_KNOWN_TAB_STATUSES = frozenset({"loading", "complete", "unknown", "missing"})
_KNOWN_ROUTE_CLASSES = frozenset(
    {
        "/blank",
        "/explore/<feed_id>",
        "/discovery/item/<feed_id>",
        "/board/<board_id>",
        "/other-xhs",
        "/non-xhs",
        "/unknown",
    }
)
_MAX_ELAPSED_MS = 60_000
_KNOWN_FAILURE_CODES = frozenset(
    {
        "DETAIL_NAVIGATION_FAILED",
        "TARGET_TAB_NOT_FOUND",
        "TARGET_TAB_IDENTITY_MISMATCH",
        "CONTENT_SCRIPT_NOT_READY",
        "MESSAGE_DISPATCH_FAILED",
        "MESSAGE_RESPONSE_EMPTY",
        "MEDIA_PARSER_EMPTY",
        "MEDIA_PARSER_ERROR",
        "MEDIA_IDENTITY_MISMATCH",
        "PAGE_TASK_ERROR",
        "RUNTIME_ENVELOPE_MISSING",
    }
)
_SAFE_TERMINAL_MESSAGES = {
    BrowserTaskStatus.FAILED: "浏览器任务执行失败，可安全重试",
    BrowserTaskStatus.NEEDS_REVIEW: "浏览器操作结果无法确认，请人工核对平台状态",
}
_SENSITIVE_BROWSER_FIELDS = frozenset(
    {"authorization", "cookie", "pending_url", "raw_url_query", "xsec_token"}
)


def sanitize_browser_page_diagnostics(
    value: dict[str, Any] | None,
) -> dict[str, JsonValue] | None:
    """把不可信失败结果裁剪为有界页面兼容性诊断。

    只保留与当前内置页面适配器匹配的版本、选择器配置、页面类型、
    已知锚点及媒体任务的有界失败阶段/错误码。URL、令牌、页面原文、
    用户文本和其他扩展字段不会进入返回值。数组读取与输出数量均受限，
    避免恶意超长结果扩张存储。

    Args:
        value: 扩展或受管浏览器返回的未知失败结果。

    Returns:
        通过白名单的有界诊断；没有安全字段时返回 ``None``。
    """
    if not isinstance(value, dict):
        return None
    diagnostics: dict[str, JsonValue] = {}
    adapter_version = _known_text(
        value.get("adapter_version"),
        _KNOWN_ADAPTER_VERSIONS,
        _MAX_ADAPTER_VERSION_LENGTH,
    )
    if adapter_version is not None:
        diagnostics["adapter_version"] = adapter_version
    selector_profile = _known_text(
        value.get("selector_profile"),
        _KNOWN_SELECTOR_PROFILES,
    )
    if selector_profile is not None:
        diagnostics["selector_profile"] = selector_profile
    page_kind = _known_text(value.get("page_kind"), _KNOWN_PAGE_KINDS)
    if page_kind is not None:
        diagnostics["page_kind"] = page_kind
    for field in ("matched_anchors", "missing_anchors"):
        anchors = _known_anchors(value.get(field))
        if anchors is not None:
            diagnostics[field] = anchors
    failure_stage = _known_text(value.get("failure_stage"), _KNOWN_FAILURE_STAGES)
    if failure_stage is not None:
        diagnostics["failure_stage"] = failure_stage
    failure_code = _known_text(value.get("failure_code"), _KNOWN_FAILURE_CODES)
    if failure_code is not None:
        diagnostics["failure_code"] = failure_code
    failure_class = _known_text(value.get("failure_class"), KNOWN_FAILURE_CLASSES)
    if failure_class is None and failure_code is not None:
        failure_class = failure_class_for_code(failure_code)
    if failure_class is not None:
        diagnostics["failure_class"] = failure_class
    parser_telemetry = sanitize_parser_telemetry(value.get("parser_telemetry"))
    if parser_telemetry is not None:
        diagnostics["parser_telemetry"] = parser_telemetry
    runtime_telemetry = sanitize_browser_runtime_telemetry(
        value.get("browser_runtime_telemetry")
    )
    if runtime_telemetry is not None:
        diagnostics["browser_runtime_telemetry"] = runtime_telemetry
    elif any(item is not None for item in (failure_stage, failure_code, failure_class)):
        diagnostics["diagnostic_schema_version"] = "SERVER-1"
        diagnostics["last_completed_runtime_boundary"] = "UNKNOWN"
    for field in (
        "target_tab_exists",
        "url_host_is_xhs",
        "expected_route_matched",
        "tab_removed",
    ):
        boolean = _known_boolean(value.get(field))
        if boolean is not None:
            diagnostics[field] = boolean
    last_tab_status = _known_text(value.get("last_tab_status"), _KNOWN_TAB_STATUSES)
    if last_tab_status is not None:
        diagnostics["last_tab_status"] = last_tab_status
    last_route_class = _known_text(value.get("last_route_class"), _KNOWN_ROUTE_CLASSES)
    if last_route_class is not None:
        diagnostics["last_route_class"] = last_route_class
    elapsed_ms = value.get("elapsed_ms")
    if type(elapsed_ms) is int and 0 <= elapsed_ms <= _MAX_ELAPSED_MS:
        diagnostics["elapsed_ms"] = elapsed_ms
    return diagnostics or None


def sanitize_browser_task_message(
    status: BrowserTaskStatus,
    value: str,
) -> str:
    """清洗浏览器执行器提供的状态消息。

    失败和待人工核对消息可能来自页面异常原文，因此一律替换为服务端
    固定摘要；其他状态仍保留现有的千字符边界。

    Args:
        status: 任务即将进入的状态。
        value: 尚未信任的执行器消息。

    Returns:
        不包含页面输入的受控消息。
    """
    return _SAFE_TERMINAL_MESSAGES.get(status, value[:1000])


def sanitize_stored_browser_task(task: BrowserTask) -> BrowserTask:
    """清洗即将进入或已经来自持久化边界的浏览器任务。

    Args:
        task: 仓储解析出的旧任务快照。

    Returns:
        不含浏览器访问 secret 和敏感请求上下文的任务快照。
    """
    safe_payload = _sanitize_browser_json(task.payload)
    safe_result = (
        sanitize_browser_page_diagnostics(task.result)
        if task.status in _SAFE_TERMINAL_MESSAGES
        else _sanitize_browser_json(task.result)
    )
    if task.status in _SAFE_TERMINAL_MESSAGES and safe_result is None:
        safe_result = missing_browser_failure_diagnostics()
    safe_message = (
        sanitize_browser_task_message(task.status, task.message)
        if task.status in _SAFE_TERMINAL_MESSAGES
        else task.message
    )
    if (
        task.payload == safe_payload
        and task.result == safe_result
        and task.message == safe_message
    ):
        return task
    return task.model_copy(
        update={
            "payload": safe_payload,
            "result": safe_result,
            "message": safe_message,
        }
    )


def sanitize_browser_task_result(
    value: dict[str, Any] | None,
) -> dict[str, JsonValue] | None:
    """移除成功结果中的 secret-bearing 字段和 URL 查询参数。

    Args:
        value: 浏览器执行器返回的成功结果。

    Returns:
        可安全持久化的结果，或空结果。
    """
    sanitized = _sanitize_browser_json(value)
    return sanitized if isinstance(sanitized, dict) else None


def _sanitize_browser_json(value: Any) -> JsonValue | None:
    if isinstance(value, dict):
        return {
            key: _sanitize_browser_json(item)
            for key, item in value.items()
            if key.lower() not in _SENSITIVE_BROWSER_FIELDS
        }
    if isinstance(value, list):
        return [_sanitize_browser_json(item) for item in value]
    if isinstance(value, str):
        return _sanitize_browser_url(value)
    return value


def _sanitize_browser_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.query:
        return value
    safe_query = [
        (key, item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in _SENSITIVE_BROWSER_FIELDS
    ]
    if len(safe_query) == len(parse_qsl(parsed.query, keep_blank_values=True)):
        return value
    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urlencode(safe_query),
            parsed.fragment,
        )
    )


def _known_text(
    value: Any,
    allowed: frozenset[str],
    max_length: int | None = None,
) -> str | None:
    if not isinstance(value, str):
        return None
    if max_length is not None and len(value) > max_length:
        return None
    return value if value in allowed else None


def _known_anchors(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    anchors: list[str] = []
    for item in value[:_MAX_INSPECTED_ANCHORS]:
        if isinstance(item, str) and item in _KNOWN_ANCHORS and item not in anchors:
            anchors.append(item)
            if len(anchors) == _MAX_ANCHOR_COUNT:
                break
    return anchors


def _known_boolean(value: Any) -> bool | None:
    return value if type(value) is bool else None
