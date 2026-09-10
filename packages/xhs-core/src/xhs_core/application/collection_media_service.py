"""收藏夹媒体结果的重试、幂等和持久化编排。"""

from collections.abc import Callable

from xhs_core.domain import (
    CollectionMediaArtifactRepository,
    CollectionMediaBatchRecord,
    CollectionMediaBatchStatus,
    CollectionMediaDeferredRecord,
    CollectionMediaItemRecord,
    CollectionMediaItemStatus,
    CollectionSnapshotItem,
    MediaKind,
    WorkDetail,
)
from xhs_core.domain.models import DownloadProgress

from .collection_media import (
    CollectionDetailDownloader,
    CollectionMediaBatchResult,
    CollectionMediaCoordinator,
    CollectionMediaItemResult,
    CollectionMediaStatus,
    DeferredCollectionMedia,
)


class CollectionMediaService:
    """闭合收藏夹媒体的 per-request 幂等、部分失败与读回。"""

    def __init__(
        self,
        downloader: CollectionDetailDownloader,
        repository: CollectionMediaArtifactRepository,
    ) -> None:
        self._coordinator = CollectionMediaCoordinator(downloader)
        self._downloader = downloader
        self._repository = repository

    async def __aenter__(self) -> "CollectionMediaService":
        """转发底层下载服务的连接池生命周期。"""
        enter = getattr(self._downloader, "__aenter__", None)
        if enter:
            await enter()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        """关闭底层下载服务的连接池。"""
        exit_method = getattr(self._downloader, "__aexit__", None)
        if exit_method:
            await exit_method(exc_type, exc_value, traceback)
            return
        close = getattr(self._downloader, "close", None)
        if close:
            await close()

    async def execute(
        self,
        item: CollectionSnapshotItem,
        detail: WorkDetail,
        request_id: str,
        *,
        retry_failed: bool = False,
        on_progress: Callable[[DownloadProgress], None] | None = None,
    ) -> CollectionMediaBatchResult:
        """执行、读回或只重试尚未成功的媒体。

        Args:
            item: 收藏快照中的条目身份。
            detail: C1 mapper 生成的 canonical 作品详情。
            request_id: 客户端为相同规划输入提供的稳定请求标识。
            retry_failed: 是否只重试历史中尚未成功的媒体。
            on_progress: 可选的底层下载进度回调。

        Returns:
            按媒体序号稳定排列的完整批次结果。
        """
        plan = self._coordinator.plan(item, detail)
        existing = await self._repository.get(request_id)
        if existing is not None:
            _validate_existing(existing, request_id, item, plan)
            if not retry_failed:
                return _result_from_record(existing)
            indexes = {
                task.media_index
                for task in plan.tasks
                if not _successful_item(
                    existing, task.work_id, task.media_index, task.kind
                )
            }
            if not indexes:
                return _result_from_record(existing)
            fresh = await self._coordinator.execute(
                item, detail, on_progress, indexes=indexes
            )
            result = _merge_results(existing, fresh, plan.tasks)
        else:
            result = await self._coordinator.execute(item, detail, on_progress)
        await self._repository.save(_record_from_result(request_id, result))
        return result


def _validate_existing(record, request_id, item, plan) -> None:
    """拒绝同一 request ID 复用到不同 collection/media 输入。"""
    if (
        record.request_id != request_id
        or record.snapshot_id != item.snapshot_id
        or record.source_order != item.source_order
        or record.work_id != item.feed_id
    ):
        raise ValueError("媒体 request identity conflict")
    expected = {(task.work_id, task.media_index, task.kind) for task in plan.tasks}
    actual = {(entry.work_id, entry.media_index, entry.kind) for entry in record.items}
    if expected != actual:
        raise ValueError("媒体 request plan conflict")


def _successful_item(record, work_id: str, media_index: int, kind: MediaKind) -> bool:
    """判断指定媒体是否已有可复用的成功 artifact。"""
    return any(
        entry.work_id == work_id
        and entry.media_index == media_index
        and entry.kind is kind
        and entry.status is CollectionMediaItemStatus.SUCCEEDED
        and entry.artifact is not None
        for entry in record.items
    )


