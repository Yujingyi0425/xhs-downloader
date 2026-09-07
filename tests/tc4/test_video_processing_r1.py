"""TC4-MVP-B-R1 的合成 artifact、PyAV 和状态语义测试。"""

from asyncio import to_thread
from contextlib import asynccontextmanager
from fractions import Fraction
from pathlib import Path
from typing import ClassVar

import av
import pytest
from xhs_adapters.filesystem.streaming import retry_stream_to_atomic_file
from xhs_adapters.sqlite.video_content import SqliteCollectionVideoContentRepository
from xhs_adapters.video import PyAvVideoInspector, SafeVideoArtifactStore, _ocr_text
from xhs_core.domain import (
    CollectionVideoContent,
    FeedMediaResource,
    FeedMediaResult,
    VideoProcessingStatus,
    VideoStageStatus,
    overall_video_status,
)
from xhs_core.domain.errors import DownloadError


class _Response:
    status_code = 200
    headers: ClassVar[dict[str, str]] = {}

    def __init__(self, data: bytes) -> None:
        self._data = data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def aiter_bytes(self, _chunk_size=None):
        yield self._data


class _Gateway:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.url = None

    def stream(self, url: str, headers=None):
        self.url = url
        return _Response(self.data)


class _RetryGateway:
    def __init__(self, responses) -> None:
        self.responses = responses

    @asynccontextmanager
    async def stream(self, _url: str, _headers=None):
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        yield response


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


@pytest.mark.asyncio
async def test_shared_retry_is_bounded_and_cleans_tc4_marker(tmp_path: Path) -> None:
    """验证共享 retry 的成功、耗尽和 TC4 marker 清理语义。

    Args:
        tmp_path: pytest 提供的临时目录。
    """
    part = tmp_path / "source.part"
    marker = tmp_path / "source.part.url"
    target = tmp_path / "final.mp4"
    result = await retry_stream_to_atomic_file(
        _RetryGateway([DownloadError("temporary"), _Response(b"video")]),
        "https://example.invalid/transient-signed-media",
        part,
        marker,
        target,
        max_attempts=2,
    )
    assert result.target == target
    assert target.read_bytes() == b"video"
    assert not marker.exists()

    exhausted_part = tmp_path / "exhausted.part"
    exhausted_marker = tmp_path / "exhausted.part.url"
    exhausted_target = tmp_path / "exhausted.mp4"
    with pytest.raises(DownloadError):
        await retry_stream_to_atomic_file(
            _RetryGateway([DownloadError("one"), DownloadError("two")]),
            "https://example.invalid/another-transient-media",
            exhausted_part,
            exhausted_marker,
            exhausted_target,
            max_attempts=2,
            cleanup_on_exhaustion=True,
        )
    assert not exhausted_part.exists()
    assert not exhausted_marker.exists()
    assert not exhausted_target.exists()


@pytest.mark.asyncio
async def test_running_rows_are_recovered_after_repository_reopen(
    tmp_path: Path,
) -> None:
    """验证重启回收 RUNNING 且保留单调 attempt fencing。

    Args:
        tmp_path: pytest 提供的临时目录。
    """
    repository = SqliteCollectionVideoContentRepository(tmp_path / "video.db")
    running = CollectionVideoContent(
        snapshot_id="snapshot",
        feed_id="feed",
        status=VideoProcessingStatus.RUNNING,
        attempt_count=1,
    )
    await repository.save(running)

    reopened = SqliteCollectionVideoContentRepository(tmp_path / "video.db")
    assert await reopened.recover_running("snapshot") == 1
    recovered = await reopened.get("snapshot", "feed")
    assert recovered is not None
    assert recovered.status is VideoProcessingStatus.FAILED_RETRYABLE
    assert recovered.attempt_count == 1


@pytest.mark.asyncio
async def test_late_attempt_cas_returns_authoritative_row(tmp_path: Path) -> None:
    """验证旧 attempt 的迟到写入不覆盖权威结果。

    Args:
        tmp_path: pytest 提供的临时目录。
    """
    repository = SqliteCollectionVideoContentRepository(tmp_path / "video.db")
    stale = CollectionVideoContent(
        snapshot_id="snapshot",
        feed_id="feed",
        status=VideoProcessingStatus.RUNNING,
        attempt_count=1,
    )
    await repository.save(stale)
    authoritative = stale.model_copy(
        update={"status": VideoProcessingStatus.SUCCEEDED, "attempt_count": 2}
    )
    await repository.save(authoritative)

    assert await repository.save_if_attempt(stale, expected_attempt=1) is False
    current = await repository.get("snapshot", "feed")
    assert current == authoritative
