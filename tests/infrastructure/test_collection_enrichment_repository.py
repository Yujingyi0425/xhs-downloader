"""收藏详情 enrichment domain/SQLite 合成测试。"""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from aiosqlite import IntegrityError
from pydantic import SecretStr
from xhs_adapters.sqlite.collection_enrichments import (
    SqliteCollectionEnrichmentRepository,
)
from xhs_adapters.sqlite.collection_storage import (
    ensure_collection_foreign_keys,
    initialize_collection_storage,
)
from xhs_adapters.sqlite.collections import SqliteCollectionRepository
from xhs_adapters.sqlite.connection import connect
from xhs_core.domain.collection import (
    CollectionImportCommand,
    CollectionImportItem,
    collection_fingerprint,
)
from xhs_core.domain.collection_enrichment import (
    CollectionEnrichmentStatus,
    CollectionFeedDetail,
)
from xhs_core.domain.collection_enrichment_ports import EnrichmentStateConflictError
from xhs_core.domain.feeds import FeedAuthor, FeedDetailResult, FeedMetrics


def import_command(request_id: str, feeds: list[str]) -> CollectionImportCommand:
    """构造不含真实数据的收藏导入命令。

    Args:
        request_id: 合成请求标识。
        feeds: 合成 feed 标识列表。

    Returns:
        合成收藏导入命令。
    """
    return CollectionImportCommand(
        request_id=request_id,
        source_type="board",
        board_id="synthetic-board",
        items=[
            CollectionImportItem(
                feed_id=feed,
                xsec_token=SecretStr("synthetic-import-token"),
                source_order=index,
            )
            for index, feed in enumerate(feeds)
        ],
    )


async def create_snapshot(database: Path, feeds: list[str]) -> str:
    """创建 synthetic TC2 snapshot 并返回其 ID。

    Args:
        database: 临时 SQLite 路径。
        feeds: 合成 feed 标识列表。

    Returns:
        新建 snapshot 标识。
    """
    repository = SqliteCollectionRepository(database)
    command = import_command("synthetic-request", feeds)
    snapshot, _ = await repository.import_snapshot(
        command,
        collection_fingerprint(command),
        datetime(2026, 1, 1, tzinfo=UTC),
    )
    return snapshot.snapshot_id


def detail(feed_id: str = "feed-a") -> FeedDetailResult:
    """构造包含嵌套评论的 synthetic 详情结果。

    Args:
        feed_id: 合成 feed 标识。

    Returns:
        合成详情结果。
    """
    author = FeedAuthor(user_id="author-a", nickname="合成作者")
    return FeedDetailResult(
        feed_id=feed_id,
        xsec_token="synthetic-xsec-never-persist",
        title="合成标题",
        body="Unicode 正文",
        author=author,
        metrics=FeedMetrics(liked=True, liked_count="7"),
        image_urls=["https://example.invalid/image.jpg"],
        published_at=1_700_000_000,
        ip_location="合成地点",
    )


@pytest.mark.asyncio
async def test_domain_conversion_and_status_contract() -> None:
    """验证状态集合、身份转换和敏感字段显式排除。"""
    converted = CollectionFeedDetail.from_feed_detail(detail(), "feed-a")
    assert converted.title == "合成标题"
    assert "xsec_token" not in converted.model_dump()
    assert "comments_cursor" not in converted.model_dump()
    assert "synthetic-xsec-never-persist" not in converted.model_dump_json()
    with pytest.raises(ValueError, match="feed_id"):
        CollectionFeedDetail.from_feed_detail(detail(), "feed-other")
    assert CollectionEnrichmentStatus.PENDING not in {
        CollectionEnrichmentStatus.SUCCEEDED,
        CollectionEnrichmentStatus.FAILED_TERMINAL,
        CollectionEnrichmentStatus.NEEDS_REIMPORT,
        CollectionEnrichmentStatus.NEEDS_REVIEW,
    }


