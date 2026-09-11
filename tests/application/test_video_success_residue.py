"""视频成功态错误残留清理测试。"""

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from xhs_adapters.sqlite.video_content import SqliteCollectionVideoContentRepository
from xhs_core.application.video_processing import VideoProcessingService
from xhs_core.domain import (
    CollectionFeedDetail,
    CollectionFeedEnrichment,
    CollectionSnapshotItem,
    CollectionVideoContent,
    FeedAuthor,
    VideoProcessingStatus,
)


@pytest.mark.asyncio
async def test_successful_video_clears_stale_error_code(tmp_path: Path) -> None:
    """成功回读时清除历史失败尝试留下的错误码。

    Args:
        tmp_path: Pytest 提供的临时目录。
    """
    repository = SqliteCollectionVideoContentRepository(tmp_path / "video.db")
    stale = CollectionVideoContent(
        snapshot_id="snapshot", feed_id="feed", status=VideoProcessingStatus.SUCCEEDED,
        acquisition_status="succeeded", stt_status="succeeded", ocr_status="succeeded",
        last_error_code="media_download_failed",
    )
    await repository.save(stale)
    now = datetime.now(UTC)
    enrichment = CollectionFeedEnrichment(
        snapshot_id="snapshot", feed_id="feed", status="succeeded",
        detail=CollectionFeedDetail(
            feed_id="feed",
            note_type="video",
            author=FeedAuthor(user_id="author"),
        ),
        created_at=now, updated_at=now, enriched_at=now,
    )

    async def _items(_snapshot_id):
        return [
            CollectionSnapshotItem(
                snapshot_id="snapshot", feed_id="feed", source_order=0
            )
        ]

    async def _enrichment(_snapshot_id, _feed_id):
        return enrichment

    async def _access(_feed_id):
        return None

    service = VideoProcessingService(
        SimpleNamespace(
            list_snapshot_items=_items, get_feed_access_context=_access
        ),
        SimpleNamespace(get_enrichment=_enrichment),
        repository,
        SimpleNamespace(),
        SimpleNamespace(),
    )
    result = (await service.process_snapshot("snapshot"))[0]
    assert result.status is VideoProcessingStatus.SUCCEEDED
    assert result.last_error_code is None
    assert (await repository.get("snapshot", "feed")).last_error_code is None
