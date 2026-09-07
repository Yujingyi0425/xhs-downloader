"""收藏详情 enrichment 的进程内后台任务协调器。"""

import asyncio
from collections.abc import Awaitable, Callable


class CollectionEnrichmentJobCoordinator:
    """为每个 snapshot 保留一个后台 enrichment 任务。"""

    def __init__(self) -> None:
        self._jobs: dict[str, asyncio.Task[object]] = {}

    def start(self, snapshot_id: str, work: Callable[[], Awaitable[object]]) -> bool:
        """启动尚未运行的快照任务。

        Args:
            snapshot_id: 快照标识。
            work: 批次异步工作函数。

        Returns:
            新建任务返回 ``True``，已有活动任务返回 ``False``。
        """
        current = self._jobs.get(snapshot_id)
        if current is not None and not current.done():
            return False
        task = asyncio.create_task(work())
        self._jobs[snapshot_id] = task
        task.add_done_callback(lambda _: self._jobs.pop(snapshot_id, None))
        return True

    def active(self, snapshot_id: str) -> bool:
        """判断快照是否有活动任务。

        Args:
            snapshot_id: 快照标识。

        Returns:
            是否正在执行。
        """
        task = self._jobs.get(snapshot_id)
        return task is not None and not task.done()

    async def close(self) -> None:
        """取消并等待所有进程内任务。"""
        tasks = list(self._jobs.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._jobs.clear()
