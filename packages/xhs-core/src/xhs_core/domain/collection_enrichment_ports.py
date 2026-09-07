"""收藏详情 enrichment 持久化端口。"""

from typing import Protocol

from .collection_enrichment import (
    CollectionEnrichmentStatus,
    CollectionFeedDetail,
    CollectionFeedEnrichment,
)


class EnrichmentStateConflictError(ValueError):
    """enrichment 状态已被其他执行者改变。"""


class CollectionEnrichmentRepository(Protocol):
    """只负责收藏条目详情 enrichment 的持久化。"""

    async def ensure_enrichment(
        self, snapshot_id: str, feed_id: str, enrichment_version: int = 1
    ) -> CollectionFeedEnrichment:
        """按复合身份创建或读取 enrichment，且不重置既有状态。

        Args:
            snapshot_id: 收藏快照标识。
            feed_id: 快照条目标识。
            enrichment_version: 详情语义版本。

        Returns:
            已存在或新建的 enrichment 记录。
        """
        ...

    async def get_enrichment(
        self, snapshot_id: str, feed_id: str, enrichment_version: int = 1
    ) -> CollectionFeedEnrichment | None:
        """读取精确 enrichment 身份。

        Args:
            snapshot_id: 收藏快照标识。
            feed_id: 快照条目标识。
            enrichment_version: 详情语义版本。

        Returns:
            匹配记录；不存在时为 ``None``。
        """
        ...

    async def list_snapshot_enrichments(
        self, snapshot_id: str
    ) -> list[CollectionFeedEnrichment]:
        """按 snapshot membership source_order 稳定读取 enrichment。

        Args:
            snapshot_id: 收藏快照标识。

        Returns:
            按收藏顺序排列的 enrichment 记录。
        """
        ...

    async def transition_enrichment(
        self,
        snapshot_id: str,
        feed_id: str,
        expected: set[CollectionEnrichmentStatus],
        new_status: CollectionEnrichmentStatus,
        enrichment_version: int = 1,
        error_code: str | None = None,
    ) -> CollectionFeedEnrichment:
        """以 compare-and-set 原子推进状态并阻止陈旧覆盖。

        Args:
            snapshot_id: 收藏快照标识。
            feed_id: 快照条目标识。
            expected: 允许作为当前状态的集合。
            new_status: 目标状态。
            enrichment_version: 详情语义版本。
            error_code: 可选的脱敏错误分类。

        Returns:
            状态推进后的记录。

        Raises:
            EnrichmentStateConflictError: 当前状态与 expected 不匹配。
        """
        ...

    async def save_detail(
        self,
        snapshot_id: str,
        feed_id: str,
        detail: CollectionFeedDetail,
        enrichment_version: int = 1,
    ) -> CollectionFeedEnrichment:
        """在 running 状态下原子保存已脱敏详情并完成 enrichment。

        Args:
            snapshot_id: 收藏快照标识。
            feed_id: 快照条目标识。
            detail: 已显式脱敏的详情模型。
            enrichment_version: 详情语义版本。

        Returns:
            已成功保存详情的记录。

        Raises:
            EnrichmentStateConflictError: 记录不处于 running 状态。
            ValueError: 详情身份与条目不一致。
        """
        ...
