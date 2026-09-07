"""TC4-MVP-B-R1 的合成 artifact、PyAV 和状态语义测试。"""

from asyncio import to_thread
from fractions import Fraction
from pathlib import Path

import av
import pytest
from xhs_adapters.video import PyAvVideoInspector, SafeVideoArtifactStore, _ocr_text
from xhs_core.domain import (
    FeedMediaResource,
    FeedMediaResult,
    VideoProcessingStatus,
    VideoStageStatus,
    overall_video_status,
)


class _Response:
    status_code = 200

    def __init__(self, data: bytes) -> None:
        self._data = data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def aiter_bytes(self):
        yield self._data


class _Gateway:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.url = None

    def stream(self, url: str):
        self.url = url
        return _Response(self.data)


def _video_bytes(seconds: int = 9) -> bytes:
    output = av.open("synthetic.mp4", mode="w", format="mp4")
    stream = output.add_stream("mpeg4", rate=2)
    stream.width, stream.height = 32, 32
    for index in range(seconds * 2):
        frame = av.VideoFrame(32, 32, "rgb24")
        frame.pts = index
        frame.time_base = Fraction(1, 2)
        for packet in stream.encode(frame):
            output.mux(packet)
    for packet in stream.encode():
        output.mux(packet)
    output.close()
    return Path("synthetic.mp4").read_bytes()


@pytest.mark.asyncio
async def test_artifact_uses_safe_relative_path_and_cleanup(tmp_path: Path) -> None:
    """验证安全相对路径、物理文件和删除策略。

    Args:
        tmp_path: pytest 提供的临时目录。
    """
    data = _video_bytes()
    try:
        gateway = _Gateway(data)
        store = SafeVideoArtifactStore(tmp_path, gateway)
        media = FeedMediaResult(
            feed_id="feed-z",
            note_type="video",
            media=[
                FeedMediaResource(
                    index=1,
                    kind="video",
                    url="https://example.invalid/synthetic.mp4",
                    suffix="mp4",
                )
            ],
        )
        relative, digest, size = await store.save("snapshot", "feed-z", media)
        assert relative.endswith("/source.mp4") or relative.endswith("\\source.mp4")
        physical = Path(store.resolve_path(relative))
        assert await to_thread(physical.is_file) and size == len(data)
        assert len(digest) == 64
        await store.discard(relative)
        assert not await to_thread(physical.exists)
    finally:
        await to_thread(Path("synthetic.mp4").unlink, True)


def test_pyav_sampling_is_bounded_and_uses_seconds(tmp_path: Path) -> None:
    """验证 PyAV 使用秒级时间戳并限制采样数量。

    Args:
        tmp_path: pytest 提供的临时目录。
    """
    path = tmp_path / "synthetic.mp4"
    try:
        path.write_bytes(_video_bytes())
        duration, frames = PyAvVideoInspector().inspect(str(path))
        assert duration == pytest.approx(9, abs=1)
        assert len(frames) <= 60
        assert list(timestamp for timestamp, _ in frames) == sorted(
            timestamp for timestamp, _ in frames
        )
        assert frames[0][0] == pytest.approx(0, abs=0.6)
    finally:
        Path("synthetic.mp4").unlink(missing_ok=True)


def test_video_status_and_ocr_schema() -> None:
    """验证部分失败状态和 PaddleOCR 文字字段提取。"""
    assert (
        overall_video_status(
            VideoStageStatus.SUCCEEDED,
            VideoStageStatus.SUCCEEDED,
            VideoStageStatus.FAILED_RETRYABLE,
        )
        is VideoProcessingStatus.FAILED_RETRYABLE
    )
    assert _ocr_text([[[[[0, 0]], ("日本語", 0.99)]]]) == "日本語"
    assert _ocr_text([[[[[0, 0]], ("A", 0.9), "debug-path"]]]) == "A"
