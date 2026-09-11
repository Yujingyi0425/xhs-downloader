"""faster-whisper 的本地 CPU 转写适配器。"""

from xhs_core.domain import VideoTranscript, VideoTranscriptSegment


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
        """使用单个惰性初始化的本地模型转写音频或视频。

        Args:
            path: 本地音频或视频路径。

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
