"""TC4-R6 synthetic source-artifact handoff and restart proof."""

from asyncio import to_thread
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar

import pytest
from xhs_adapters.sqlite.video_content import SqliteCollectionVideoContentRepository
from xhs_adapters.video import SafeVideoArtifactStore
from xhs_core.application.video_processing import VideoProcessingService
from xhs_core.domain import (
    CollectionFeedAccessContext,
    CollectionFeedDetail,
    CollectionFeedEnrichment,
    CollectionSnapshotItem,
    FeedAuthor,
    FeedMediaResource,
    FeedMediaResult,
    VideoProcessingStatus,
)


class _Response:
    status_code = 200
    headers: ClassVar[dict[str, str]] = {}

    def __init__(self, data: bytes) -> None:
        self._data = data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def aiter_bytes(self, _chunk_size=None):
        yield self._data


class _Gateway:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def stream(self, _url: str, _headers=None):
        return _Response(self.data)


class _MappingGateway:
    def __init__(self, responses: dict[str, bytes]) -> None:
        self.responses = responses
        self.requested: list[str] = []

    def stream(self, url: str, _headers=None):
        self.requested.append(url)
        return _Response(self.responses[url])


@pytest.mark.asyncio
async def test_video_artifact_handoff_survives_repository_reopen(
    tmp_path: Path,
) -> None:
    """验证默认保留的 source artifact 可跨仓储重开按摘要读取。

    Args:
        tmp_path: pytest 提供的临时目录。
    """
    data = b"synthetic-r6-video-bytes"
    snapshot_id = "snapshot-r6"
    feed_id = "feed-r6"
    database = tmp_path / "video.db"
    artifact_root = tmp_path / "artifacts"
    now = datetime.now(UTC)
    enrichment = CollectionFeedEnrichment(
        snapshot_id=snapshot_id,
        feed_id=feed_id,
        status="succeeded",
        detail=CollectionFeedDetail(
            feed_id=feed_id,
            note_type="video",
            author=FeedAuthor(user_id="synthetic-author"),
        ),
        created_at=now,
        updated_at=now,
        enriched_at=now,
    )
    acquisitions = 0

    async def list_items(_snapshot_id):
        return [
            CollectionSnapshotItem(
                snapshot_id=snapshot_id, feed_id=feed_id, source_order=0
            )
        ]

    async def get_access(_feed_id):
        return CollectionFeedAccessContext(
            feed_id=feed_id,
            latest_xsec_token="synthetic-r6-token",
            token_updated_at=now,
            last_seen_at=now,
        )

    async def get_enrichment(_snapshot_id, _feed_id):
        return enrichment

    async def acquire(_feed_id, _token, _request_id):
        nonlocal acquisitions
        acquisitions += 1
        return FeedMediaResult(
            feed_id=feed_id,
            note_type="video",
            media=[
                FeedMediaResource(
                    index=1,
                    kind="video",
                    url="https://example.invalid/synthetic-r6-video",
                    suffix="mp4",
                )
            ],
        )

    collections = SimpleNamespace(
        list_snapshot_items=list_items, get_feed_access_context=get_access
    )
    service = VideoProcessingService(
        collections,
        SimpleNamespace(get_enrichment=get_enrichment),
        SqliteCollectionVideoContentRepository(database),
        SimpleNamespace(acquire=acquire),
        SafeVideoArtifactStore(artifact_root, _Gateway(data)),
    )

    result = (await service.process_snapshot(snapshot_id))[0]
    assert result.status is VideoProcessingStatus.SUCCEEDED
    assert result.artifact.local_video_available
    assert result.artifact.relative_path
    assert not Path(result.artifact.relative_path).is_absolute()
    assert result.artifact.sha256 == sha256(data).hexdigest()
    assert result.artifact.size == len(data)

    reopened_repository = SqliteCollectionVideoContentRepository(database)
    reopened = await reopened_repository.get(snapshot_id, feed_id)
    assert reopened == result
    physical = Path(
        SafeVideoArtifactStore(artifact_root, _Gateway(b"unused")).resolve_path(
            result.artifact.relative_path
        )
    )
    stored = await to_thread(physical.read_bytes)
    assert stored == data
    assert sha256(stored).hexdigest() == result.artifact.sha256
    assert acquisitions == 1
    raw_db = await to_thread(database.read_bytes)
    assert b"synthetic-r6-token" not in raw_db
    assert b"synthetic-r6-video" not in raw_db


