"""TC4 本地视频 artifact、PyAV、STT 与 OCR 适配器。"""

from asyncio import to_thread
from hashlib import sha256
from pathlib import Path

import av
from xhs_core.domain import (
    FeedMediaResult,
    VideoOcrFrame,
    VideoOcrResult,
)

from .filesystem.streaming import retry_stream_to_atomic_file
from .video_audio import PyAvAudioExtractor  # noqa: F401
from .video_transcription import FasterWhisperTranscriber  # noqa: F401


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
        try:
            stream = container.streams.video[0]
            duration = (
                float(stream.duration * stream.time_base) if stream.duration else 0.0
            )
            duration = duration or float(container.duration or 0) / av.time_base
            wanted = set(
                range(0, max(1, int(duration) + self._interval), self._interval)
            )
            frames: list[tuple[float, object]] = []
            for frame in container.decode(stream):
                timestamp = float(frame.time or 0)
                second = min(wanted, key=lambda value: abs(value - timestamp))
                if abs(second - timestamp) <= self._interval / 2 and all(
                    existing != second for existing, _ in frames
                ):
                    frames.append((timestamp, frame.to_image()))
                    if len(frames) >= self._max_frames:
                        break
            return duration, frames
        finally:
            container.close()


class PaddleOcrRecognizer:
    """惰性 CPU 多语言 PaddleOCR 适配器。"""

    def __init__(self) -> None:
        self._engine = None
        self._rapid_engine = None
        self._paddle_unavailable = False

    def _get_engine(self):
        if self._engine is None:
            from paddleocr import PaddleOCR

            options = {
                "lang": "ch",
                "use_doc_orientation_classify": False,
                "use_doc_unwarping": False,
                "use_textline_orientation": False,
                "enable_mkldnn": False,
            }
            try:
                self._engine = PaddleOCR(**options)
            except TypeError:
                self._engine = PaddleOCR(lang="ch")
        return self._engine

    def recognize(self, frames) -> VideoOcrResult:
        """识别关键帧文字并返回去重后的安全结果。

        Args:
            frames: 带时间戳的关键帧序列。

        Returns:
            仅包含文字和时间戳的 OCR 结果。
        """
        if isinstance(frames, (str, Path)):
            return self.recognize_image(str(frames))
        results: list[VideoOcrFrame] = []
        for timestamp, image in frames:
            if self._paddle_unavailable:
                text = _rapid_ocr_text(image, self._get_rapid_engine())
            else:
                try:
                    output = self._recognize(image)
                    text = _ocr_text(output)
                except Exception:
                    self._paddle_unavailable = True
                    text = _rapid_ocr_text(image, self._get_rapid_engine())
            results.append(
                VideoOcrFrame(
                    timestamp_seconds=timestamp,
                    text=text,
                    status="SUCCESS" if text else "NO_TEXT",
                )
            )
        return VideoOcrResult(
            combined_text="\n".join(item.text for item in results), frames=results
        )

    def recognize_image(self, path: str) -> str:
        """识别一个本地图片 artifact，供 image raw extraction 复用。

        Args:
            path: 本地图片 artifact 路径。

        Returns:
            OCR 纯文本；没有文字时为空字符串。
        """
        from PIL import Image

        try:
            from pillow_heif import register_heif_opener

            register_heif_opener()
        except ImportError:
            pass

        with Image.open(path) as image:
            if self._paddle_unavailable:
                return _rapid_ocr_text(image, self._get_rapid_engine())
            try:
                return _ocr_text(self._recognize(image))
            except Exception:
                self._paddle_unavailable = True
                return _rapid_ocr_text(image, self._get_rapid_engine())

    def _recognize(self, image):
        import numpy as np
        from PIL import Image

        if isinstance(image, Image.Image):
            image = np.asarray(image.convert("RGB"))
        engine = self._get_engine()
        if hasattr(engine, "predict"):
            return engine.predict(image)
        return engine.ocr(image, cls=False)

    def _get_rapid_engine(self):
        if self._rapid_engine is None:
            from rapidocr_onnxruntime import RapidOCR

            self._rapid_engine = RapidOCR()
        return self._rapid_engine


def _rapid_ocr_text(image, engine) -> str:
    """提取 RapidOCR 的 ``box/text/score`` 结果，不保存置信度。"""
    import numpy as np
    from PIL import Image

    if isinstance(image, Image.Image):
        image = np.asarray(image.convert("RGB"))
    result, _ = engine(image)
    if not result:
        return ""
    return " ".join(
        str(item[1]).strip()
        for item in result
        if isinstance(item, (list, tuple)) and len(item) > 1 and str(item[1]).strip()
    )


def _ocr_text(output) -> str:
    """仅从 PaddleOCR 2.x 的 ``(text, score)`` 行记录提取文字。"""
    values: list[str] = []

    def visit(value) -> None:
        if isinstance(value, dict):
            for key in ("rec_texts", "text", "texts"):
                candidate = value.get(key)
                if isinstance(candidate, str):
                    values.append(candidate.strip())
                elif isinstance(candidate, (list, tuple)):
                    values.extend(
                        str(item).strip()
                        for item in candidate
                        if str(item).strip()
                    )
            for item in value.values():
                if isinstance(item, (dict, list, tuple)):
                    visit(item)
            return
        if hasattr(value, "json"):
            try:
                visit(value.json)
                return
            except Exception:
                pass
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
