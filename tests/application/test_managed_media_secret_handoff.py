"""受管媒体任务的临时令牌交接测试。"""

import asyncio

from xhs_adapters.sqlite import SqliteBrowserTaskRepository
from xhs_core.application import (
    BrowserExecutionService,
    BrowserTaskService,
    ManagedBrowserExecutionGate,
    ManagedBrowserWorker,
)
from xhs_core.domain import (
    BrowserDriver,
    BrowserTask,
    BrowserTaskExecutionResult,
    BrowserTaskStatus,
    ManagedBrowserState,
    ManagedBrowserStatus,
)


class _Controller:
    async def status(self) -> ManagedBrowserStatus:
        return ManagedBrowserStatus(
            installed=True,
            state=ManagedBrowserState.RUNNING,
            executable_name="Synthetic Chromium",
            cdp_port=9222,
            owned_by_current_process=True,
        )


class _Executor:
    def __init__(self) -> None:
        self.tasks: list[BrowserTask] = []

    async def execute(self, task: BrowserTask) -> BrowserTaskExecutionResult:
        self.tasks.append(task)
        return BrowserTaskExecutionResult(
            status=BrowserTaskStatus.SUCCEEDED,
            message="媒体读取完成",
            result={"feed_id": "synthetic-feed", "note_type": "video", "media": []},
        )

    async def close(self) -> None:
        pass


async def test_managed_media_task_receives_ephemeral_token(tmp_path) -> None:
    """确保媒体任务收到不落盘的临时访问令牌。

    Args:
        tmp_path: Pytest 提供的临时目录。
    """
    repository = SqliteBrowserTaskRepository(tmp_path / "state.db")
    tasks = BrowserTaskService(repository)
    execution = BrowserExecutionService(repository, lease_seconds=60)
    executor = _Executor()
    task = await tasks.submit_ephemeral_feed_media(
        {"feed_id": "synthetic-feed", "xsec_token": "synthetic-token"},
        target_driver=BrowserDriver.MANAGED,
    )
    worker = ManagedBrowserWorker(
        _Controller(),
        execution,
        executor,
        ManagedBrowserExecutionGate(),
        poll_interval=0.01,
    )
    await worker.start()
    try:
        for _ in range(100):
            if (
                await tasks.require(task.task_id)
            ).status is BrowserTaskStatus.SUCCEEDED:
                break
            await asyncio.sleep(0.01)
    finally:
        await worker.close()
    assert executor.tasks[0].payload["xsec_token"] == "synthetic-token"
