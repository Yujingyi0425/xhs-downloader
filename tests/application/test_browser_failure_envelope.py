"""浏览器任务缺失失败 envelope 的持久化回归。"""

from xhs_adapters.sqlite import SqliteBrowserTaskRepository
from xhs_core.application import BrowserExecutionService, BrowserTaskService
from xhs_core.domain import BrowserTaskStatus


async def test_missing_failure_result_persists_bounded_fallback(tmp_path) -> None:
    """旧版或异常扩展省略 result 时不得再产生 null readback。

    Args:
        tmp_path: Pytest 提供的临时目录。
    """
    repository = SqliteBrowserTaskRepository(tmp_path.joinpath("state.db"))
    tasks = BrowserTaskService(repository)
    execution = BrowserExecutionService(repository, lease_seconds=60)
    task = await tasks.submit_ephemeral_feed_detail(
        {"feed_id": "synthetic-feed", "xsec_token": "synthetic-token"}
    )
    claim = await execution.claim("synthetic-extension")
    assert claim is not None

    completed = await execution.update(
        task.task_id,
        claim.lease_token,
        BrowserTaskStatus.FAILED,
        "旧版扩展未返回失败结果",
        None,
    )
    stored = await repository.get(task.task_id)

    expected = {
        "diagnostic_schema_version": "SERVER-1",
        "last_completed_runtime_boundary": "UNKNOWN",
        "failure_stage": "unknown",
        "failure_code": "RUNTIME_ENVELOPE_MISSING",
        "failure_class": "RUNTIME_ENVELOPE_MISSING",
    }
    assert completed.result == expected
    assert stored is not None
    assert stored.result == expected
