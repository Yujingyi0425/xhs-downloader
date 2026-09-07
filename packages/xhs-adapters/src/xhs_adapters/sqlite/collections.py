"""收藏快照 SQLite 仓储。"""

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from xhs_core.domain.collection import (
    CollectionDiff,
    CollectionImportCommand,
    CollectionSnapshot,
)
from xhs_core.domain.collection_ports import CollectionIdempotencyConflictError

from .collection_reads import CollectionReadMixin
from .collection_storage import (
    ensure_collection_foreign_keys,
    initialize_collection_storage,
)
from .connection import connect


class SqliteCollectionRepository(CollectionReadMixin):
    """以单事务保存收藏夹快照、membership 与最新 token 上下文。"""

    def __init__(self, database: Path) -> None:
        self._database = database
        self._initialized = False

    async def import_snapshot(
        self, command: CollectionImportCommand, fingerprint: str, captured_at: datetime
    ) -> tuple[CollectionSnapshot, CollectionDiff]:
        """原子导入，或按 request_id 返回已存在的相同观察。

        Args:
            command: 已验证的收藏导入命令。
            fingerprint: ordered membership 的内容指纹。
            captured_at: 观察发生时间。

        Returns:
            快照及相邻 revision 的差异。
        """
        await self._initialize()
        async with connect(self._database) as database:
            await ensure_collection_foreign_keys(database)
            await database.execute("BEGIN IMMEDIATE")
            try:
                existing = await self._find_by_request(database, command.request_id)
                if existing:
                    current_items = await self._read_items(
                        database, existing.snapshot_id
                    )
                    current_fingerprint = await self._membership_fingerprint(
                        existing.source_type, existing.board_id, current_items
                    )
                    if (
                        existing.source_type,
                        existing.board_id,
                        current_fingerprint,
                    ) != (command.source_type, command.board_id, fingerprint):
                        raise CollectionIdempotencyConflictError(
                            "request_id conflicts with an existing observation"
                        )
                    await database.commit()
                    return existing, CollectionDiff(added=[], removed=[], retained=[])

                previous = await self._latest(
                    database, command.source_type, command.board_id
                )
                revision = (previous.board_revision if previous else 0) + 1
                now = captured_at.isoformat()
                await database.execute(
                    """
                    INSERT INTO collection_board
                    (source_type, board_id, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(source_type, board_id)
                    DO UPDATE SET updated_at=excluded.updated_at
                    """,
                    (command.source_type, command.board_id, now, now),
                )
                snapshot_id = str(uuid4())
                await database.execute(
                    """INSERT INTO collection_snapshot
                    (snapshot_id, source_type, board_id, board_revision, request_id,
                     captured_at, item_count, fingerprint, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'captured')""",
                    (
                        snapshot_id,
                        command.source_type,
                        command.board_id,
                        revision,
                        command.request_id,
                        now,
                        len(command.items),
                        fingerprint,
                    ),
                )
                for item in command.items:
                    await self._upsert_feed(
                        database, item.feed_id, item.xsec_token.get_secret_value(), now
                    )
                    await self._insert_item(
                        database, snapshot_id, item.feed_id, item.source_order
                    )
                cursor = await database.execute(
                    """
                    SELECT COUNT(*) FROM collection_snapshot_item
                    WHERE snapshot_id = ?
                    """,
                    (snapshot_id,),
                )
                row = await cursor.fetchone()
                if row != (len(command.items),):
                    raise RuntimeError("collection membership count mismatch")
                await database.commit()
                snapshot = await self._get_by_id(database, snapshot_id)
                if snapshot is None:
                    raise RuntimeError("new collection snapshot disappeared")
                previous_items = (
                    await self._read_items(database, previous.snapshot_id)
                    if previous
                    else []
                )
                return snapshot, self._diff(previous_items, command.items)
            except Exception:
                await database.rollback()
                raise

    async def _insert_item(
        self, database, snapshot_id: str, feed_id: str, source_order: int
    ) -> None:
        await database.execute(
            """
            INSERT INTO collection_snapshot_item
            (snapshot_id, feed_id, source_order) VALUES (?, ?, ?)
            """,
            (snapshot_id, feed_id, source_order),
        )

    async def _upsert_feed(self, database, feed_id: str, token: str, now: str) -> None:
        await database.execute(
            """
            INSERT INTO collection_feed
            (feed_id, latest_xsec_token, token_updated_at, last_seen_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(feed_id) DO UPDATE SET
                latest_xsec_token=excluded.latest_xsec_token,
                token_updated_at=excluded.token_updated_at,
                last_seen_at=excluded.last_seen_at
            """,
            (feed_id, token, now, now),
        )

    async def _initialize(self) -> None:
        if not self._initialized:
            self._database.parent.mkdir(parents=True, exist_ok=True)
            await initialize_collection_storage(self._database)
            self._initialized = True

    async def _membership_fingerprint(self, source_type, board_id, items):
        from pydantic import SecretStr
        from xhs_core.domain.collection import (
            CollectionImportCommand,
            CollectionImportItem,
        )

        command = CollectionImportCommand(
            request_id="existing",
            source_type=source_type,
            board_id=board_id,
            items=[
                CollectionImportItem(
                    feed_id=item.feed_id,
                    xsec_token=SecretStr("synthetic"),
                    source_order=item.source_order,
                )
                for item in items
            ],
        )
        from xhs_core.domain.collection import collection_fingerprint

        return collection_fingerprint(command)

    @staticmethod
    def _diff(previous_items, current_items):
        previous = {item.feed_id for item in previous_items}
        current = {item.feed_id for item in current_items}
        return CollectionDiff(
            added=sorted(current - previous),
            removed=sorted(previous - current),
            retained=sorted(current & previous),
        )
