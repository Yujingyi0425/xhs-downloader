"""收藏快照契约与 FK 合成回归测试。"""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError
from xhs_adapters.sqlite.collection_storage import ensure_collection_foreign_keys
from xhs_adapters.sqlite.collections import SqliteCollectionRepository
from xhs_adapters.sqlite.connection import connect
from xhs_core.application.collection_import import CollectionImportService
from xhs_core.domain.collection import (
    CollectionFeedAccessContext,
    CollectionImportCommand,
    CollectionImportItem,
    collection_fingerprint,
)

from .test_collection_repository import command


@pytest.mark.asyncio
async def test_reorder_changes_fingerprint_but_not_set_diff(tmp_path: Path) -> None:
    """验证重排只改变有序 fingerprint，集合差异仍全为 retained。

    Args:
        tmp_path: Pytest 临时目录。
    """
    repository = SqliteCollectionRepository(tmp_path / "state.db")
    first = command("first", ["feed-a", "feed-b", "feed-c"])
    second = command("second", ["feed-c", "feed-b", "feed-a"])
    first_snapshot, _ = await repository.import_snapshot(
        first, collection_fingerprint(first), datetime.now(UTC)
    )
    second_snapshot, diff = await repository.import_snapshot(
        second, collection_fingerprint(second), datetime.now(UTC)
    )
    assert first_snapshot.board_revision == 1
    assert second_snapshot.board_revision == 2
    assert collection_fingerprint(first) != collection_fingerprint(second)
    assert diff.added == []
    assert diff.removed == []
    assert diff.retained == ["feed-a", "feed-b", "feed-c"]


@pytest.mark.asyncio
async def test_fk_constraint_and_pre_commit_result_rollback(tmp_path: Path) -> None:
    """验证真实 FK constraint 与 COMMIT 前 result preparation 回滚。

    Args:
        tmp_path: Pytest 临时目录。
    """
    import sqlite3

    database = tmp_path / "state.db"
    repository = SqliteCollectionRepository(database)
    await repository._initialize()
    async with connect(database) as connection:
        await ensure_collection_foreign_keys(connection)
        with pytest.raises(sqlite3.IntegrityError):
            await connection.execute(
                """
                INSERT INTO collection_snapshot_item
                (snapshot_id, feed_id, source_order)
                VALUES ('missing', 'missing', 0)
                """
            )
        await connection.rollback()

    class PreparationFailingRepository(SqliteCollectionRepository):
        async def _prepare_result(self, snapshot, previous_items, current_items):
            raise RuntimeError("synthetic result preparation failure")

    failing = PreparationFailingRepository(database)
    with pytest.raises(RuntimeError) as error:
        command_value = command(
            "prepare-failure", ["feed-a"], "synthetic-secret-token-never-leak"
        )
        await CollectionImportService(failing).import_snapshot(command_value)
    assert "synthetic-secret-token-never-leak" not in str(error.value)
    assert await repository.get_latest_snapshot("board", "synthetic-board") is None


def test_duplicate_feed_and_token_sentinel_are_redacted(caplog) -> None:
    """验证 duplicate feed、领域 repr、validation error 和日志不泄露 sentinel。

    Args:
        caplog: Pytest 日志捕获 fixture。
    """
    sentinel = "synthetic-secret-token-never-leak"
    item = CollectionImportItem(
        feed_id="feed-a", xsec_token=SecretStr(sentinel), source_order=0
    )
    with pytest.raises(ValidationError) as error:
        CollectionImportCommand(
            request_id="duplicate",
            source_type="board",
            board_id="synthetic-board",
            items=[
                item,
                CollectionImportItem(
                    feed_id="feed-a", xsec_token=SecretStr(sentinel), source_order=1
                ),
            ],
        )
    context = CollectionFeedAccessContext(
        feed_id="feed-a",
        latest_xsec_token=SecretStr(sentinel),
        token_updated_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )
    assert sentinel not in repr(item)
    assert sentinel not in repr(context)
    assert sentinel not in str(error.value)
    assert sentinel not in repr(error.value)
    assert all(sentinel not in record.getMessage() for record in caplog.records)