@pytest.mark.asyncio
async def test_create_cas_success_and_stale_failure_are_safe(tmp_path: Path) -> None:
    """验证创建幂等、CAS、attempt 一次递增和成功保护。

    Args:
        tmp_path: Pytest 临时目录。
    """
    database = tmp_path / "state.db"
    snapshot_id = await create_snapshot(database, ["feed-a", "feed-b"])
    repository = SqliteCollectionEnrichmentRepository(database)
    first = await repository.ensure_enrichment(snapshot_id, "feed-a")
    second = await repository.ensure_enrichment(snapshot_id, "feed-a")
    assert first == second
    running = await repository.transition_enrichment(
        snapshot_id,
        "feed-a",
        {CollectionEnrichmentStatus.PENDING},
        CollectionEnrichmentStatus.RUNNING,
    )
    assert running.attempt_count == 1
    again = await repository.transition_enrichment(
        snapshot_id,
        "feed-a",
        {CollectionEnrichmentStatus.RUNNING},
        CollectionEnrichmentStatus.RUNNING,
    )
    assert again.attempt_count == 1
    succeeded = await repository.save_detail(
        snapshot_id, "feed-a", CollectionFeedDetail.from_feed_detail(detail(), "feed-a")
    )
    assert succeeded.status is CollectionEnrichmentStatus.SUCCEEDED
    assert succeeded.detail is not None and succeeded.enriched_at is not None
    with pytest.raises(EnrichmentStateConflictError):
        await repository.transition_enrichment(
            snapshot_id,
            "feed-a",
            {CollectionEnrichmentStatus.RUNNING},
            CollectionEnrichmentStatus.FAILED_RETRYABLE,
            error_code="late-worker",
        )
    assert (
        await repository.get_enrichment(snapshot_id, "feed-a")
    ).status is CollectionEnrichmentStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_fk_order_restart_and_tc2_data_are_preserved(tmp_path: Path) -> None:
    """验证孤儿拒绝、source_order 排序、重启 round-trip 与 TC2 数据不变。

    Args:
        tmp_path: Pytest 临时目录。
    """
    database = tmp_path / "state.db"
    snapshot_id = await create_snapshot(database, ["feed-b", "feed-a"])
    repository = SqliteCollectionEnrichmentRepository(database)
    await repository.ensure_enrichment(snapshot_id, "feed-b")
    await repository.ensure_enrichment(snapshot_id, "feed-a")
    await repository.transition_enrichment(
        snapshot_id,
        "feed-a",
        {CollectionEnrichmentStatus.PENDING},
        CollectionEnrichmentStatus.FAILED_RETRYABLE,
        error_code="synthetic-timeout",
    )
    await repository.ensure_enrichment(snapshot_id, "feed-a")
    listed = await repository.list_snapshot_enrichments(snapshot_id)
    assert [item.feed_id for item in listed] == ["feed-b", "feed-a"]
    assert listed[0].attempt_count == 0
    assert listed[1].status is CollectionEnrichmentStatus.FAILED_RETRYABLE
    reopened = SqliteCollectionEnrichmentRepository(database)
    assert (
        await reopened.get_enrichment(snapshot_id, "feed-a")
    ).status is CollectionEnrichmentStatus.FAILED_RETRYABLE
    async with connect(database) as connection:
        await ensure_collection_foreign_keys(connection)
        columns = await connection.execute_fetchall(
            "PRAGMA table_info(collection_feed_enrichment)"
        )
        assert not {str(row[1]) for row in columns} & {
            "xsec_token",
            "access_context",
            "source_url",
        }
        with pytest.raises(IntegrityError):
            await connection.execute(
                """INSERT INTO collection_feed_enrichment
                (snapshot_id, feed_id, enrichment_version, status,
                 attempt_count, created_at, updated_at)
                VALUES ('missing', 'missing', 1, 'pending', 0, 'now', 'now')"""
            )
    await initialize_collection_storage(database)
    tc2 = SqliteCollectionRepository(database)
    snapshot = await tc2.get_snapshot(snapshot_id)
    assert snapshot is not None and snapshot.item_count == 2
    assert [item.feed_id for item in await tc2.list_snapshot_items(snapshot_id)] == [
        "feed-b",
        "feed-a",
    ]
    assert (
        await tc2.get_feed_access_context("feed-a")
    ).latest_xsec_token.get_secret_value() == "synthetic-import-token"


@pytest.mark.asyncio
async def test_detail_round_trip_and_failure_does_not_persist_partial(
    tmp_path: Path,
) -> None:
    """验证详情序列化、成功不变量和身份错误不会落半截结果。

    Args:
        tmp_path: Pytest 临时目录。
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
    reopened = SqliteCollectionEnrichmentRepository(database)
    loaded = await reopened.get_enrichment(snapshot_id, "feed-a")
    assert loaded == saved
    assert loaded.detail is not None and loaded.detail.body == "Unicode 正文"
    assert "synthetic-xsec-never-persist" not in repr(loaded)
