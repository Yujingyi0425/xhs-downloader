"""收藏夹持久化端口。"""

from datetime import datetime
from typing import Protocol

from .collection import (
    CollectionDiff,
    CollectionFeedAccessContext,
    CollectionImportCommand,
    CollectionSnapshot,
    CollectionSnapshotItem,
)


class CollectionIdempotencyConflictError(ValueError):
    """request_id 已被不同收藏夹或 membership 使用。"""


class CollectionRepository(Protocol):
    """收藏快照的原子持久化端口。"""

    async def import_snapshot(
        self, command: CollectionImportCommand, fingerprint: str, captured_at: datetime
    ) -> tuple[CollectionSnapshot, CollectionDiff]:
        """原子导入快照并返回相邻 revision 的差异。

        Args:
            command: 已验证的导入命令。
            fingerprint: ordered membership 指纹。
            captured_at: 观察时间。

        Returns:
            快照及相邻 revision 的差异。
        """
        ...

    async def get_snapshot_by_request_id(
        self, request_id: str
    ) -> CollectionSnapshot | None:
        """按 request_id 读取快照。

        Args:
            request_id: 客户端请求幂等标识。

        Returns:
            匹配快照或 ``None``。
        """
        ...

    async def get_snapshot(self, snapshot_id: str) -> CollectionSnapshot | None:
        """按 ID 读取快照。

        Args:
            snapshot_id: 快照唯一标识。

        Returns:
            匹配快照或 ``None``。
        """
        ...

    async def get_latest_snapshot(
        self, source_type: str, board_id: str
    ) -> CollectionSnapshot | None:
        """按 board_revision 读取最新快照。

        Args:
            source_type: 收藏来源类型。
            board_id: 收藏夹标识。

        Returns:
            最新快照或 ``None``。
        """
        ...

    async def list_snapshots(
        self, source_type: str, board_id: str, limit: int
    ) -> list[CollectionSnapshot]:
        """按 board_revision 倒序读取历史快照。

        Args:
            source_type: 收藏来源类型。
            board_id: 收藏夹标识。
            limit: 最大返回数量。

        Returns:
            历史快照列表。
        """
        ...

    async def list_snapshot_items(
        self, snapshot_id: str
    ) -> list[CollectionSnapshotItem]:
        """按 source_order 读取 membership。

        Args:
            snapshot_id: 快照唯一标识。

        Returns:
            不含 token 的 membership 列表。
        """
        ...

    async def get_feed_access_context(
        self, feed_id: str
    ) -> CollectionFeedAccessContext | None:
        """显式读取 feed 的敏感详情访问上下文。

        Args:
            feed_id: 帖子 feed 标识。

        Returns:
            内部 access context 或 ``None``。
        """
        ...
