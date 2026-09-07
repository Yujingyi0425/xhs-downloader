"""收藏快照详情 enrichment 编排用例。"""

import asyncio
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Protocol

from pydantic import BaseModel, Field

from xhs_core.domain import (
    CollectionEnrichmentStatus,
    CollectionFeedDetail,
    CollectionRepository,
    EnrichmentStateConflictError,
    ProviderError,
    ProviderFailureCode,
)
from xhs_core.domain.collection_enrichment_ports import CollectionEnrichmentRepository

from .collection_enrichment_helpers import detail_request_id, item_summary, summary


class DetailCapability(Protocol):
    """详情能力运行时的最小端口。"""

    async def get_feed_detail(
        self,
        feed_id: str,
        xsec_token: str,
        *,
        comment_limit: int,
        include_replies: bool,
        reply_limit: int,
        request_id: str,
    ) -> object:
        """通过统一只读能力读取详情。

        Args:
            feed_id: 帖子标识。
            xsec_token: 短期访问令牌。
            comment_limit: 一级评论上限。
            include_replies: 是否包含回复。
            reply_limit: 回复上限。
            request_id: 详情任务幂等标识。

        Returns:
            统一路由结果。
        """
        ...


class CollectionDetailEnrichmentOptions(BaseModel):
    """详情 enrichment 的有界选项。"""

    comment_limit: int = Field(default=10, ge=0, le=100)
    include_replies: bool = False
    reply_limit: int = Field(default=10, ge=0, le=100)
    limit: int | None = Field(default=None, ge=1, le=500)


class CollectionEnrichmentItemSummary(BaseModel):
    """单个 enrichment 的安全摘要。"""

    feed_id: str
    source_order: int
    status: CollectionEnrichmentStatus
    attempt_count: int
    last_error_code: str | None = None
    detail: CollectionFeedDetail | None = None


class CollectionEnrichmentSummary(BaseModel):
    """批次详情 enrichment 的安全汇总。"""

    snapshot_id: str
    total: int
    succeeded: int = 0
    already_succeeded: int = 0
    failed_retryable: int = 0
    failed_terminal: int = 0
    needs_reimport: int = 0
    needs_review: int = 0
    running_skipped: int = 0
    concurrent_skipped: int = 0
    items: list[CollectionEnrichmentItemSummary] = Field(default_factory=list)


class UnknownSnapshotError(LookupError):
    """请求的收藏快照不存在。"""


