"""收藏快照 SQLite 读取能力。"""

from xhs_core.domain.collection import (
    CollectionDiff,
    CollectionFeedAccessContext,
    CollectionSnapshot,
    CollectionSnapshotItem,
)

from .collection_storage import (
    access_context_from_row,
    item_from_row,
    snapshot_from_row,
)
from .connection import connect


class CollectionReadMixin:
    """为 collection repository 提供不带 token 的读取接口。"""

    async def get_snapshot_by_request_id(
        self, request_id: str
    ) -> CollectionSnapshot | None:
        """按 request_id 读取快照。

        Args:
            request_id: 客户端请求幂等标识。

        Returns:
            匹配的快照；不存在时为 ``None``。
        """
        await self._initialize()
        async with self._connect() as database:
            return await self._find_by_request(database, request_id)

    async def get_snapshot(self, snapshot_id: str) -> CollectionSnapshot | None:
        """按快照 ID 读取快照。

        Args:
            snapshot_id: 快照唯一标识。

        Returns:
            匹配的快照；不存在时为 ``None``。
        """
        await self._initialize()
        async with self._connect() as database:
            return await self._get_by_id(database, snapshot_id)

    async def get_latest_snapshot(
        self, source_type: str, board_id: str
    ) -> CollectionSnapshot | None:
        """按 board_revision 读取最新快照。

        Args:
            source_type: 收藏来源类型。
            board_id: 收藏夹标识。

        Returns:
            最新快照；不存在时为 ``None``。
        """
        await self._initialize()
        async with self._connect() as database:
            return await self._latest(database, source_type, board_id)

    async def list_snapshots(
        self, source_type: str, board_id: str, limit: int
    ) -> list[CollectionSnapshot]:
        """按 board_revision 倒序读取历史快照。

        Args:
            source_type: 收藏来源类型。
            board_id: 收藏夹标识。
            limit: 最大返回数量。

        Returns:
            按 revision 倒序排列的快照列表。
        """
        await self._initialize()
        async with self._connect() as database:
            cursor = await database.execute(
                """
                SELECT * FROM collection_snapshot
                WHERE source_type=? AND board_id=?
                ORDER BY board_revision DESC LIMIT ?
                """,
                (source_type, board_id, limit),
            )
            return [snapshot_from_row(row) for row in await cursor.fetchall()]

    async def list_snapshot_items(
        self, snapshot_id: str
    ) -> list[CollectionSnapshotItem]:
        """按 source_order 读取不含 token 的 membership。

        Args:
            snapshot_id: 快照唯一标识。

        Returns:
            按收藏顺序排列的 membership。
        """
        await self._initialize()
        async with self._connect() as database:
            return await self._read_items(database, snapshot_id)

    async def get_feed_access_context(
        self, feed_id: str
    ) -> CollectionFeedAccessContext | None:
        """显式读取 feed 的敏感访问上下文。

        Args:
            feed_id: 帖子 feed 标识。

        Returns:
            最新访问上下文；不存在时为 ``None``。
        """
        await self._initialize()
        async with self._connect() as database:
            cursor = await database.execute(
                "SELECT * FROM collection_feed WHERE feed_id=?", (feed_id,)
            )
            row = await cursor.fetchone()
            return access_context_from_row(row) if row else None

    async def get_snapshot_diff(self, snapshot_id: str) -> CollectionDiff:
        """读取快照与前一 revision 的 membership 差异，不读取 token。

        Args:
            snapshot_id: 快照唯一标识。

        Returns:
            当前快照与前一 revision 的 membership 差异。
        """
        snapshot = await self.get_snapshot(snapshot_id)
        if not snapshot:
            return CollectionDiff(added=[], removed=[], retained=[])
        history = await self.list_snapshots(
            snapshot.source_type, snapshot.board_id, snapshot.board_revision
        )
        previous = next(
            (
                candidate
                for candidate in history
                if candidate.board_revision == snapshot.board_revision - 1
            ),
            None,
        )
        previous_items = (
            await self.list_snapshot_items(previous.snapshot_id) if previous else []
        )
        current_items = await self.list_snapshot_items(snapshot_id)
        return _diff(previous_items, current_items)

    async def _find_by_request(self, database, request_id: str):
        cursor = await database.execute(
            "SELECT * FROM collection_snapshot WHERE request_id=?", (request_id,)
        )
        row = await cursor.fetchone()
        return snapshot_from_row(row) if row else None

    async def _get_by_id(self, database, snapshot_id: str):
        cursor = await database.execute(
            "SELECT * FROM collection_snapshot WHERE snapshot_id=?", (snapshot_id,)
        )
        row = await cursor.fetchone()
        return snapshot_from_row(row) if row else None

    async def _latest(self, database, source_type: str, board_id: str):
        cursor = await database.execute(
            """
            SELECT * FROM collection_snapshot
            WHERE source_type=? AND board_id=?
            ORDER BY board_revision DESC LIMIT 1
            """,
            (source_type, board_id),
        )
        row = await cursor.fetchone()
        return snapshot_from_row(row) if row else None

    async def _read_items(self, database, snapshot_id: str):
        cursor = await database.execute(
            """
            SELECT snapshot_id, feed_id, source_order
            FROM collection_snapshot_item
            WHERE snapshot_id=? ORDER BY source_order
            """,
            (snapshot_id,),
        )
        return [item_from_row(row) for row in await cursor.fetchall()]

    def _connect(self):
        return connect(self._database)


def _diff(previous_items, current_items) -> CollectionDiff:
    previous = {item.feed_id for item in previous_items}
    current = {item.feed_id for item in current_items}
    return CollectionDiff(
        added=sorted(current - previous),
        removed=sorted(previous - current),
        retained=sorted(current & previous),
    )
