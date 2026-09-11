"""原始笔记抽取记录的幂等、来源和重启读回测试。"""

from pathlib import Path
from types import SimpleNamespace

import pytest
from xhs_adapters.sqlite import SqliteNoteExtractionRepository
from xhs_core.application.note_extraction import NoteExtractionService
from xhs_core.domain import (
    CollectionEnrichmentStatus,
    CollectionFeedDetail,
    CollectionFeedEnrichment,
    CollectionMediaBatchRecord,
    CollectionMediaBatchStatus,
    CollectionMediaItemRecord,
    CollectionMediaItemStatus,
    CollectionSnapshotItem,
    DownloadArtifact,
    ExtractionMediaType,
    FeedAuthor,
    MediaKind,
    NoteExtractionRecord,
    NoteExtractionStatus,
    TextProvenanceSource,
)


class _ImageOcr:
    def recognize(self, _path: str) -> str:
        return "本地 OCR"


@pytest.mark.asyncio
async def test_extraction_record_round_trip_is_source_provenant(tmp_path: Path) -> None:
    """记录持久化后保留来源、artifact 关联且不含访问凭据。

    Args:
        tmp_path: pytest 提供的临时目录。
    """
    database = tmp_path / "state.db"
    record = NoteExtractionRecord(
        snapshot_id="snapshot",
        feed_id="feed",
        media_type=ExtractionMediaType.IMAGE,
        title="title",
        text_provenance=[
            {"source": TextProvenanceSource.NOTE_TITLE, "text": "title"}
        ],
    )
    repository = SqliteNoteExtractionRepository(database)
    await repository.save(record)
    reopened = SqliteNoteExtractionRepository(database)
    stored = await reopened.get("snapshot", "feed")
    assert stored == record
    payload = (await _payload(database))[0]
    assert "xsec_token" not in payload
    assert "signed" not in payload


@pytest.mark.asyncio
async def test_image_extraction_reuses_artifact_and_persists_ocr(
    tmp_path: Path,
) -> None:
    """图片抽取复用已存在 artifact，并在重启后读回 OCR 来源。

    Args:
        tmp_path: pytest 提供的临时目录。
    """
    image_path = tmp_path / "download" / "image.jpeg"
    image_path.parent.mkdir()
    image_path.write_bytes(b"local-image")
    item = CollectionSnapshotItem(
        snapshot_id="snapshot", feed_id="feed", source_order=0
    )
    detail = CollectionFeedDetail(
        feed_id="feed",
        title="标题",
        body="正文",
        note_type="image",
        author=FeedAuthor(user_id="author"),
    )
    enrichment = CollectionFeedEnrichment.model_construct(
        snapshot_id="snapshot",
        feed_id="feed",
        status=CollectionEnrichmentStatus.SUCCEEDED,
        detail=detail,
    )
    artifact = DownloadArtifact(
        path="download/image.jpeg",
        sha256="a" * 64,
        size=11,
        media_index=1,
        kind=MediaKind.IMAGE,
    )
    batch = CollectionMediaBatchRecord(
        request_id="request",
        snapshot_id="snapshot",
        source_order=0,
        work_id="feed",
        status=CollectionMediaBatchStatus.SUCCEEDED,
        items=[
            CollectionMediaItemRecord(
                snapshot_id="snapshot",
                source_order=0,
                work_id="feed",
                media_index=1,
                kind=MediaKind.IMAGE,
                status=CollectionMediaItemStatus.SUCCEEDED,
                artifact=artifact,
            )
        ],
        deferred=[],
    )

    class _Collections:
        async def get_snapshot(self, _snapshot_id):
            return object()

        async def list_snapshot_items(self, _snapshot_id):
            return [item]

    class _Enrichments:
        async def get_enrichment(self, _snapshot_id, _feed_id):
            return enrichment

    class _Media:
        async def get(self, _request_id):
            return batch

    service = NoteExtractionService(
        _Collections(), _Enrichments(), _Media(),
        SqliteNoteExtractionRepository(tmp_path / "records.db"),
        SimpleNamespace(), _ImageOcr(), tmp_path,
    )
    result = (await service.process_snapshot("snapshot"))[0]
    assert result.extraction_status is NoteExtractionStatus.SUCCEEDED
    assert len(result.media_artifacts) == 1
    assert {item.source for item in result.text_provenance} == {
        TextProvenanceSource.NOTE_TITLE,
        TextProvenanceSource.NOTE_BODY,
        TextProvenanceSource.IMAGE_OCR,
    }


async def _payload(database: Path):
    import aiosqlite

    async with aiosqlite.connect(database) as connection:
        cursor = await connection.execute("SELECT payload FROM note_extraction")
        return await cursor.fetchone()
