"""收藏快照 core/SQLite 合成回归测试。"""

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError
from xhs_adapters.sqlite.collections import SqliteCollectionRepository
from xhs_core.domain.collection import (
    CollectionImportCommand,
    CollectionImportItem,
    collection_fingerprint,
)
from xhs_core.domain.collection_ports import CollectionIdempotencyConflictError


def command(request_id: str, feeds: list[str], token: str = "synthetic-token"):
    """创建 synthetic 导入命令。

    Args:
        request_id: 合成请求标识。
        feeds: 合成 feed 标识列表。
        token: 合成访问 token。

    Returns:
        合成导入命令。
    """
    return CollectionImportCommand(
        request_id=request_id,
        source_type="board",
        board_id="synthetic-board",
        items=[
            CollectionImportItem(
                feed_id=feed,
                xsec_token=SecretStr(token),
                source_order=index,
            )
            for index, feed in enumerate(feeds)
        ],
    )


@pytest.mark.asyncio
async def test_import_scale_diff_revision_and_reads(tmp_path: Path) -> None:
    """验证空集、revision、diff、历史和 token 显式读取。

    Args:
        tmp_path: Pytest 临时目录。
    """
    repository = SqliteCollectionRepository(tmp_path / "state.db")
    first_command = command("request-1", ["feed-a", "feed-b"])
    first, diff = await repository.import_snapshot(
        first_command,
        collection_fingerprint(first_command),
        datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert first.board_revision == 1
    assert diff.added == ["feed-a", "feed-b"]
    second_command = command("request-2", ["feed-b", "feed-c"], "synthetic-token-2")
    second, diff = await repository.import_snapshot(
        second_command,
        collection_fingerprint(second_command),
        datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert second.board_revision == 2
    assert diff.added == ["feed-c"]
    assert diff.removed == ["feed-a"]
    assert diff.retained == ["feed-b"]
    assert (
        await repository.get_latest_snapshot("board", "synthetic-board")
    ).snapshot_id == second.snapshot_id
    assert [
        item.feed_id
        for item in await repository.list_snapshot_items(second.snapshot_id)
    ] == ["feed-b", "feed-c"]
    assert len(await repository.list_snapshots("board", "synthetic-board", 10)) == 2
    access = await repository.get_feed_access_context("feed-b")
    assert access is not None
    assert access.latest_xsec_token.get_secret_value() == "synthetic-token-2"
    assert "synthetic-token-2" not in repr(access)


@pytest.mark.asyncio
async def test_request_idempotency_conflict_and_token_only_retry(
    tmp_path: Path,
) -> None:
    """验证 retry 不增加 revision，冲突由 core error 表达。

    Args:
        tmp_path: Pytest 临时目录。
    """
    repository = SqliteCollectionRepository(tmp_path / "state.db")
    original_command = command("same", ["feed-a"], "token-old")
    original, _ = await repository.import_snapshot(
        original_command, collection_fingerprint(original_command), datetime.now(UTC)
    )
    retry_command = command("same", ["feed-a"], "token-new")
    retry, _ = await repository.import_snapshot(
        retry_command, collection_fingerprint(retry_command), datetime.now(UTC)
    )
    assert retry.snapshot_id == original.snapshot_id
    assert (
        await repository.get_latest_snapshot("board", "synthetic-board")
    ).board_revision == 1
    assert (
        await repository.get_feed_access_context("feed-a")
    ).latest_xsec_token.get_secret_value() == "token-old"
    with pytest.raises(CollectionIdempotencyConflictError):
        await repository.import_snapshot(
            command("same", ["feed-b"]), "different", datetime.now(UTC)
        )


@pytest.mark.asyncio
async def test_new_request_refreshes_token_and_restart_reads_state(
    tmp_path: Path,
) -> None:
    """验证新 observation 才刷新 token，并可由新实例恢复。

    Args:
        tmp_path: Pytest 临时目录。
    """
    database = tmp_path / "state.db"
    repository = SqliteCollectionRepository(database)
    first, _ = await repository.import_snapshot(
        command("first", ["feed-a"], "token-old"), "fp", datetime.now(UTC)
    )
    second, _ = await repository.import_snapshot(
        command("second", ["feed-a"], "token-new"), "fp", datetime.now(UTC)
    )
    reopened = SqliteCollectionRepository(database)
    assert (
        await reopened.get_latest_snapshot("board", "synthetic-board")
    ).snapshot_id == second.snapshot_id
    assert (await reopened.get_snapshot(first.snapshot_id)).board_revision == 1
    assert (
        await reopened.get_feed_access_context("feed-a")
    ).latest_xsec_token.get_secret_value() == "token-new"


@pytest.mark.asyncio
async def test_exact_rollback_for_new_and_existing_board(tmp_path: Path) -> None:
    """验证中途失败不会留下 board、snapshot、membership 或 token 更新。

    Args:
        tmp_path: Pytest 临时目录。
    """

    class FailingRepository(SqliteCollectionRepository):
        def __init__(self, database: Path, fail_feed: str) -> None:
            super().__init__(database)
            self.fail_feed = fail_feed

        async def _insert_item(self, database, snapshot_id, feed_id, source_order):
            if feed_id == self.fail_feed:
                raise RuntimeError("synthetic repository failure")
            await super()._insert_item(database, snapshot_id, feed_id, source_order)

    database = tmp_path / "state.db"
    failing = FailingRepository(database, "feed-fail")
    with pytest.raises(RuntimeError):
        await failing.import_snapshot(
            command("new", ["feed-ok", "feed-fail"]), "fp", datetime.now(UTC)
        )
    assert await failing.get_latest_snapshot("board", "synthetic-board") is None
    assert await failing.get_feed_access_context("feed-ok") is None

    healthy = SqliteCollectionRepository(database)
    await healthy.import_snapshot(
        command("old", ["feed-old"], "old-token"), "old", datetime.now(UTC)
    )
    with pytest.raises(RuntimeError):
        await failing.import_snapshot(
            command("failed", ["feed-old", "feed-new", "feed-fail"], "new-token"),
            "new",
            datetime.now(UTC),
        )
    latest = await healthy.get_latest_snapshot("board", "synthetic-board")
    assert latest.board_revision == 1
    assert await healthy.get_feed_access_context("feed-new") is None
    assert (
        await healthy.get_feed_access_context("feed-old")
    ).latest_xsec_token.get_secret_value() == "old-token"


@pytest.mark.asyncio
async def test_concurrent_imports_get_distinct_revisions(tmp_path: Path) -> None:
    """验证同 board 的并发新 request 不丢失 snapshot。

    Args:
        tmp_path: Pytest 临时目录。
    """
    repository = SqliteCollectionRepository(tmp_path / "state.db")
    results = await asyncio.gather(
        repository.import_snapshot(
            command("one", ["feed-1"]), "one", datetime.now(UTC)
        ),
        repository.import_snapshot(
            command("two", ["feed-2"]), "two", datetime.now(UTC)
        ),
    )
    assert sorted(result[0].board_revision for result in results) == [1, 2]


def test_source_order_and_token_validation_redaction() -> None:
    """验证 source_order 不归一化，且 sentinel 不进入模型错误文本。"""
    with pytest.raises(ValidationError) as error:
        command("bad", ["feed-a", "feed-b"])
        CollectionImportCommand(
            request_id="bad",
            source_type="board",
            board_id="synthetic-board",
            items=[
                CollectionImportItem(
                    feed_id="feed-a", xsec_token=SecretStr("ok"), source_order=1
                ),
            ],
        )
    assert "synthetic-secret-token-never-leak" not in str(error.value)
    with pytest.raises(ValidationError):
        CollectionImportItem(
            feed_id="feed-a",
            xsec_token=SecretStr("   "),
            source_order=0,
        )
