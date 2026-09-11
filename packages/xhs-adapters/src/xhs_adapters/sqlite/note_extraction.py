"""原始笔记抽取记录的 SQLite 仓储。"""

from pathlib import Path

from xhs_core.domain import NoteExtractionRecord

from .connection import connect


class SqliteNoteExtractionRepository:
    """只保存已脱敏的原始抽取记录，不保存访问凭据。"""

    def __init__(self, database: Path) -> None:
        self._database = database
        self._initialized = False

    async def get(
        self, snapshot_id: str, feed_id: str, version: int = 1
    ) -> NoteExtractionRecord | None:
        """读取一个 snapshot/feed/version 的抽取记录。

        Args:
            snapshot_id: 收藏快照标识。
            feed_id: 帖子标识。
            version: 抽取语义版本。

        Returns:
            抽取记录或 None。
        """
        await self._initialize()
        async with connect(self._database) as database:
            cursor = await database.execute(
                """SELECT payload FROM note_extraction
                WHERE snapshot_id=? AND feed_id=? AND extraction_version=?""",
                (snapshot_id, feed_id, version),
            )
            row = await cursor.fetchone()
        return NoteExtractionRecord.model_validate_json(row[0]) if row else None

    async def save(self, record: NoteExtractionRecord) -> NoteExtractionRecord:
        """原子幂等保存记录。

        Args:
            record: 已脱敏的抽取记录。

        Returns:
            保存后的抽取记录。
        """
        await self._initialize()
        payload = record.model_dump_json()
        async with connect(self._database) as database:
            await database.execute(
                """INSERT INTO note_extraction
                (snapshot_id, feed_id, extraction_version, status, payload)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(snapshot_id, feed_id, extraction_version) DO UPDATE SET
                status=excluded.status, payload=excluded.payload""",
                (
                    record.snapshot_id,
                    record.feed_id,
                    record.extraction_version,
                    record.extraction_status.value,
                    payload,
                ),
            )
            await database.commit()
        return record

    async def list_snapshot(self, snapshot_id: str) -> list[NoteExtractionRecord]:
        """按快照 source_order 稳定读取记录。

        Args:
            snapshot_id: 收藏快照标识。

        Returns:
            按收藏顺序排列的抽取记录。
        """
        await self._initialize()
        async with connect(self._database) as database:
            cursor = await database.execute(
                """SELECT e.payload FROM note_extraction e
                LEFT JOIN collection_snapshot_item i
                  ON i.snapshot_id=e.snapshot_id AND i.feed_id=e.feed_id
                WHERE e.snapshot_id=? ORDER BY i.source_order, e.feed_id""",
                (snapshot_id,),
            )
            rows = await cursor.fetchall()
        return [NoteExtractionRecord.model_validate_json(row[0]) for row in rows]

    async def _initialize(self) -> None:
        if self._initialized:
            return
        self._database.parent.mkdir(parents=True, exist_ok=True)
        async with connect(self._database) as database:
            await database.execute(
                """CREATE TABLE IF NOT EXISTS note_extraction (
                    snapshot_id TEXT NOT NULL,
                    feed_id TEXT NOT NULL,
                    extraction_version INTEGER NOT NULL CHECK(extraction_version >= 1),
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY(snapshot_id, feed_id, extraction_version)
                )"""
            )
            await database.execute(
                """CREATE INDEX IF NOT EXISTS note_extraction_snapshot
                ON note_extraction(snapshot_id, extraction_version)"""
            )
            await database.commit()
        self._initialized = True
