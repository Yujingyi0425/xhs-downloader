"""浏览器任务终态结果的安全归一化。"""

from pydantic import JsonValue

from xhs_core.domain import (
    BrowserTask,
    BrowserTaskStatus,
    mark_browser_runtime_telemetry_submitted,
    missing_browser_failure_diagnostics,
    sanitize_browser_page_diagnostics,
)
from xhs_core.domain.browser_requests import validate_browser_task_result


def normalize_browser_task_result(
    task: BrowserTask,
    status: BrowserTaskStatus,
    result: dict[str, JsonValue] | None,
) -> dict[str, JsonValue] | None:
    """校验成功结果，并为失败结果生成安全、非空的诊断 envelope。

    Args:
        task: 当前浏览器任务及其正式结果 schema。
        status: 执行器即将写入的终态或中间态。
        result: 执行器回传的结构化结果。

    Returns:
        校验后的成功结果、安全失败诊断或中间态的 ``None``。
    """
    if status is BrowserTaskStatus.SUCCEEDED and result is not None:
        return validate_browser_task_result(task.kind, result)
    if status in {BrowserTaskStatus.FAILED, BrowserTaskStatus.NEEDS_REVIEW}:
        diagnostics = sanitize_browser_page_diagnostics(result)
        if diagnostics is None:
            diagnostics = missing_browser_failure_diagnostics()
        return mark_browser_runtime_telemetry_submitted(diagnostics)
    return None
