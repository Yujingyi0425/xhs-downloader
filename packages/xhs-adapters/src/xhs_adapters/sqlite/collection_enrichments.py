"""收藏条目详情 enrichment 的 SQLite 仓储。"""

from datetime import UTC, datetime
from pathlib import Path

from xhs_core.domain.collection_enrichment import (
    TERMINAL_ENRICHMENT_STATUSES,
    CollectionEnrichmentStatus,
    CollectionFeedDetail,
    CollectionFeedEnrichment,
)
from xhs_core.domain.collection_enrichment_ports import EnrichmentStateConflictError

from .collection_enrichment_storage import enrichment_from_row
from .collection_storage import (
    ensure_collection_foreign_keys,
    initialize_collection_storage,
)
from .connection import connect


class SqliteCollectionEnrichmentRepository:
    """持久化详情 enrichment，不保存任何 token 或访问上下文。"""

    def __init__(self, database: Path) -> None:
        self._database = database

    async def ensure_enrichment(
        self, snapshot_id: str, feed_id: str, enrichment_version: int = 1
    ) -> CollectionFeedEnrichment:
        """创建或读取复合身份 enrichment。

        Args:
            snapshot_id: 收藏快照标识。
            feed_id: 快照条目标识。
            enrichment_version: 详情语义版本。

        Returns:
            已存在或新建的 enrichment 记录。
        """
        await initialize_collection_storage(self._database)
        now = datetime.now(UTC).isoformat()
        async with connect(self._database) as database:
            await ensure_collection_foreign_keys(database)
            await database.execute(
                """INSERT INTO collection_feed_enrichment
                (snapshot_id, feed_id, enrichment_version, status, detail_json,
                 attempt_count, last_error_code, created_at, updated_at, enriched_at)
                VALUES (?, ?, ?, 'pending', NULL, 0, NULL, ?, ?, NULL)
                ON CONFLICT(snapshot_id, feed_id, enrichment_version) DO NOTHING""",
                (snapshot_id, feed_id, enrichment_version, now, now),
            )
            await database.commit()
            return await self._get(database, snapshot_id, feed_id, enrichment_version)

    async def get_enrichment(
        self, snapshot_id: str, feed_id: str, enrichment_version: int = 1
    ) -> CollectionFeedEnrichment | None:
        """读取精确复合身份 enrichment。

        Args:
            snapshot_id: 收藏快照标识。
            feed_id: 快照条目标识。
            enrichment_version: 详情语义版本。

        Returns:
            匹配记录；不存在时为 ``None``。
        """
        await initialize_collection_storage(self._database)
        async with connect(self._database) as database:
            await ensure_collection_foreign_keys(database)
            return await self._get(database, snapshot_id, feed_id, enrichment_version)

    async def list_snapshot_enrichments(
        self, snapshot_id: str
    ) -> list[CollectionFeedEnrichment]:
        """按 snapshot membership 的 source_order 稳定读取记录。

        Args:
            snapshot_id: 收藏快照标识。

        Returns:
            按收藏顺序排列的 enrichment 记录。
        """
        await initialize_collection_storage(self._database)
        async with connect(self._database) as database:
            await ensure_collection_foreign_keys(database)
            cursor = await database.execute(
                """SELECT e.* FROM collection_feed_enrichment e
                JOIN collection_snapshot_item i
                  ON i.snapshot_id=e.snapshot_id AND i.feed_id=e.feed_id
                WHERE e.snapshot_id=? ORDER BY i.source_order, e.enrichment_version""",
                (snapshot_id,),
            )
            return [enrichment_from_row(row) for row in await cursor.fetchall()]

    async def transition_enrichment(
        self,
        snapshot_id: str,
        feed_id: str,
        expected: set[CollectionEnrichmentStatus],
        new_status: CollectionEnrichmentStatus,
        enrichment_version: int = 1,
        error_code: str | None = None,
    ) -> CollectionFeedEnrichment:
        """以状态 CAS 推进 enrichment，running 只增加一次 attempt。

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
        await initialize_collection_storage(self._database)
        async with connect(self._database) as database:
            await ensure_collection_foreign_keys(database)
            await database.execute("BEGIN IMMEDIATE")
            current = await self._get(
                database, snapshot_id, feed_id, enrichment_version
            )
            if (
                current is None
                or current.status not in expected
                or current.status in TERMINAL_ENRICHMENT_STATUSES
                or new_status is CollectionEnrichmentStatus.SUCCEEDED
                or (error_code is not None and len(error_code) > 200)
            ):
                await database.rollback()
                raise EnrichmentStateConflictError("enrichment 状态已变化")
            now = datetime.now(UTC)
            attempts = current.attempt_count + (
                1
                if new_status is CollectionEnrichmentStatus.RUNNING
                and current.status is not new_status
                else 0
            )
            await database.execute(
                """UPDATE collection_feed_enrichment
                SET status=?, attempt_count=?, last_error_code=?, updated_at=?
                WHERE snapshot_id=? AND feed_id=? AND enrichment_version=?
                  AND status=?""",
                (
                    new_status.value,
                    attempts,
                    error_code,
                    now.isoformat(),
                    snapshot_id,
                    feed_id,
                    enrichment_version,
                    current.status.value,
                ),
            )
            updated = await self._get(
                database, snapshot_id, feed_id, enrichment_version
            )
            await database.commit()
            return updated

    async def save_detail(
        self,
        snapshot_id: str,
        feed_id: str,
        detail: CollectionFeedDetail,
        enrichment_version: int = 1,
    ) -> CollectionFeedEnrichment:
        """校验身份后把脱敏详情与成功状态原子写入。

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
        if detail.feed_id != feed_id:
            raise ValueError("详情 feed_id 与 enrichment 条目不一致")
        await initialize_collection_storage(self._database)
        async with connect(self._database) as database:
            await ensure_collection_foreign_keys(database)
            await database.execute("BEGIN IMMEDIATE")
            current = await self._get(
                database, snapshot_id, feed_id, enrichment_version
            )
            if (
                current is None
                or current.status is not CollectionEnrichmentStatus.RUNNING
            ):
                await database.rollback()
                raise EnrichmentStateConflictError("详情只能保存到 running enrichment")
            now = datetime.now(UTC)
            await database.execute(
                """UPDATE collection_feed_enrichment
                SET status='succeeded', detail_json=?, last_error_code=NULL,
                    updated_at=?, enriched_at=?
                WHERE snapshot_id=? AND feed_id=? AND enrichment_version=?
                  AND status='running'""",
                (
                    detail.model_dump_json(),
                    now.isoformat(),
                    now.isoformat(),
                    snapshot_id,
                    feed_id,
                    enrichment_version,
                ),
            )
            updated = await self._get(
                database, snapshot_id, feed_id, enrichment_version
            )
            updated.validate_invariants()
            await database.commit()
            return updated

    async def _get(self, database, snapshot_id, feed_id, enrichment_version):
        cursor = await database.execute(
            """SELECT snapshot_id, feed_id, enrichment_version, status, detail_json,
            attempt_count, last_error_code, created_at, updated_at, enriched_at
            FROM collection_feed_enrichment
            WHERE snapshot_id=? AND feed_id=? AND enrichment_version=?""",
            (snapshot_id, feed_id, enrichment_version),
        )
        row = await cursor.fetchone()
        return enrichment_from_row(row) if row else None
