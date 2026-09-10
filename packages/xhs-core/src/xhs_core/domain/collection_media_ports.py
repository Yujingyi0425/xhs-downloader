"""收藏夹媒体 artifact 持久化端口。"""

from typing import Protocol

from .collection_media import CollectionMediaBatchRecord


class CollectionMediaArtifactRepository(Protocol):
    """按稳定 request identity 保存收藏夹媒体批次。"""

    async def get(self, request_id: str) -> CollectionMediaBatchRecord | None:
        """读取一个已持久化的媒体批次。

        Args:
            request_id: 稳定的客户端请求标识。

        Returns:
            已保存的批次；不存在时返回 ``None``。
        """
        ...

    async def save(self, record: CollectionMediaBatchRecord) -> None:
        """原子覆盖一个媒体批次结果。

        Args:
            record: 已通过身份与 artifact 校验的批次记录。
        """
        ...