class CollectionDetailEnrichmentService:
    """按快照 membership 顺序、有界并发获取并保存帖子详情。"""

    def __init__(
        self,
        collections: CollectionRepository,
        enrichments: CollectionEnrichmentRepository,
        runtime_lease: Callable[[], AbstractAsyncContextManager[DetailCapability]],
        *,
        max_in_flight: int = 3,
    ) -> None:
        if max_in_flight != 3:
            raise ValueError("详情 enrichment 并发上限必须为 3")
        self._collections = collections
        self._enrichments = enrichments
        self._runtime_lease = runtime_lease
        self.max_in_flight = max_in_flight

    async def enrich_snapshot(
        self,
        snapshot_id: str,
        options: CollectionDetailEnrichmentOptions | None = None,
    ) -> CollectionEnrichmentSummary:
        """执行一批收藏详情 enrichment。

        Args:
            snapshot_id: 已存在的收藏快照标识。
            options: 有界详情读取选项。

        Returns:
            按 membership source_order 排列的安全汇总。

        Raises:
            UnknownSnapshotError: 快照不存在。
        """
        snapshot = await self._collections.get_snapshot(snapshot_id)
        if snapshot is None:
            raise UnknownSnapshotError(snapshot_id)
        items = await self._collections.list_snapshot_items(snapshot_id)
        selected = items[: (options or CollectionDetailEnrichmentOptions()).limit]
        opts = options or CollectionDetailEnrichmentOptions()
        summaries: list[CollectionEnrichmentItemSummary | None] = [None] * len(selected)
        queue: asyncio.Queue[tuple[int, object] | None] = asyncio.Queue()
        for index, item in enumerate(selected):
            queue.put_nowait((index, item))

        async def worker() -> None:
            while True:
                work = await queue.get()
                try:
                    if work is None:
                        return
                    index, item = work
                    summaries[index] = await self._enrich_one(item, opts)
                finally:
                    queue.task_done()

        workers = [asyncio.create_task(worker()) for _ in range(self.max_in_flight)]
        await queue.join()
        for _ in workers:
            queue.put_nowait(None)
        await asyncio.gather(*workers)
        result_items = [item for item in summaries if item is not None]
        from .collection_enrichment_helpers import summary

        return summary(snapshot_id, result_items)

    async def list_snapshot_enrichments(
        self, snapshot_id: str
    ) -> CollectionEnrichmentSummary:
        """读取当前快照的有序 enrichment 结果。

        Args:
            snapshot_id: 已存在的收藏快照标识。

        Returns:
            按 membership source_order 排列的安全汇总。

        Raises:
            UnknownSnapshotError: 快照不存在。
        """
        if await self._collections.get_snapshot(snapshot_id) is None:
            raise UnknownSnapshotError(snapshot_id)
        items = await self._collections.list_snapshot_items(snapshot_id)
        records = {
            record.feed_id: record
            for record in await self._enrichments.list_snapshot_enrichments(snapshot_id)
        }
        summaries = [
            item_summary(item.source_order, records[item.feed_id])
            for item in items
            if item.feed_id in records
        ]
        return summary(snapshot_id, summaries)

    async def _enrich_one(self, item, options) -> CollectionEnrichmentItemSummary:
        record = await self._enrichments.ensure_enrichment(
            item.snapshot_id, item.feed_id
        )
        if record.status in {
            CollectionEnrichmentStatus.SUCCEEDED,
            CollectionEnrichmentStatus.FAILED_TERMINAL,
            CollectionEnrichmentStatus.NEEDS_REIMPORT,
            CollectionEnrichmentStatus.NEEDS_REVIEW,
        }:
            return item_summary(item.source_order, record)
        if record.status is CollectionEnrichmentStatus.RUNNING:
            return item_summary(item.source_order, record)
        access = await self._collections.get_feed_access_context(item.feed_id)
        if access is None:
            record = await self._enrichments.transition_enrichment(
                item.snapshot_id,
                item.feed_id,
                {record.status},
                CollectionEnrichmentStatus.NEEDS_REIMPORT,
                error_code="missing_access_context",
            )
            return item_summary(item.source_order, record)
        try:
            record = await self._enrichments.transition_enrichment(
                item.snapshot_id,
                item.feed_id,
                {
                    CollectionEnrichmentStatus.PENDING,
                    CollectionEnrichmentStatus.FAILED_RETRYABLE,
                },
                CollectionEnrichmentStatus.RUNNING,
            )
        except EnrichmentStateConflictError:
            latest = await self._enrichments.get_enrichment(
                item.snapshot_id, item.feed_id
            )
            return item_summary(item.source_order, latest, concurrent=True)
        request_id = detail_request_id(
            item.snapshot_id,
            item.feed_id,
            record.enrichment_version,
            record.attempt_count,
        )
        try:
            async with self._runtime_lease() as runtime:
                routed = await runtime.get_feed_detail(
                    item.feed_id,
                    access.latest_xsec_token.get_secret_value(),
                    comment_limit=options.comment_limit,
                    include_replies=options.include_replies,
                    reply_limit=options.reply_limit,
                    request_id=request_id,
                )
            detail = CollectionFeedDetail.from_feed_detail(
                routed.value, expected_feed_id=item.feed_id
            )
            record = await self._enrichments.save_detail(
                item.snapshot_id, item.feed_id, detail
            )
        except EnrichmentStateConflictError:
            latest = await self._enrichments.get_enrichment(
                item.snapshot_id, item.feed_id
            )
            return item_summary(item.source_order, latest, concurrent=True)
        except ProviderError as error:
            return item_summary(
                item.source_order, await self._transition_failure(item, record, error)
            )
        except ValueError as error:
            code = (
                "detail_identity_mismatch"
                if "feed_id" in str(error)
                else "unexpected_error"
            )
            record = await self._enrichments.transition_enrichment(
                item.snapshot_id,
                item.feed_id,
                {record.status},
                CollectionEnrichmentStatus.FAILED_TERMINAL
                if code == "detail_identity_mismatch"
                else CollectionEnrichmentStatus.FAILED_RETRYABLE,
                error_code=code,
            )
        except Exception:
            record = await self._enrichments.transition_enrichment(
                item.snapshot_id,
                item.feed_id,
                {record.status},
                CollectionEnrichmentStatus.FAILED_RETRYABLE,
                error_code="unexpected_error",
            )
        return item_summary(item.source_order, record)

    async def _transition_failure(self, item, record, error: ProviderError):
        status = (
            CollectionEnrichmentStatus.NEEDS_REVIEW
            if error.code is ProviderFailureCode.EFFECT_UNCERTAIN
            else CollectionEnrichmentStatus.FAILED_RETRYABLE
        )
        code = f"provider_{error.code.value}"
        return await self._enrichments.transition_enrichment(
            item.snapshot_id, item.feed_id, {record.status}, status, error_code=code
        )
