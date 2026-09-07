"""视频内容独立生命周期的 SQLite 仓储。"""

from pathlib import Path

from xhs_core.domain import CollectionVideoContent, VideoProcessingStatus

from .connection import connect


class SqliteCollectionVideoContentRepository:
    """保存不含 URL、token 的视频内容结果。"""

    def __init__(self, database: Path) -> None:
        self._database = database
        self._initialized = False

    async def get(self, snapshot_id: str, feed_id: str, version: int = 1):
        """读取一个 snapshot/feed/version 的视频内容。

        Args:
            snapshot_id: 收藏快照标识。
            feed_id: 帖子标识。
            version: 处理语义版本。

        Returns:
            已保存内容，不存在时返回 ``None``。
        """
        await self._initialize()
        async with connect(self._database) as database:
            cursor = await database.execute(
                """SELECT content_json FROM collection_video_content
                WHERE snapshot_id=? AND feed_id=? AND processing_version=?""",
                (snapshot_id, feed_id, version),
            )
            row = await cursor.fetchone()
        return CollectionVideoContent.model_validate_json(row[0]) if row else None

    async def save(self, content: CollectionVideoContent) -> CollectionVideoContent:
        """原子保存视频内容，且不写入 URL 或 token。

        Args:
            content: 已脱敏的视频内容。

        Returns:
            保存后的内容。
        """
        await self._initialize()
        payload = content.model_dump_json()
        async with connect(self._database) as database:
            await database.execute(
                """INSERT INTO collection_video_content
                (snapshot_id, feed_id, processing_version, status, content_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(snapshot_id, feed_id, processing_version) DO UPDATE SET
                status=excluded.status, content_json=excluded.content_json""",
                (
                    content.snapshot_id,
                    content.feed_id,
                    content.processing_version,
                    content.status.value,
                    payload,
                ),
            )
            await database.commit()
        return content

    async def save_if_status(
        self,
        content: CollectionVideoContent,
        expected: VideoProcessingStatus | None,
    ) -> bool:
        """按状态 CAS 保存，阻止 stale worker 覆盖新状态。

        Args:
            content: 待保存内容。
            expected: 预期旧状态。

        Returns:
            CAS 是否成功。
        """
        await self._initialize()
        payload = content.model_dump_json()
        async with connect(self._database) as database:
            if expected is None:
                cursor = await database.execute(
                    """INSERT OR IGNORE INTO collection_video_content
                    (snapshot_id, feed_id, processing_version, status, content_json)
                    VALUES (?, ?, ?, ?, ?)""",
                    (
                        content.snapshot_id,
                        content.feed_id,
                        content.processing_version,
                        content.status.value,
                        payload,
                    ),
                )
            else:
                cursor = await database.execute(
                    """UPDATE collection_video_content SET status=?, content_json=?
                    WHERE snapshot_id=? AND feed_id=?
                    AND processing_version=? AND status=?""",
                    (
                        content.status.value,
                        payload,
                        content.snapshot_id,
                        content.feed_id,
                        content.processing_version,
                        expected.value,
                    ),
                )
            await database.commit()
            return cursor.rowcount == 1

    async def save_if_attempt(
        self, content: CollectionVideoContent, expected_attempt: int
    ) -> bool:
        """按 JSON 中的 attempt_count 做 CAS，拒绝旧 worker 写入。

        Args:
            content: 待保存的视频内容。
            expected_attempt: 预期的当前尝试次数。

        Returns:
            CAS 是否成功。
        """
        await self._initialize()
        payload = content.model_dump_json()
        async with connect(self._database) as database:
            cursor = await database.execute(
                """UPDATE collection_video_content SET status=?, content_json=?
                WHERE snapshot_id=? AND feed_id=? AND processing_version=?
                AND json_extract(content_json, '$.attempt_count')=?""",
                (
                    content.status.value,
                    payload,
                    content.snapshot_id,
                    content.feed_id,
                    content.processing_version,
                    expected_attempt,
                ),
            )
            await database.commit()
            return cursor.rowcount == 1

    async def recover_running(self, snapshot_id: str) -> int:
        """回收指定快照中进程重启遗留的 RUNNING 记录。

        Args:
            snapshot_id: 待恢复的收藏快照标识。

        Returns:
            被回收的记录数量。
        """
        await self._initialize()
        async with connect(self._database) as database:
            cursor = await database.execute(
                """UPDATE collection_video_content
                SET status=?, content_json=json_set(content_json, '$.status', ?)
                WHERE snapshot_id=? AND status=?""",
                (
                    VideoProcessingStatus.FAILED_RETRYABLE.value,
                    VideoProcessingStatus.FAILED_RETRYABLE.value,
                    snapshot_id,
                    VideoProcessingStatus.RUNNING.value,
                ),
            )
            await database.commit()
            return cursor.rowcount

    async def list_snapshot(self, snapshot_id: str) -> list[CollectionVideoContent]:
        """按 feed_id 稳定读取一个快照的视频内容。

        Args:
            snapshot_id: 收藏快照标识。

        Returns:
            按 feed_id 排序的内容列表。
        """
        await self._initialize()
        async with connect(self._database) as database:
            cursor = await database.execute(
                """SELECT content_json FROM collection_video_content
                WHERE snapshot_id=? ORDER BY feed_id""",
                (snapshot_id,),
            )
            rows = await cursor.fetchall()
        return [CollectionVideoContent.model_validate_json(row[0]) for row in rows]

    async def _initialize(self) -> None:
        if self._initialized:
            return
        self._database.parent.mkdir(parents=True, exist_ok=True)
        async with connect(self._database) as database:
            await database.execute(
                """CREATE TABLE IF NOT EXISTS collection_video_content (
                    snapshot_id TEXT NOT NULL,
                    feed_id TEXT NOT NULL,
                    processing_version INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    content_json TEXT NOT NULL,
                    PRIMARY KEY (snapshot_id, feed_id, processing_version)
                )"""
            )
            await database.commit()
        self._initialized = True
