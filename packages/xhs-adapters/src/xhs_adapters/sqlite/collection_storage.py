"""收藏快照 SQLite schema 初始化与行转换。"""

from datetime import datetime
from pathlib import Path

from aiosqlite import Connection
from xhs_core.domain.collection import (
    CollectionBoard,
    CollectionFeedAccessContext,
    CollectionSnapshot,
    CollectionSnapshotItem,
    CollectionStatus,
)


async def initialize_collection_storage(database: Path) -> None:
    """创建收藏快照所需的表和索引。

    Args:
        database: SQLite 状态库路径。
    """
    from .connection import connect

    async with connect(database) as connection:
        await ensure_collection_foreign_keys(connection)
        await create_collection_schema(connection)
        await connection.commit()


async def ensure_collection_foreign_keys(connection: Connection) -> None:
    """在当前连接上启用并验证 SQLite 外键。

    Args:
        connection: 当前 collection 操作使用的数据库连接。
    """
    await connection.execute("PRAGMA foreign_keys = ON")
    cursor = await connection.execute("PRAGMA foreign_keys")
    row = await cursor.fetchone()
    if row != (1,):
        raise RuntimeError("collection SQLite foreign keys are not enabled")


async def create_collection_schema(connection: Connection) -> None:
    """在当前连接内幂等创建 collection schema。

    Args:
        connection: 将执行建表语句的数据库连接。
    """
    await connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS collection_board (
            source_type TEXT NOT NULL,
            board_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (source_type, board_id)
        );
        CREATE TABLE IF NOT EXISTS collection_snapshot (
            snapshot_id TEXT PRIMARY KEY,
            source_type TEXT NOT NULL,
            board_id TEXT NOT NULL,
            board_revision INTEGER NOT NULL,
            request_id TEXT NOT NULL UNIQUE,
            captured_at TEXT NOT NULL,
            item_count INTEGER NOT NULL,
            fingerprint TEXT NOT NULL,
            status TEXT NOT NULL,
            UNIQUE (source_type, board_id, board_revision),
            FOREIGN KEY (source_type, board_id)
                REFERENCES collection_board (source_type, board_id)
        );
        CREATE TABLE IF NOT EXISTS collection_feed (
            feed_id TEXT PRIMARY KEY,
            latest_xsec_token TEXT NOT NULL,
            token_updated_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS collection_snapshot_item (
            snapshot_id TEXT NOT NULL,
            feed_id TEXT NOT NULL,
            source_order INTEGER NOT NULL,
            PRIMARY KEY (snapshot_id, feed_id),
            UNIQUE (snapshot_id, source_order),
            FOREIGN KEY (snapshot_id) REFERENCES collection_snapshot (snapshot_id),
            FOREIGN KEY (feed_id) REFERENCES collection_feed (feed_id)
        );
        CREATE INDEX IF NOT EXISTS collection_board_updated
            ON collection_board (updated_at DESC);
        CREATE INDEX IF NOT EXISTS collection_snapshot_revision
            ON collection_snapshot (source_type, board_id, board_revision DESC);
        CREATE INDEX IF NOT EXISTS collection_snapshot_status_revision
            ON collection_snapshot (source_type, board_id, status, board_revision DESC);
        CREATE INDEX IF NOT EXISTS collection_snapshot_item_order
            ON collection_snapshot_item (snapshot_id, source_order);
        CREATE INDEX IF NOT EXISTS collection_snapshot_item_feed
            ON collection_snapshot_item (feed_id, snapshot_id);
        """
    )


def board_from_row(row: tuple[object, ...]) -> CollectionBoard:
    """把 board 行转换为领域模型。

    Args:
        row: SQLite 查询行。

    Returns:
        收藏夹领域模型。
    """
    return CollectionBoard(
        source_type=str(row[0]),
        board_id=str(row[1]),
        created_at=datetime.fromisoformat(str(row[2])),
        updated_at=datetime.fromisoformat(str(row[3])),
    )


def snapshot_from_row(row: tuple[object, ...]) -> CollectionSnapshot:
    """把 snapshot 行转换为不含 token 的领域模型。

    Args:
        row: SQLite 查询行。

    Returns:
        不含 token 的快照模型。
    """
    return CollectionSnapshot(
        snapshot_id=str(row[0]),
        source_type=str(row[1]),
        board_id=str(row[2]),
        board_revision=int(row[3]),
        request_id=str(row[4]),
        captured_at=datetime.fromisoformat(str(row[5])),
        item_count=int(row[6]),
        fingerprint=str(row[7]),
        status=CollectionStatus(str(row[8])),
    )


def item_from_row(row: tuple[object, ...]) -> CollectionSnapshotItem:
    """把 membership 行转换为不含 token 的领域模型。

    Args:
        row: SQLite 查询行。

    Returns:
        快照 membership 模型。
    """
    return CollectionSnapshotItem(
        snapshot_id=str(row[0]), feed_id=str(row[1]), source_order=int(row[2])
    )


def access_context_from_row(row: tuple[object, ...]) -> CollectionFeedAccessContext:
    """把 feed 行转换为显式敏感 access context。

    Args:
        row: SQLite 查询行。

    Returns:
        仅供内部使用的 feed access context。
    """
    return CollectionFeedAccessContext(
        feed_id=str(row[0]),
        latest_xsec_token=str(row[1]),
        token_updated_at=datetime.fromisoformat(str(row[2])),
        last_seen_at=datetime.fromisoformat(str(row[3])),
    )
