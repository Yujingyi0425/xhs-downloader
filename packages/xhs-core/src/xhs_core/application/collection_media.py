"""收藏夹图像媒体的计划、执行和结果关联。"""

import asyncio
from collections.abc import Callable
from typing import Protocol

from xhs_core.domain import (
    CollectionSnapshotItem,
    WorkDetail,
)
from xhs_core.domain.models import (
    DownloadArtifact,
    DownloadProgress,
    MediaKind,
    WorkType,
)

from .collection_media_models import (
    CollectionMediaBatchResult,
    CollectionMediaItemResult,
    CollectionMediaPlan,
    CollectionMediaStatus,
    CollectionMediaTask,
    DeferredCollectionMedia,
)
from .collection_media_validation import safe_suffix, validate_media_url


class CollectionDetailDownloader(Protocol):
    """接收已解析作品详情的现有下载能力最小端口。"""

    async def download_detail(
        self,
        detail: WorkDetail,
        indexes: set[int],
        on_progress: Callable[[DownloadProgress], None] | None = None,
    ) -> list[DownloadArtifact]:
        """下载已解析详情中的指定媒体。

        Args:
            detail: 已验证的 canonical 作品详情。
            indexes: 需要下载的一基媒体序号。
            on_progress: 可选的下载进度回调。

        Returns:
            已完成落盘的 artifact 列表。
        """
        ...


class CollectionMediaCoordinator:
    """把 canonical WorkDetail 拆成独立图像任务并复用现有下载器。"""

    def __init__(self, downloader: CollectionDetailDownloader) -> None:
        self._downloader = downloader

    def plan(
        self, item: CollectionSnapshotItem, detail: WorkDetail
    ) -> CollectionMediaPlan:
        """创建保持媒体顺序且不执行视频的任务计划。

        Args:
            item: 收藏快照中的条目身份和 collection 顺序。
            detail: C1 mapper 生成的 canonical 作品详情。

        Returns:
            图像任务和延后媒体的确定性计划。

        Raises:
            ValueError: collection/work identity 或媒体身份无效。
        """
        self._validate_work_identity(item, detail)
        tasks: list[CollectionMediaTask] = []
        deferred: list[DeferredCollectionMedia] = []
        seen_indexes: set[int] = set()
        for resource in detail.media:
            if resource.index in seen_indexes:
                raise ValueError("media index must be unique within a work")
            seen_indexes.add(resource.index)
            if resource.kind is not MediaKind.IMAGE:
                deferred.append(
                    DeferredCollectionMedia(
                        work_id=detail.work_id,
                        media_index=resource.index,
                        kind=resource.kind,
                        reason="media_kind_deferred",
                    )
                )
                continue
            media_url = resource.url.strip()
            validate_media_url(media_url)
            suffix = safe_suffix(resource.suffix)
            tasks.append(
                CollectionMediaTask(
                    snapshot_id=item.snapshot_id,
                    source_order=item.source_order,
                    work_id=detail.work_id,
                    source_url=detail.source_url,
                    media_index=resource.index,
                    kind=resource.kind,
                    media_url=media_url,
                    suffix=suffix,
                )
            )
        if detail.work_type is WorkType.VIDEO and not detail.media:
            deferred.append(
                DeferredCollectionMedia(
                    work_id=detail.work_id,
                    media_index=None,
                    kind=MediaKind.VIDEO,
                    reason="video_acquisition_deferred",
                )
            )
        return CollectionMediaPlan(tuple(tasks), tuple(deferred))

    async def execute(
        self,
        item: CollectionSnapshotItem,
        detail: WorkDetail,
        on_progress: Callable[[DownloadProgress], None] | None = None,
        indexes: set[int] | None = None,
    ) -> CollectionMediaBatchResult:
        """执行图像计划并按逻辑任务恢复结果顺序。

        Args:
            item: 收藏快照条目身份。
            detail: canonical 作品详情。
            on_progress: 可选的底层下载进度回调。

        Returns:
            按输入媒体顺序排列的逐媒体结果；视频只进入 deferred。

        Args:
            indexes: 可选的待执行媒体序号；重试时只传入未成功媒体。
        """
        plan = self.plan(item, detail)
        tasks = tuple(
            task
            for task in plan.tasks
            if indexes is None or task.media_index in indexes
        )
        results = await asyncio.gather(
            *(self._execute_one(task, detail, on_progress) for task in tasks),
            return_exceptions=True,
        )
        normalized = [
            result
            if isinstance(result, CollectionMediaItemResult)
            else self._failed_result(task, "download_failed")
            for task, result in zip(tasks, results, strict=True)
        ]
        return CollectionMediaBatchResult(
            snapshot_id=item.snapshot_id,
            source_order=item.source_order,
            work_id=detail.work_id,
            items=tuple(normalized),
            deferred=plan.deferred,
        )

    async def _execute_one(
        self,
        task: CollectionMediaTask,
        detail: WorkDetail,
        on_progress: Callable[[DownloadProgress], None] | None,
    ) -> CollectionMediaItemResult:
        try:
            download_detail = _download_detail(detail, task)
            artifacts = await self._downloader.download_detail(
                download_detail, {task.media_index}, on_progress
            )
        except Exception:
            return self._failed_result(task, "download_failed")
        if len(artifacts) != 1:
            return self._failed_result(task, "artifact_missing")
        artifact = artifacts[0]
        if artifact.media_index != task.media_index or artifact.kind is not task.kind:
            return self._failed_result(task, "artifact_identity_mismatch")
        return CollectionMediaItemResult(
            snapshot_id=task.snapshot_id,
            source_order=task.source_order,
            work_id=task.work_id,
            media_index=task.media_index,
            kind=task.kind,
            status=CollectionMediaStatus.SUCCEEDED,
            artifact=artifact,
        )

    @staticmethod
    def _failed_result(
        task: CollectionMediaTask, error_code: str
    ) -> CollectionMediaItemResult:
        """构造不暴露底层异常正文的失败结果。"""
        return CollectionMediaItemResult(
            snapshot_id=task.snapshot_id,
            source_order=task.source_order,
            work_id=task.work_id,
            media_index=task.media_index,
            kind=task.kind,
            status=CollectionMediaStatus.FAILED,
            error_code=error_code,
        )

    @staticmethod
    def _validate_work_identity(
        item: CollectionSnapshotItem, detail: WorkDetail
    ) -> None:
        """拒绝错误 collection/work 关联。"""
        if not item.snapshot_id.strip() or not item.feed_id.strip():
            raise ValueError("collection identity is missing")
        if not detail.work_id.strip():
            raise ValueError("work identity is missing")
        if item.feed_id != detail.work_id:
            raise ValueError("collection item and work_id do not match")


def _download_detail(detail: WorkDetail, task: CollectionMediaTask) -> WorkDetail:
    """生成仅含当前图像且带稳定身份命名提示的下载输入。"""
    resource = next(
        (
            media
            for media in detail.media
            if media.index == task.media_index and media.kind is MediaKind.IMAGE
        ),
        None,
    )
    if resource is None:
        raise ValueError("planned image media is missing")
    safe_resource = resource.model_copy(update={"suffix": task.suffix})
    stable_title = (
        f"{detail.title}_{detail.work_id}" if detail.title else detail.work_id
    )
    return detail.model_copy(update={"title": stable_title, "media": [safe_resource]})
