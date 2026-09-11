"""PyAV 音轨解码适配器。"""

from hashlib import sha256
from pathlib import Path
from tempfile import mkdtemp
from wave import open as open_wave

import av


class PyAvAudioExtractor:
    """用 PyAV 在没有系统 ffmpeg 命令时抽取临时 16kHz 单声道 WAV。"""

    def __init__(self, root: Path | None = None) -> None:
        self._root = root or Path(mkdtemp(prefix="xhs-audio-"))
        self._root.mkdir(parents=True, exist_ok=True)

    def extract(self, path: str) -> str:
        """从视频解码音轨到临时 WAV，不把音频作为产品 artifact 保存。

        Args:
            path: 本地视频路径。

        Returns:
            临时 WAV 文件路径。
        """
        target = self._root / f"{sha256(path.encode()).hexdigest()}.wav"
        container = av.open(path)
        try:
            stream = container.streams.audio[0]
            resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
            with open_wave(str(target), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(16000)
                for frame in container.decode(stream):
                    converted = resampler.resample(frame)
                    values = converted if isinstance(converted, list) else [converted]
                    for value in values:
                        output.writeframes(value.to_ndarray().tobytes())
        finally:
            container.close()
        if not target.exists() or target.stat().st_size <= 44:
            raise ValueError("audio_track_unavailable")
        return str(target)

    def cleanup(self, path: str) -> None:
        """删除临时音频文件。

        Args:
            path: 待删除的临时 WAV 路径。
        """
        Path(path).unlink(missing_ok=True)
