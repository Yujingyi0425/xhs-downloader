"""收藏夹快照导入应用服务。"""

from datetime import UTC, datetime

from xhs_core.domain.collection import (
    CollectionDiff,
    CollectionImportCommand,
    CollectionSnapshot,
    collection_fingerprint,
)
from xhs_core.domain.collection_ports import CollectionRepository


class CollectionImportService:
    """执行收藏夹输入校验、指纹计算并委托原子仓储导入。"""

    def __init__(self, repository: CollectionRepository) -> None:
        """初始化服务。

        Args:
            repository: 提供单事务导入能力的收藏夹仓储。
        """
        self._repository = repository

    async def import_snapshot(
        self, command: CollectionImportCommand, captured_at: datetime | None = None
    ) -> tuple[CollectionSnapshot, CollectionDiff]:
        """导入一份收藏观察。

        Args:
            command: 已按领域规则验证的导入命令。
            captured_at: 观察时间；未提供时使用 UTC 当前时间。

        Returns:
            新建或幂等命中的快照及其相邻快照差异。
        """
        timestamp = captured_at or datetime.now(UTC)
        return await self._repository.import_snapshot(
            command, collection_fingerprint(command), timestamp
        )
