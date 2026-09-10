"""浏览器任务失败类别与缺失 envelope 的固定摘要。"""

from pydantic import JsonValue

KNOWN_FAILURE_CLASSES = frozenset(
    {
        "DETAIL_NAVIGATION",
        "CONTENT_SCRIPT",
        "PAGE_TASK",
        "PARSER",
        "RUNTIME",
        "RUNTIME_ENVELOPE_MISSING",
        "UNKNOWN",
    }
)
FAILURE_CLASS_BY_CODE = {
    "DETAIL_NAVIGATION_FAILED": "DETAIL_NAVIGATION",
    "TARGET_TAB_NOT_FOUND": "DETAIL_NAVIGATION",
    "TARGET_TAB_IDENTITY_MISMATCH": "DETAIL_NAVIGATION",
    "CONTENT_SCRIPT_NOT_READY": "CONTENT_SCRIPT",
    "MESSAGE_DISPATCH_FAILED": "CONTENT_SCRIPT",
    "MESSAGE_RESPONSE_EMPTY": "CONTENT_SCRIPT",
    "MEDIA_PARSER_EMPTY": "PARSER",
    "MEDIA_PARSER_ERROR": "PARSER",
    "MEDIA_IDENTITY_MISMATCH": "PARSER",
    "PAGE_TASK_ERROR": "PAGE_TASK",
}


def failure_class_for_code(code: str) -> str | None:
    """根据固定失败码返回可持久化的失败类别。

    Args:
        code: 扩展回传的固定失败码。

    Returns:
        对应的安全失败类别；未知失败码返回 ``None``。
    """
    return FAILURE_CLASS_BY_CODE.get(code)


def missing_browser_failure_diagnostics() -> dict[str, JsonValue]:
    """为缺少结果 envelope 的终态任务生成固定、可追踪的失败摘要。

    Returns:
        不代表扩展运行时事实的服务端兜底诊断；未知边界明确标记为
        ``UNKNOWN``，避免把旧版扩展或异常中断误判为某个已完成边界。
    """
    return {
        "diagnostic_schema_version": "SERVER-1",
        "last_completed_runtime_boundary": "UNKNOWN",
        "failure_stage": "unknown",
        "failure_code": "RUNTIME_ENVELOPE_MISSING",
        "failure_class": "RUNTIME_ENVELOPE_MISSING",
    }
