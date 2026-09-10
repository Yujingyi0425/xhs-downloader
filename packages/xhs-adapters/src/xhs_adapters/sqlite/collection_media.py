"""收藏夹媒体 artifact 结果的 SQLite 仓储。"""

import json
from pathlib import Path

from loguru import logger
from pydantic import ValidationError
from xhs_core.domain import CollectionMediaBatchRecord

from .connection import connect


class SqliteCollectionMediaArtifactRepository:
    """只保存脱敏 artifact 元数据、媒体状态和稳定 request identity。"""

    def __init__(self, database: Path) -> None:
        self._database = database
        self._initialized = False

    async def get(self, request_id: str) -> CollectionMediaBatchRecord | None:
        """按 request identity 读取收藏媒体批次。

        Args:
            request_id: 稳定的客户端请求标识。

        Returns:
            已保存的批次；不存在或无效时返回 ``None``。
        """
        await self._initialize()
        async with connect(self._database) as database:
            cursor = await database.execute(
                "SELECT payload FROM collection_media_artifact WHERE request_id=?",
                (request_id,),
            )
            row = await cursor.fetchone()
        if not row:
            return None
        return self._validate(row[0])

    async def save(self, record: CollectionMediaBatchRecord) -> None:
        """原子保存一个收藏媒体批次，不写入媒体 locator。

        Args:
            record: 已通过身份与 artifact 校验的批次记录。
        """
        record.validate_invariants()
        await self._initialize()
        payload = record.model_dump_json()
        async with connect(self._database) as database:
            await database.execute(
                """
                INSERT INTO collection_media_artifact
                    (request_id, snapshot_id, work_id, payload)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(request_id) DO UPDATE SET
                    snapshot_id=excluded.snapshot_id,
                    work_id=excluded.work_id,
                    payload=excluded.payload
                """,
                (record.request_id, record.snapshot_id, record.work_id, payload),
            )
            await database.commit()

    @staticmethod
    def _validate(payload: str) -> CollectionMediaBatchRecord | None:
        try:
            record = CollectionMediaBatchRecord.model_validate_json(payload)
            record.validate_invariants()
            return record
        except (ValidationError, ValueError, json.JSONDecodeError) as error:
            logger.warning("忽略无效的收藏媒体 artifact 记录：{}", error)
            return None

    async def _initialize(self) -> None:
        if self._initialized:
            return
        self._database.parent.mkdir(parents=True, exist_ok=True)
        async with connect(self._database) as database:
            await database.execute(
                """
                CREATE TABLE IF NOT EXISTS collection_media_artifact (
                    request_id TEXT PRIMARY KEY,
                    snapshot_id TEXT NOT NULL,
                    work_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            await database.commit()
        self._initialized = True
