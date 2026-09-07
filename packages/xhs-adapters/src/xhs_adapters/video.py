"""TC4 本地视频 artifact、PyAV、STT 与 OCR 适配器。"""

from asyncio import to_thread
from hashlib import sha256
from pathlib import Path

import av
from xhs_core.domain import (
    FeedMediaResult,
    VideoOcrFrame,
    VideoOcrResult,
    VideoTranscript,
    VideoTranscriptSegment,
)

from .filesystem.streaming import retry_stream_to_atomic_file


class SafeVideoArtifactStore:
    """把 transient 视频定位器写入安全、非用户内容命名的目录。"""

    def __init__(self, root: Path, gateway) -> None:
        self._root = root
        self._gateway = gateway

    async def save(
        self, snapshot_id: str, feed_id: str, media: FeedMediaResult
    ) -> tuple[str, str, int]:
        """流式写入安全命名的本地视频并返回摘要。

        Args:
            snapshot_id: 收藏快照标识。
            feed_id: 帖子标识。
            media: 含短期媒体定位器的结果。

        Returns:
            相对路径、SHA-256 和字节数。
        """
        video = next((item for item in media.media if item.kind == "video"), None)
        if video is None:
            raise LookupError("media_unavailable")
        safe_id = sha256(f"{snapshot_id}\0{feed_id}".encode()).hexdigest()
        target_dir = self._root / safe_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / "source.mp4"
        part = target_dir / ".source.mp4.part"
        marker = target_dir / ".source.mp4.part.url"
        result = await retry_stream_to_atomic_file(
            self._gateway,
            str(video.url),
            part,
            marker,
            target,
            cleanup_on_exhaustion=True,
            max_attempts=3,
        )
        return str(result.target.relative_to(self._root)), result.sha256, result.size

    def resolve_path(self, relative_path: str) -> str:
        """把安全相对路径解析为仅供运行时使用的物理路径。

        Args:
            relative_path: 相对于 artifact 根目录的安全路径。

        Returns:
            解析后的物理路径。
        """
        candidate = (self._root / relative_path).resolve()
        if self._root.resolve() not in candidate.parents:
            raise ValueError("artifact path escapes configured root")
        return str(candidate)

    async def discard(self, relative_path: str) -> None:
        """删除处理完成后不再保留的本地源文件。

        Args:
            relative_path: 相对于 artifact 根目录的安全路径。
        """
        await to_thread((self._root / relative_path).unlink, True)


class PyAvVideoInspector:
    """使用 PyAV 探测时长并抽取固定间隔、有界关键帧。"""

    def __init__(self, interval_seconds: int = 4, max_frames: int = 60) -> None:
        self._interval = interval_seconds
        self._max_frames = max_frames

    def inspect(self, path: str) -> tuple[float, list[tuple[float, object]]]:
        """读取视频时长并抽取固定间隔的有界关键帧。

        Args:
            path: 本地 MP4 路径。

        Returns:
            视频时长和按时间排序的关键帧。
        """
        container = av.open(path)
        stream = container.streams.video[0]
        duration = float(stream.duration * stream.time_base) if stream.duration else 0.0
        wanted = set(range(0, max(1, int(duration) + self._interval), self._interval))
        frames: list[tuple[float, object]] = []
        for frame in container.decode(stream):
            timestamp = float(frame.time or 0)
            second = (
                min(wanted, key=lambda value: abs(value - timestamp)) if wanted else 0
            )
            if abs(second - timestamp) <= self._interval / 2 and all(
                existing != second for existing, _ in frames
            ):
                frames.append((timestamp, frame.to_image()))
                if len(frames) >= self._max_frames:
                    break
        container.close()
        return duration, frames


class FasterWhisperTranscriber:
    """惰性复用的本地 faster-whisper CPU int8 转写器。"""

    def __init__(self, model_size: str = "small") -> None:
        self._model_size = model_size
        self._model = None

    def _get_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                self._model_size, device="cpu", compute_type="int8"
            )
        return self._model

    def transcribe(self, path: str) -> VideoTranscript:
        """使用单个惰性初始化的本地模型转写 MP4。

        Args:
            path: 本地 MP4 路径。

        Returns:
            脱敏后的转写结果。
        """
        segments, info = self._get_model().transcribe(path)
        values = [
            VideoTranscriptSegment(
                start=float(s.start), end=float(s.end), text=str(s.text).strip()
            )
            for s in segments
        ]
        return VideoTranscript(
            language=str(info.language or ""),
            duration_seconds=float(info.duration or 0),
            text=" ".join(item.text for item in values),
            segments=values,
        )


class PaddleOcrRecognizer:
    """惰性 CPU 多语言 PaddleOCR 适配器。"""

    def __init__(self) -> None:
        self._engine = None

    def _get_engine(self):
        if self._engine is None:
            from paddleocr import PaddleOCR

            self._engine = PaddleOCR(lang="japan")
        return self._engine

    def recognize(self, frames) -> VideoOcrResult:
        """识别关键帧文字并返回去重后的安全结果。

        Args:
            frames: 带时间戳的关键帧序列。

        Returns:
            仅包含文字和时间戳的 OCR 结果。
        """
        results: list[VideoOcrFrame] = []
        for timestamp, image in frames:
            output = self._get_engine().ocr(image, cls=False)
            text = _ocr_text(output)
            if text and (not results or results[-1].text != text):
                results.append(VideoOcrFrame(timestamp_seconds=timestamp, text=text))
        return VideoOcrResult(
            combined_text="\n".join(item.text for item in results), frames=results
        )


def _ocr_text(output) -> str:
    """仅从 PaddleOCR 2.x 的 ``(text, score)`` 行记录提取文字。"""
    values: list[str] = []

    def visit(value) -> None:
        if (
            isinstance(value, (list, tuple))
            and len(value) == 2
            and isinstance(value[0], str)
            and isinstance(value[1], (int, float))
        ):
            values.append(value[0].strip())
        elif isinstance(value, (list, tuple)):
            for item in value:
                visit(item)

    visit(output)
    return " ".join(value for value in values if value)
