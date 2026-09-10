"""选择性收藏图片生产的 production-component 合成 E2E。"""

from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from xhs_adapters.sqlite import (
    SqliteCollectionEnrichmentRepository,
    SqliteCollectionMediaArtifactRepository,
    SqliteCollectionRepository,
)
from xhs_core.application import (
    CollectionDetailEnrichmentService,
    CollectionImageProductionService,
    CollectionMediaService,
)

from tests.application.test_collection_media import FakeDetailDownloader
from tests.infrastructure.collection_enrichment_fixtures import (
    create_snapshot,
    detail,
)


class RuntimeFixture:
    """返回合成详情并记录真实 enrichment 调用。"""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def get_feed_detail(self, feed_id, xsec_token, **kwargs):
        """返回不含真实数据的合成详情。

        Args:
            feed_id: 合成帖子标识。
            xsec_token: 未持久化的合成访问令牌。
            kwargs: 合成读取选项。

        Returns:
            包装后的合成详情结果。
        """
        del xsec_token, kwargs
        self.calls.append(feed_id)
        if feed_id == "feed-video":
            value = detail(feed_id, note_type="video")
        elif feed_id == "feed-gallery":
            value = detail(
                feed_id,
                image_urls=[
                    "https://example.invalid/gallery-1.jpg",
                    "https://example.invalid/gallery-2.jpg",
                ],
            )
        else:
            value = detail(feed_id)
        return SimpleNamespace(value=value)


def build_service(database: Path, runtime: RuntimeFixture, downloader):
    """组装真实 SQLite repository 与应用 service。

    Args:
        database: 合成 SQLite 数据库路径。
        runtime: 合成详情读取运行时。
        downloader: 合成图片下载器。

    Returns:
        由真实 repository 和 application service 组成的生产服务。
    """
    collections = SqliteCollectionRepository(database)
    enrichments = SqliteCollectionEnrichmentRepository(database)

    @asynccontextmanager
    async def lease():
        yield runtime

    enrichment = CollectionDetailEnrichmentService(collections, enrichments, lease)
    media = CollectionMediaService(
        downloader, SqliteCollectionMediaArtifactRepository(database)
    )
    return CollectionImageProductionService(collections, enrichment, media)


@pytest.mark.asyncio
async def test_selective_image_e2e_uses_production_components_and_reads_back(
    tmp_path,
):
    """选择单图、图集和视频时只处理选择项，且重启后可读回 artifact。

    Args:
        tmp_path: 测试临时目录。
    """
    database = tmp_path / "state.db"
    snapshot_id = await create_snapshot(
        database, ["feed-image", "feed-gallery", "feed-video", "feed-unused"]
    )
    runtime = RuntimeFixture()
    downloader = FakeDetailDownloader()
    service = build_service(database, runtime, downloader)

    result = await service.process_snapshot(
        snapshot_id,
        selected_feed_ids=["feed-video", "feed-gallery", "feed-image"],
    )

    assert [item.feed_id for item in result.items] == [
        "feed-image",
        "feed-gallery",
        "feed-video",
    ]
    assert [item.media_status for item in result.items] == [
        "media_succeeded",
        "media_succeeded",
        "video_deferred",
    ]
    assert set(runtime.calls) == {"feed-image", "feed-gallery", "feed-video"}
    assert "feed-unused" not in runtime.calls
    assert {detail.work_id for detail, _ in downloader.calls} == {
        "feed-image",
        "feed-gallery",
    }
    assert len(downloader.calls) == 3

    restarted_runtime = RuntimeFixture()
    restarted = build_service(database, restarted_runtime, FakeDetailDownloader())
    readback = await restarted.process_snapshot(
        snapshot_id,
        selected_feed_ids=["feed-video", "feed-gallery", "feed-image"],
    )

    assert readback == result
    assert restarted_runtime.calls == []
