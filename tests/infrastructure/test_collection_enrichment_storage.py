"""Synthetic SQLite storage, ordering, FK, and legacy-upgrade tests."""

from pathlib import Path

import pytest
from aiosqlite import IntegrityError
from xhs_adapters.sqlite.collection_enrichments import (
    SqliteCollectionEnrichmentRepository,
)
from xhs_adapters.sqlite.collection_storage import (
    ensure_collection_foreign_keys,
    initialize_collection_storage,
)
from xhs_adapters.sqlite.collections import SqliteCollectionRepository
from xhs_adapters.sqlite.connection import connect
from xhs_core.domain.collection_enrichment import CollectionEnrichmentStatus

from .collection_enrichment_fixtures import create_snapshot


@pytest.mark.asyncio
async def test_fk_order_restart_and_tc2_data_are_preserved(tmp_path: Path) -> None:
    """Verify FK safety, source ordering, restart persistence, and TC2 data.

    Args:
        tmp_path: Pytest temporary directory.
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
    assert (
        await SqliteCollectionEnrichmentRepository(database).get_enrichment(
            snapshot_id, "feed-a"
        )
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
async def test_legacy_tc2_database_upgrades_in_place(tmp_path: Path) -> None:
    """Verify a TC2-only database upgrades in place without losing data.

    Args:
        tmp_path: Pytest temporary directory.
    """
    database = tmp_path / "legacy.db"
    async with connect(database) as connection:
        await connection.execute("PRAGMA foreign_keys=ON")
        await connection.execute("""CREATE TABLE collection_board (
            source_type TEXT NOT NULL, board_id TEXT NOT NULL, created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL, PRIMARY KEY (source_type, board_id))""")
        await connection.execute("""CREATE TABLE collection_snapshot (
            snapshot_id TEXT PRIMARY KEY, source_type TEXT NOT NULL,
            board_id TEXT NOT NULL, board_revision INTEGER NOT NULL,
            request_id TEXT NOT NULL UNIQUE, captured_at TEXT NOT NULL,
            item_count INTEGER NOT NULL, fingerprint TEXT NOT NULL,
            status TEXT NOT NULL,
            UNIQUE (source_type, board_id, board_revision),
            FOREIGN KEY (source_type, board_id)
            REFERENCES collection_board(source_type, board_id))""")
        await connection.execute("""CREATE TABLE collection_feed (
            feed_id TEXT PRIMARY KEY, latest_xsec_token TEXT NOT NULL,
            token_updated_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL)""")
        await connection.execute("""CREATE TABLE collection_snapshot_item (
            snapshot_id TEXT NOT NULL, feed_id TEXT NOT NULL,
            source_order INTEGER NOT NULL,
            PRIMARY KEY (snapshot_id, feed_id), UNIQUE (snapshot_id, source_order),
            FOREIGN KEY (snapshot_id) REFERENCES collection_snapshot(snapshot_id),
            FOREIGN KEY (feed_id) REFERENCES collection_feed(feed_id))""")
        await connection.execute(
            "INSERT INTO collection_board VALUES (?, ?, ?, ?)",
            (
                "board",
                "legacy-board",
                "2026-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
            ),
        )
        await connection.execute(
            "INSERT INTO collection_snapshot VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "legacy-snapshot",
                "board",
                "legacy-board",
                1,
                "legacy-request",
                "2026-01-01T00:00:00+00:00",
                2,
                "legacy-fingerprint",
                "captured",
            ),
        )
        for feed_id, order in [("feed-b", 0), ("feed-a", 1)]:
            await connection.execute(
                "INSERT INTO collection_feed VALUES (?, ?, ?, ?)",
                (
                    feed_id,
                    "legacy-token",
                    "2026-01-01T00:00:00+00:00",
                    "2026-01-01T00:00:00+00:00",
                ),
            )
            await connection.execute(
                "INSERT INTO collection_snapshot_item VALUES ('legacy-snapshot', ?, ?)",
                (feed_id, order),
            )
        await connection.commit()
        names = await connection.execute_fetchall(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        assert "collection_feed_enrichment" not in {str(row[0]) for row in names}
    await initialize_collection_storage(database)
    collection = SqliteCollectionRepository(database)
    assert (
        await collection.get_snapshot("legacy-snapshot")
    ).fingerprint == "legacy-fingerprint"
    assert [
        item.feed_id for item in await collection.list_snapshot_items("legacy-snapshot")
    ] == ["feed-b", "feed-a"]
    assert (
        await collection.get_feed_access_context("feed-a")
    ).latest_xsec_token.get_secret_value() == "legacy-token"
    enrichment = SqliteCollectionEnrichmentRepository(database)
    assert await enrichment.list_snapshot_enrichments("legacy-snapshot") == []
    assert (
        await enrichment.ensure_enrichment("legacy-snapshot", "feed-a")
    ).status is CollectionEnrichmentStatus.PENDING
    assert len(await enrichment.list_snapshot_enrichments("legacy-snapshot")) == 1