@pytest.mark.asyncio
async def test_video_service_keep_source_false_cleans_and_persists_metadata(
    tmp_path: Path,
) -> None:
    """验证服务级显式清理仍保留准确摘要并可跨仓储重开。

    Args:
        tmp_path: pytest 提供的临时目录。
    """
    data = b"synthetic-r6-cleanup-bytes"
    snapshot_id = "snapshot-r6-cleanup"
    feed_id = "feed-r6-cleanup"
    database = tmp_path / "video.db"
    artifact_root = tmp_path / "artifacts"
    now = datetime.now(UTC)
    enrichment = CollectionFeedEnrichment(
        snapshot_id=snapshot_id,
        feed_id=feed_id,
        status="succeeded",
        detail=CollectionFeedDetail(
            feed_id=feed_id,
            note_type="video",
            author=FeedAuthor(user_id="synthetic-author"),
        ),
        created_at=now,
        updated_at=now,
        enriched_at=now,
    )

    async def list_items(_snapshot_id):
        return [
            CollectionSnapshotItem(
                snapshot_id=snapshot_id, feed_id=feed_id, source_order=0
            )
        ]

    async def get_access(_feed_id):
        return CollectionFeedAccessContext(
            feed_id=feed_id,
            latest_xsec_token="synthetic-r6-cleanup-token",
            token_updated_at=now,
            last_seen_at=now,
        )

    async def get_enrichment(_snapshot_id, _feed_id):
        return enrichment

    async def acquire(_feed_id, _token, _request_id):
        return FeedMediaResult(
            feed_id=feed_id,
            note_type="video",
            media=[
                FeedMediaResource(
                    index=1,
                    kind="video",
                    url="https://example.invalid/r6-cleanup-video",
                    suffix="mp4",
                )
            ],
        )

    service = VideoProcessingService(
        SimpleNamespace(
            list_snapshot_items=list_items, get_feed_access_context=get_access
        ),
        SimpleNamespace(get_enrichment=get_enrichment),
        SqliteCollectionVideoContentRepository(database),
        SimpleNamespace(acquire=acquire),
        SafeVideoArtifactStore(artifact_root, _Gateway(data)),
    )
    result = (await service.process_snapshot(snapshot_id, keep_source=False))[0]

    assert result.status is VideoProcessingStatus.SUCCEEDED
    assert result.acquisition_status.value == "succeeded"
    assert not result.artifact.local_video_available
    assert result.artifact.relative_path is None
    assert result.artifact.sha256 == sha256(data).hexdigest()
    assert result.artifact.size == len(data)
    assert not list(artifact_root.rglob("source.mp4"))
    reopened = await SqliteCollectionVideoContentRepository(database).get(
        snapshot_id, feed_id
    )
    assert reopened == result
    assert reopened.artifact.sha256 == sha256(data).hexdigest()
    assert reopened.artifact.size == len(data)


@pytest.mark.asyncio
async def test_video_artifact_store_selects_video_resource_by_kind(
    tmp_path: Path,
) -> None:
    """验证混合 locator 只下载 video，且无 video 时 fail closed。

    Args:
        tmp_path: pytest 提供的临时目录。
    """
    image_url = "https://example.invalid/r6-image"
    video_url = "https://example.invalid/r6-video"
    image_data = b"image-bytes-must-not-be-selected"
    video_data = b"video-bytes-selected"
    gateway = _MappingGateway({image_url: image_data, video_url: video_data})
    store = SafeVideoArtifactStore(tmp_path, gateway)
    locator = FeedMediaResult(
        feed_id="feed",
        note_type="video",
        media=[
            FeedMediaResource(index=1, kind="image", url=image_url, suffix="jpg"),
            FeedMediaResource(index=2, kind="video", url=video_url, suffix="mp4"),
        ],
    )

    relative, digest, size = await store.save("snapshot", "feed", locator)
    physical = Path(store.resolve_path(relative))
    stored = await to_thread(physical.read_bytes)
    assert gateway.requested == [video_url]
    assert stored == video_data
    assert image_data not in stored
    assert digest == sha256(video_data).hexdigest()
    assert size == len(video_data)

    with pytest.raises(LookupError):
        await store.save(
            "snapshot-no-video",
            "feed-no-video",
            FeedMediaResult(
                feed_id="feed-no-video",
                note_type="video",
                media=[
                    FeedMediaResource(
                        index=1, kind="image", url=image_url, suffix="jpg"
                    )
                ],
            ),
        )
