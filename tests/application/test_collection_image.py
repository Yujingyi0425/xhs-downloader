"""收藏夹到图片生产的 C4 合成接线测试。"""

import pytest
from xhs_core.application import (
    CollectionImageProductionService,
    CollectionMediaService,
)
from xhs_core.application.collection_enrichment import (
    CollectionEnrichmentItemSummary,
    CollectionEnrichmentSummary,
)
from xhs_core.domain import (
    CollectionEnrichmentStatus,
    CollectionFeedDetail,
    CollectionSnapshot,
    CollectionSnapshotItem,
    CollectionStatus,
    FeedAuthor,
)

from tests.application.test_collection_media import (
    FakeDetailDownloader,
)
from tests.application.test_collection_media_service import (
    MemoryCollectionMediaRepository,
)


class FakeCollections:
    """提供一份不含 token 的合成快照。"""

    def __init__(self, items):
        self.items = items
        self.snapshot = CollectionSnapshot(
            snapshot_id="synthetic-snapshot",
            source_type="board",
            board_id="synthetic-board",
            board_revision=1,
            request_id="synthetic-request",
            captured_at="2026-01-01T00:00:00Z",
            item_count=len(items),
            fingerprint="a" * 64,
            status=CollectionStatus.CAPTURED,
        )

    async def get_snapshot(self, snapshot_id):
        """读取合成快照。

        Args:
            snapshot_id: 待读取的快照标识。

        Returns:
            匹配的合成快照或空值。
        """
        return self.snapshot if snapshot_id == self.snapshot.snapshot_id else None

    async def list_snapshot_items(self, snapshot_id):
        """读取合成快照 membership。

        Args:
            snapshot_id: 待读取的快照标识。

        Returns:
            合成 membership 列表。
        """
        return list(self.items) if snapshot_id == self.snapshot.snapshot_id else []


class FakeEnrichment:
    """返回预先构造的安全详情汇总，不访问浏览器或网络。"""

    def __init__(self, entries):
        self.entries = entries
        self.calls = 0

    async def enrich_snapshot(self, snapshot_id, options=None):
        """记录编排调用并返回合成汇总。

        Args:
            snapshot_id: 待处理的快照标识。
            options: 未使用的合成选项。

        Returns:
            合成 enrichment 汇总。
        """
        self.calls += 1
        return self.summary(snapshot_id)

    async def list_snapshot_enrichments(self, snapshot_id):
        """读取合成 enrichment 汇总。

        Args:
            snapshot_id: 待读取的快照标识。

        Returns:
            合成 enrichment 汇总。
        """
        return self.summary(snapshot_id)

    def summary(self, snapshot_id):
        """构造合成 enrichment 汇总。

        Args:
            snapshot_id: 汇总所属的快照标识。

        Returns:
            合成 enrichment 汇总。
        """
        return CollectionEnrichmentSummary(
            snapshot_id=snapshot_id,
            total=len(self.entries),
            succeeded=sum(
                entry.status is CollectionEnrichmentStatus.SUCCEEDED
                for entry in self.entries
            ),
            items=self.entries,
        )


def entry(item, detail, status=CollectionEnrichmentStatus.SUCCEEDED, error=None):
    """构造一条合成 enrichment 摘要。

    Args:
        item: 合成收藏条目。
        detail: 合成详情或空值。
        status: enrichment 状态。
        error: 脱敏错误分类或空值。

    Returns:
        合成 enrichment 摘要。
    """
    return CollectionEnrichmentItemSummary(
        feed_id=item.feed_id,
        source_order=item.source_order,
        status=status,
        attempt_count=1,
        last_error_code=error,
        detail=detail,
    )


def collection_item(feed_id, source_order=0):
    """构造一条合成 membership。

    Args:
        feed_id: 作品标识。
        source_order: 收藏顺序。

    Returns:
        合成收藏条目。
    """
    return CollectionSnapshotItem(
        snapshot_id="synthetic-snapshot",
        feed_id=feed_id,
        source_order=source_order,
    )


