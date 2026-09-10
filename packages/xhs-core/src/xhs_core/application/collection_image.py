"""收藏快照到图片媒体结果的生产编排。"""

from dataclasses import dataclass

from xhs_core.domain import (
    CollectionEnrichmentStatus,
    CollectionRepository,
    CollectionSnapshotItem,
    WorkType,
)

from .collection_enrichment import (
    CollectionDetailEnrichmentOptions,
    CollectionDetailEnrichmentService,
)
from .collection_media import CollectionMediaBatchResult
from .collection_media_service import (
    CollectionMediaService,
    collection_media_request_id,
)
from .collection_work_mapping import collection_feed_detail_to_work_detail


@dataclass(frozen=True)
class CollectionImageItemResult:
    """一条收藏在生产图片管线中的安全状态摘要。"""

    feed_id: str
    source_order: int
    enrichment_status: str
    media_status: str
    image_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    video_deferred: bool = False
    error_code: str | None = None


@dataclass(frozen=True)
class CollectionImageBatchResult:
    """收藏图片生产管线的有序批次摘要。"""

    snapshot_id: str
    status: str
    items: tuple[CollectionImageItemResult, ...]


class CollectionImageProductionService:
    """把现有 collection、enrichment 和 C3 media service 接成一条链。"""

    def __init__(
        self,
        collections: CollectionRepository,
        enrichment: CollectionDetailEnrichmentService,
        media: CollectionMediaService,
    ) -> None:
        self._collections = collections
        self._enrichment = enrichment
        self._media = media

    async def process_snapshot(
        self,
        snapshot_id: str,
        options: CollectionDetailEnrichmentOptions | None = None,
        *,
        retry_failed: bool = False,
    ) -> CollectionImageBatchResult:
        """先执行现有 enrichment，再执行图片媒体并持久化结果。

        Args:
            snapshot_id: 已存在的收藏快照标识。
            options: 现有 enrichment 的有界选项。
            retry_failed: 是否只重试未成功的图片媒体。

        Returns:
            每条收藏独立的有序状态摘要。
        """
        await self._enrichment.enrich_snapshot(snapshot_id, options)
        return await self._collect_results(snapshot_id, retry_failed, execute=True)

    async def read_snapshot(self, snapshot_id: str) -> CollectionImageBatchResult:
        """只读收藏图片状态，不重新 enrichment 或下载媒体。

        Args:
            snapshot_id: 已存在的收藏快照标识。

        Returns:
            当前已持久化的每条收藏状态摘要。
        """
        return await self._collect_results(snapshot_id, False, execute=False)

    async def _collect_results(
        self, snapshot_id: str, retry_failed: bool, *, execute: bool
    ) -> CollectionImageBatchResult:
        if await self._collections.get_snapshot(snapshot_id) is None:
            raise LookupError(snapshot_id)
        items = await self._collections.list_snapshot_items(snapshot_id)
        summary = await self._enrichment.list_snapshot_enrichments(snapshot_id)
        records = {entry.feed_id: entry for entry in summary.items}
        results = [
            await self._one_item(
                item,
                records.get(item.feed_id),
                retry_failed,
                execute=execute,
            )
            for item in items
        ]
        statuses = {entry.media_status for entry in results}
        status = (
            "partial"
            if any(
                value
                in {
                    "enrichment_failed",
                    "media_failed",
                    "media_partial",
                    "unsupported",
                    "video_deferred",
                }
                for value in statuses
            )
            else "ready"
            if results
            else "empty"
        )
        return CollectionImageBatchResult(snapshot_id, status, tuple(results))

    async def _one_item(self, item, enrichment, retry_failed, *, execute):
        if enrichment is None:
            return _item(
                item, "pending", "media_pending", error_code="enrichment_pending"
            )
        if (
            enrichment.status is not CollectionEnrichmentStatus.SUCCEEDED
            or enrichment.detail is None
        ):
            return _item(
                item,
                enrichment.status.value,
                "enrichment_failed",
                error_code=enrichment.last_error_code or "enrichment_not_ready",
            )
        try:
            detail = collection_feed_detail_to_work_detail(enrichment.detail, item)
        except ValueError:
            return _item(
                item,
                enrichment.status.value,
                "media_failed",
                error_code="detail_identity_mismatch",
            )
        if detail.work_type is WorkType.UNKNOWN:
            return _item(
                item,
                enrichment.status.value,
                "unsupported",
                error_code="unsupported_work_type",
            )
        request_id = collection_media_request_id(item.snapshot_id, detail.work_id)
        try:
            media = (
                await self._media.execute(
                    item,
                    detail,
                    request_id,
                    retry_failed=retry_failed,
                )
                if execute
                else await self._media.read(request_id)
            )
        except ValueError:
            return _item(
                item,
                enrichment.status.value,
                "media_failed",
                error_code="media_identity_conflict",
            )
        if media is None:
            return _item(item, enrichment.status.value, "media_pending")
        return _media_item(item, enrichment.status.value, media)


def _item(item, enrichment_status, media_status, *, error_code=None):
    """构造不含详情正文的收藏状态。"""
    return CollectionImageItemResult(
        feed_id=item.feed_id,
        source_order=item.source_order,
        enrichment_status=enrichment_status,
        media_status=media_status,
        error_code=error_code,
    )


def _media_item(
    item: CollectionSnapshotItem,
    enrichment_status: str,
    media: CollectionMediaBatchResult,
) -> CollectionImageItemResult:
    """把 C3 media batch 转换为用户可见的计数状态。"""
    success = sum(entry.artifact is not None for entry in media.items)
    failure = sum(entry.artifact is None for entry in media.items)
    video_deferred = any(
        entry.kind.value == "视频" for entry in media.deferred if entry.kind
    )
    if video_deferred and not media.items:
        status = "video_deferred"
    elif failure and success:
        status = "media_partial"
    elif failure:
        status = "media_failed"
    elif video_deferred:
        status = "media_partial"
    else:
        status = "media_succeeded"
    error = next((entry.error_code for entry in media.items if entry.error_code), None)
    return CollectionImageItemResult(
        feed_id=item.feed_id,
        source_order=item.source_order,
        enrichment_status=enrichment_status,
        media_status=status,
        image_count=len(media.items),
        success_count=success,
        failure_count=failure,
        video_deferred=video_deferred,
        error_code=error,
    )
