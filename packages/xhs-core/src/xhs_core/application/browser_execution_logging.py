"""浏览器任务执行日志的安全辅助函数。"""

from loguru import logger

from xhs_core.domain import BrowserTaskStatus, sanitize_browser_task_message


def log_discarded_reason(task_id: str, status: BrowserTaskStatus, message: str) -> None:
    """把即将被脱敏掉的失败原因留在本地日志里。

    Args:
        task_id: 浏览器任务标识。
        status: 任务即将进入的状态。
        message: 浏览器执行器返回的原始消息。
    """
    safe = sanitize_browser_task_message(status, message)
    if safe == message:
        return
    logger.warning(
        "浏览器任务 {} 进入 {} 的原始原因：{}",
        task_id,
        status.value,
        message[:500],
    )