def _merge_results(record, fresh, tasks) -> CollectionMediaBatchResult:
    """按规划顺序合并旧成功项与本次重试结果。"""
    old = {
        (entry.work_id, entry.media_index, entry.kind): entry
        for entry in record.items
    }
    new = {
        (entry.work_id, entry.media_index, entry.kind): entry
        for entry in fresh.items
    }
    items = tuple(
        new.get(
            (task.work_id, task.media_index, task.kind),
            _item_result_from_record(old[(task.work_id, task.media_index, task.kind)]),
        )
        for task in tasks
    )
    return CollectionMediaBatchResult(
        snapshot_id=fresh.snapshot_id,
        source_order=fresh.source_order,
        work_id=fresh.work_id,
        items=items,
        deferred=fresh.deferred,
    )


def _record_from_result(
    request_id: str, result: CollectionMediaBatchResult
) -> CollectionMediaBatchRecord:
    """把不含 locator 的结果转换为持久化 artifact record。"""
    items = [
        CollectionMediaItemRecord(
            snapshot_id=item.snapshot_id,
            source_order=item.source_order,
            work_id=item.work_id,
            media_index=item.media_index,
            kind=item.kind,
            status=CollectionMediaItemStatus(item.status.value),
            artifact=item.artifact,
            error_code=item.error_code,
        )
        for item in result.items
    ]
    deferred = [
        CollectionMediaDeferredRecord(
            work_id=entry.work_id,
            media_index=entry.media_index,
            kind=entry.kind,
            reason=entry.reason,
        )
        for entry in result.deferred
    ]
    return CollectionMediaBatchRecord(
        request_id=request_id,
        snapshot_id=result.snapshot_id,
        source_order=result.source_order,
        work_id=result.work_id,
        status=_batch_status(result.items, result.deferred),
        items=items,
        deferred=deferred,
    )


def _batch_status(items, deferred) -> CollectionMediaBatchStatus:
    """计算 all-success、partial、all-failed 和 deferred 汇总状态。"""
    success = any(item.status is CollectionMediaStatus.SUCCEEDED for item in items)
    failed = any(item.status is CollectionMediaStatus.FAILED for item in items)
    if failed and success:
        return CollectionMediaBatchStatus.PARTIAL
    if failed:
        return CollectionMediaBatchStatus.FAILED
    if deferred and not items:
        return CollectionMediaBatchStatus.DEFERRED
    if deferred:
        return CollectionMediaBatchStatus.PARTIAL
    return CollectionMediaBatchStatus.SUCCEEDED


def _result_from_record(
    record: CollectionMediaBatchRecord,
) -> CollectionMediaBatchResult:
    """从持久化记录恢复稳定媒体顺序和关联。"""
    items = tuple(
        _item_result_from_record(entry)
        for entry in sorted(record.items, key=lambda entry: entry.media_index)
    )
    deferred = tuple(
        DeferredCollectionMedia(
            work_id=entry.work_id,
            media_index=entry.media_index,
            kind=entry.kind,
            reason=entry.reason,
        )
        for entry in record.deferred
    )
    return CollectionMediaBatchResult(
        snapshot_id=record.snapshot_id,
        source_order=record.source_order,
        work_id=record.work_id,
        items=items,
        deferred=deferred,
    )


def _item_result_from_record(
    entry: CollectionMediaItemRecord,
) -> CollectionMediaItemResult:
    """恢复一条媒体成功或失败结果。"""
    return CollectionMediaItemResult(
        snapshot_id=entry.snapshot_id,
        source_order=entry.source_order,
        work_id=entry.work_id,
        media_index=entry.media_index,
        kind=entry.kind,
        status=CollectionMediaStatus(entry.status.value),
        artifact=entry.artifact,
        error_code=entry.error_code,
    )
