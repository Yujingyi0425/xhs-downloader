"""TC4 service-level restart recovery and CAS semantic tests."""

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from xhs_adapters.sqlite.video_content import SqliteCollectionVideoContentRepository
from xhs_core.application.video_processing import VideoProcessingService
from xhs_core.domain import (
    CollectionFeedAccessContext,
    CollectionFeedDetail,
    CollectionFeedEnrichment,
    CollectionSnapshotItem,
    CollectionVideoContent,
    FeedAuthor,
    FeedMediaResource,
    FeedMediaResult,
    VideoOcrResult,
    VideoProcessingStatus,
    VideoTranscript,
)
from xhs_core.domain.errors import DownloadError, InvalidPartialContentError


@pytest.mark.asyncio
async def test_service_restart_recovers_running_and_fences_stale_worker(
    tmp_path: Path,
) -> None:
    """验证服务重启恢复、单调 attempt 和 stale worker fencing。

    Args:
        tmp_path: pytest 提供的临时目录。
    """
    now = datetime.now(UTC)
    repository = SqliteCollectionVideoContentRepository(tmp_path / "video.db")
    running = CollectionVideoContent(
        snapshot_id="snapshot",
        feed_id="feed",
        status=VideoProcessingStatus.RUNNING,
        attempt_count=1,
    )
    await repository.save(running)
    events: list[str] = []
    enrichment = CollectionFeedEnrichment(
        snapshot_id="snapshot",
        feed_id="feed",
        status="succeeded",
        detail=CollectionFeedDetail(
            feed_id="feed",
            note_type="video",
            author=FeedAuthor(user_id="author"),
        ),
        created_at=now,
        updated_at=now,
        enriched_at=now,
    )

    async def _list_items(_snapshot_id):
        return [
            CollectionSnapshotItem(
                snapshot_id="snapshot", feed_id="image-feed", source_order=0
            ),
            CollectionSnapshotItem(
                snapshot_id="snapshot", feed_id="feed", source_order=1
            ),
        ]

    async def _get_access(_feed_id):
        events.append("access")
        return CollectionFeedAccessContext(
            feed_id="feed",
            latest_xsec_token="synthetic-xsec-never-persist",
            token_updated_at=now,
            last_seen_at=now,
        )

    async def _get_enrichment(_snapshot_id, _feed_id):
        return enrichment if _feed_id == "feed" else None

    async def _acquire(_feed_id, _token, _request_id):
        events.append("acquire")
        return FeedMediaResult(
            feed_id="feed",
            note_type="video",
            media=[
                FeedMediaResource(
                    index=1,
                    kind="video",
                    url="https://example.invalid/transient-signed-media",
                    suffix="mp4",
                )
            ],
        )

    async def _save_artifact(_snapshot_id, _feed_id, _media):
        events.append("artifact")
        return "safe-id/source.mp4", "a" * 64, 4

    def _inspect(_path):
        events.append("inspect")
        return 1.0, []

    def _transcribe(_path):
        events.append("transcribe")
        return VideoTranscript()

    def _recognize(_frames):
        events.append("recognize")
        return VideoOcrResult()

    collections = SimpleNamespace(
        list_snapshot_items=_list_items, get_feed_access_context=_get_access
    )
    enrichments = SimpleNamespace(get_enrichment=_get_enrichment)
    media = SimpleNamespace(acquire=_acquire)
    artifacts = SimpleNamespace(save=_save_artifact)
    reopened = SqliteCollectionVideoContentRepository(tmp_path / "video.db")
    service = VideoProcessingService(
        collections,
        enrichments,
        reopened,
        media,
        artifacts,
        SimpleNamespace(inspect=_inspect),
        SimpleNamespace(transcribe=_transcribe),
        SimpleNamespace(recognize=_recognize),
    )

    results = await service.process_snapshot("snapshot")
    assert results[0].status is VideoProcessingStatus.SUCCEEDED, events
    assert results[0].attempt_count == 2
    assert "transcribe" not in events
    assert "recognize" not in events
    authoritative = await reopened.get("snapshot", "feed")
    assert authoritative == results[0]
    assert results[0].feed_id == "feed"
    assert await reopened.get("snapshot", "image-feed") is None
    raw_db = (tmp_path / "video.db").read_bytes()
    assert b"synthetic-xsec-never-persist" not in raw_db
    assert b"transient-signed-media" not in raw_db

    stale = running.model_copy(
        update={"status": VideoProcessingStatus.FAILED_RETRYABLE}
    )
    assert await service._persist(stale) == authoritative
    assert await reopened.get("snapshot", "feed") == authoritative