def collection_detail(feed_id, *, image_urls=None, note_type="image"):
    """构造 C1 mapper 可消费的脱敏详情。

    Args:
        feed_id: 作品标识。
        image_urls: 合成图片地址。
        note_type: 小红书详情类型。

    Returns:
        C1 mapper 可消费的详情。
    """
    return CollectionFeedDetail(
        feed_id=feed_id,
        title="合成标题",
        body="合成正文",
        note_type=note_type,
        author=FeedAuthor(user_id="author-a", nickname="合成作者"),
        image_urls=image_urls or ["https://example.invalid/image.jpg"],
    )


@pytest.mark.asyncio
async def test_collection_image_production_wires_single_and_multi_image() -> None:
    """单图与多图均通过 C1 mapper 和 C3 service 生成 artifact。"""
    items = [collection_item("feed-a"), collection_item("feed-b", 1)]
    enrichment = FakeEnrichment(
        [
            entry(items[0], collection_detail("feed-a")),
            entry(
                items[1],
                collection_detail(
                    "feed-b",
                    image_urls=[
                        "https://example.invalid/1.jpg",
                        "https://example.invalid/2.jpg",
                    ],
                ),
            ),
        ]
    )
    downloader = FakeDetailDownloader()
    service = CollectionImageProductionService(
        FakeCollections(items),
        enrichment,
        CollectionMediaService(downloader, MemoryCollectionMediaRepository()),
    )

    result = await service.process_snapshot("synthetic-snapshot")

    assert result.status == "ready"
    assert [(item.success_count, item.image_count) for item in result.items] == [
        (1, 1),
        (2, 2),
    ]
    assert len(downloader.calls) == 3
    assert enrichment.calls == 1


@pytest.mark.asyncio
async def test_failed_item_does_not_block_successful_image_item() -> None:
    """Enrichment 失败和图片失败都只影响对应条目。"""
    items = [collection_item("feed-f"), collection_item("feed-ok", 1)]
    enrichment = FakeEnrichment(
        [
            entry(
                items[0],
                None,
                CollectionEnrichmentStatus.FAILED_RETRYABLE,
                "provider_unavailable",
            ),
            entry(items[1], collection_detail("feed-ok")),
        ]
    )
    downloader = FakeDetailDownloader(failures={1})
    service = CollectionImageProductionService(
        FakeCollections(items),
        enrichment,
        CollectionMediaService(downloader, MemoryCollectionMediaRepository()),
    )

    result = await service.process_snapshot("synthetic-snapshot")

    assert result.status == "partial"
    assert result.items[0].media_status == "enrichment_failed"
    assert result.items[0].error_code == "provider_unavailable"
    assert result.items[1].media_status == "media_failed"


@pytest.mark.asyncio
async def test_video_is_deferred_and_unknown_is_unsupported() -> None:
    """视频不获取，未知类型不拖死图片生产。"""
    items = [collection_item("feed-video"), collection_item("feed-unknown", 1)]
    enrichment = FakeEnrichment(
        [
            entry(items[0], collection_detail("feed-video", note_type="video")),
            entry(items[1], collection_detail("feed-unknown", note_type="text")),
        ]
    )
    downloader = FakeDetailDownloader()
    service = CollectionImageProductionService(
        FakeCollections(items),
        enrichment,
        CollectionMediaService(downloader, MemoryCollectionMediaRepository()),
    )

    result = await service.process_snapshot("synthetic-snapshot")

    assert [item.media_status for item in result.items] == [
        "video_deferred",
        "unsupported",
    ]
    assert not downloader.calls


@pytest.mark.asyncio
async def test_repeated_process_is_idempotent_and_read_is_side_effect_free() -> None:
    """重复生产读回 C3 artifact，读取不会 enrichment 或下载。"""
    item = collection_item("feed-a")
    enrichment = FakeEnrichment([entry(item, collection_detail("feed-a"))])
    downloader = FakeDetailDownloader()
    service = CollectionImageProductionService(
        FakeCollections([item]),
        enrichment,
        CollectionMediaService(downloader, MemoryCollectionMediaRepository()),
    )

    first = await service.process_snapshot("synthetic-snapshot")
    second = await service.process_snapshot("synthetic-snapshot")
    read = await service.read_snapshot("synthetic-snapshot")

    assert second == first == read
    assert len(downloader.calls) == 1
    assert enrichment.calls == 2
