"""TC4 视频处理所需的基础设施端口。"""

from collections.abc import Sequence
from typing import Protocol

from .feeds import FeedMediaResult
from .video_content import (
    CollectionVideoContent,
    VideoOcrResult,
    VideoProcessingStatus,
    VideoTranscript,
)


class VideoStateConflictError(RuntimeError):
    """视频处理状态已被另一个 worker 改变。"""


class VideoContentRepository(Protocol):
    """视频内容独立生命周期的持久化端口。"""

    async def get(
        self, snapshot_id: str, feed_id: str, version: int = 1
    ) -> CollectionVideoContent | None:
        """读取指定视频内容。

        Args:
            snapshot_id: 快照标识。
            feed_id: 帖子标识。
            version: 处理版本。

        Returns:
            内容或 None。
        """
        ...

    async def save(self, content: CollectionVideoContent) -> CollectionVideoContent:
        """保存当前版本的视频内容。 Args: 脱敏内容。 Returns: 保存后的内容。"""
        ...

    async def save_if_status(
        self,
        content: CollectionVideoContent,
        expected: VideoProcessingStatus | None,
    ) -> bool:
        """仅在当前状态仍为 expected 时保存，并返回是否成功。

        Args:
            content: 待保存的视频内容。
            expected: 预期旧状态。

        Returns:
            CAS 是否成功。
        """
        ...

    async def list_snapshot(self, snapshot_id: str) -> list[CollectionVideoContent]:
        """读取快照内的全部视频内容。 Args: 快照标识。 Returns: 内容列表。"""
        ...


class VideoMediaAcquirer(Protocol):
    """获取短期视频媒体定位器的端口。"""

    async def acquire(
        self, feed_id: str, xsec_token: str, request_id: str
    ) -> FeedMediaResult:
        """使用短期访问上下文获取媒体定位器。 Args: 身份、令牌和请求标识。

        Returns: 媒体结果。
        """
        ...


class VideoArtifactStore(Protocol):
    """将媒体定位器安全落盘的端口。"""

    async def save(
        self, snapshot_id: str, feed_id: str, media: FeedMediaResult
    ) -> tuple[str, str, int]:
        """将媒体定位器安全写入本地 artifact。 Args: 快照、身份和媒体。

        Returns: 相对路径、摘要和大小。
        """
        ...


class VideoInspector(Protocol):
    """本地视频探测和有界关键帧端口。"""

    def inspect(self, path: str) -> tuple[float, Sequence[tuple[float, object]]]:
        """读取时长并返回有界关键帧。 Args: 本地路径。 Returns: 时长和帧。"""
        ...


class VideoTranscriber(Protocol):
    """本地视频转写端口。"""

    def transcribe(self, path: str) -> VideoTranscript:
        """转写本地视频。 Args: 本地路径。 Returns: 转写结果。"""
        ...


class VideoOcr(Protocol):
    """关键帧 OCR 端口。"""

    def recognize(self, frames: Sequence[tuple[float, object]]) -> VideoOcrResult:
        """识别关键帧文字。 Args: 关键帧序列。 Returns: OCR 结果。"""
        ...