@pytest.mark.asyncio
async def test_successful_video_clears_stale_error_code(tmp_path: Path) -> None:
    """成功回读时清除历史失败尝试留下的错误码。"""
    now = datetime.now(UTC)
    repository = SqliteCollectionVideoContentRepository(tmp_path / "video.db")
    stale = CollectionVideoContent(
        snapshot_id="snapshot",
        feed_id="feed",
        status=VideoProcessingStatus.SUCCEEDED,
        acquisition_status="succeeded",
        stt_status="succeeded",
        ocr_status="succeeded",
        last_error_code="media_download_failed",
    )
    await repository.save(stale)
    enrichment = CollectionFeedEnrichment(
        snapshot_id="snapshot",
        feed_id="feed",
        status="succeeded",
        detail=CollectionFeedDetail(
            feed_id="feed",
            note_type="video",
            author=FeedAuthor(user_id="author"),
        ),
        created_at=now,
        updated_at=now,
        enriched_at=now,
    )

    async def _list_items(_snapshot_id):
        return [
            CollectionSnapshotItem(
                snapshot_id="snapshot", feed_id="feed", source_order=0
            )
        ]

    async def _get_access(_feed_id):
        return None

    async def _get_enrichment(_snapshot_id, _feed_id):
        return enrichment

    service = VideoProcessingService(
        SimpleNamespace(
            list_snapshot_items=_list_items,
            get_feed_access_context=_get_access,
        ),
        SimpleNamespace(get_enrichment=_get_enrichment),
        repository,
        SimpleNamespace(),
        SimpleNamespace(),
    )

    result = (await service.process_snapshot("snapshot"))[0]
    assert result.status is VideoProcessingStatus.SUCCEEDED
    assert result.last_error_code is None
    assert (await repository.get("snapshot", "feed")).last_error_code is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure", ["access", "acquire", "download", "partial", "identity"]
)
async def test_video_failures_are_explicit_and_non_success(
    tmp_path: Path, failure: str
) -> None:
    """验证访问、获取、下载和 partial failure 都不会伪装成功。

    Args:
        tmp_path: pytest 提供的临时目录。
        failure: 要注入的 synthetic failure 类型。
    """
    now = datetime.now(UTC)
    repository = SqliteCollectionVideoContentRepository(tmp_path / "video.db")
    enrichment = CollectionFeedEnrichment(
        snapshot_id="snapshot",
        feed_id="feed",
        status="succeeded",
        detail=CollectionFeedDetail(
            feed_id="feed",
            note_type="video",
            author=FeedAuthor(user_id="author"),
        ),
        created_at=now,
        updated_at=now,
        enriched_at=now,
    )

    async def _list_items(_snapshot_id):
        return [
            CollectionSnapshotItem(
                snapshot_id="snapshot", feed_id="feed", source_order=0
            )
        ]

    async def _get_enrichment(_snapshot_id, _feed_id):
        return enrichment

    async def _get_access(_feed_id):
        if failure == "access":
            return None
        return CollectionFeedAccessContext(
            feed_id="feed",
            latest_xsec_token="synthetic-xsec-never-copy",
            token_updated_at=now,
            last_seen_at=now,
        )

    async def _acquire(_feed_id, _token, _request_id):
        if failure == "acquire":
            raise DownloadError("synthetic acquisition failure")
        return FeedMediaResult(
            feed_id="other-feed" if failure == "identity" else "feed",
            note_type="video",
            media=[
                FeedMediaResource(
                    index=1,
                    kind="video",
                    url="https://example.invalid/transient-signed-secret-media",
                    suffix="mp4",
                )
            ],
        )

    async def _save_artifact(_snapshot_id, _feed_id, _media):
        if failure == "download":
            raise DownloadError("synthetic download failure")
        if failure == "partial":
            raise InvalidPartialContentError("synthetic partial failure")
        return "safe/source.mp4", "a" * 64, 10

    def _inspect(_path):
        return 1.0, []

    def _transcribe(_path):
        return VideoTranscript()

    def _recognize(_frames):
        return VideoOcrResult()

    service = VideoProcessingService(
        SimpleNamespace(
            list_snapshot_items=_list_items, get_feed_access_context=_get_access
        ),
        SimpleNamespace(get_enrichment=_get_enrichment),
        repository,
        SimpleNamespace(acquire=_acquire),
        SimpleNamespace(save=_save_artifact),
        SimpleNamespace(inspect=_inspect),
        SimpleNamespace(transcribe=_transcribe),
        SimpleNamespace(recognize=_recognize),
    )

    results = await service.process_snapshot("snapshot")
    assert results[0].status is VideoProcessingStatus.FAILED_RETRYABLE
    assert not results[0].artifact.local_video_available
    assert results[0].transcript is None
    assert results[0].ocr is None
    raw_db = (tmp_path / "video.db").read_bytes()
    assert b"synthetic-xsec-never-copy" not in raw_db
    assert b"transient-signed-secret-media" not in raw_db
