"""原始笔记抽取的持久化和 OCR 端口。"""

from typing import Protocol

from .note_extraction import NoteExtractionRecord


class NoteExtractionRepository(Protocol):
    """按 snapshot/feed/version 保存原始抽取结果。"""

    async def get(
        self, snapshot_id: str, feed_id: str, version: int = 1
    ) -> NoteExtractionRecord | None:
        """读取精确抽取记录。

        Args:
            snapshot_id: 收藏快照标识。
            feed_id: 笔记标识。
            version: canonical record 版本。

        Returns:
            已持久化记录，不存在时返回 ``None``。
        """
        ...

    async def save(self, record: NoteExtractionRecord) -> NoteExtractionRecord:
        """幂等保存抽取记录。

        Args:
            record: 要保存的 canonical record。

        Returns:
            保存后的记录。
        """
        ...

    async def list_snapshot(self, snapshot_id: str) -> list[NoteExtractionRecord]:
        """按快照稳定顺序读取抽取记录。

        Args:
            snapshot_id: 收藏快照标识。

        Returns:
            按收藏顺序排列的记录。
        """
        ...


class ImageOcr(Protocol):
    """本地图片 OCR 端口。"""

    def recognize(self, path: str) -> str:
        """读取本地图片并返回纯文本。

        Args:
            path: 本地图片路径。

        Returns:
            OCR 文本；没有可识别文字时为空字符串。
        """
        ...


class AudioExtractor(Protocol):
    """本地视频音频抽取端口。"""

    def extract(self, path: str) -> str:
        """从视频生成临时本地音频路径。

        Args:
            path: 本地视频路径。

        Returns:
            临时 WAV 文件路径。
        """
        ...

    def cleanup(self, path: str) -> None:
        """清理临时音频文件。

        Args:
            path: 要清理的临时文件路径。
        """
        ...
