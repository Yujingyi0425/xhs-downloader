"""Synthetic detail serialization and redaction tests."""

from pathlib import Path

import pytest
from xhs_adapters.sqlite.collection_enrichments import (
    SqliteCollectionEnrichmentRepository,
)
from xhs_adapters.sqlite.connection import connect
from xhs_core.domain.collection_enrichment import (
    CollectionEnrichmentStatus,
    CollectionFeedDetail,
)

from .collection_enrichment_fixtures import create_snapshot, detail


@pytest.mark.asyncio
async def test_detail_round_trip_and_failure_does_not_persist_partial(
    tmp_path: Path,
) -> None:
    """Verify detail round-trip and rejection without partial persistence.

    Args:
        tmp_path: Pytest temporary directory.
    """
    database = tmp_path / "state.db"
    snapshot_id = await create_snapshot(database, ["feed-a"])
    repository = SqliteCollectionEnrichmentRepository(database)
    await repository.ensure_enrichment(snapshot_id, "feed-a")
    await repository.transition_enrichment(
        snapshot_id,
        "feed-a",
        {CollectionEnrichmentStatus.PENDING},
        CollectionEnrichmentStatus.RUNNING,
    )
    with pytest.raises(ValueError, match="feed_id"):
        await repository.save_detail(
            snapshot_id,
            "feed-a",
            CollectionFeedDetail.from_feed_detail(detail(), "feed-a").model_copy(
                update={"feed_id": "other"}
            ),
        )
    failed = await repository.get_enrichment(snapshot_id, "feed-a")
    assert failed.status is CollectionEnrichmentStatus.RUNNING
    assert failed.detail is None and failed.enriched_at is None
    saved = await repository.save_detail(
        snapshot_id, "feed-a", CollectionFeedDetail.from_feed_detail(detail(), "feed-a")
    )
    loaded = await SqliteCollectionEnrichmentRepository(database).get_enrichment(
        snapshot_id, "feed-a"
    )
    assert loaded == saved
    assert loaded.detail is not None
    assert loaded.detail.body == "Unicode 正文"
    assert loaded.detail.comments[0].replies[0].content == "合成回复"
    assert loaded.detail.comments_has_more is True
    assert "synthetic-xsec-never-persist" not in repr(loaded)
    async with connect(database) as connection:
        cursor = await connection.execute(
            "SELECT detail_json FROM collection_feed_enrichment"
        )
        row = await cursor.fetchone()
        raw = str(row[0])
        assert '"xsec_token"' not in raw
        assert "synthetic-xsec-never-persist" not in raw
        assert '"comments_cursor"' not in raw


def test_detail_normalizes_legacy_temporary_image_route() -> None:
    """新持久化详情不应继续保存带临时路由的图片地址。"""
    converted = CollectionFeedDetail.from_feed_detail(
        detail().model_copy(
            update={
                "image_urls": [
                    "http://sns-webpic-qc.xhscdn.com/202609072122/"
                    "726496a2ef314128a8a3cec0155bd038/notes_pre_post!nd_dft_wlteh_webp_3"
                ]
            }
        ),
        "feed-a",
    )
    assert converted.image_urls == ["https://sns-img-bd.xhscdn.com/notes_pre_post"]
