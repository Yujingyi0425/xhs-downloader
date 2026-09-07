"""TC4 视频内容处理的独立领域模型。"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class VideoProcessingStatus(StrEnum):
    """视频内容批次状态。"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_TERMINAL = "failed_terminal"


class VideoStageStatus(StrEnum):
    """视频处理阶段状态。"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_TERMINAL = "failed_terminal"
    SKIPPED = "skipped"


class VideoTranscriptSegment(BaseModel):
    """安全的本地转写片段。"""

    model_config = ConfigDict(extra="forbid")

    start: float = Field(ge=0)
    end: float = Field(ge=0)
    text: str = Field(max_length=20_000)


class VideoTranscript(BaseModel):
    """不含模型调试信息的转写结果。"""

    model_config = ConfigDict(extra="forbid")

    language: str = Field(default="", max_length=32)
    duration_seconds: float = Field(default=0, ge=0)
    text: str = Field(default="", max_length=100_000)
    segments: list[VideoTranscriptSegment] = Field(
        default_factory=list, max_length=2000
    )


class VideoOcrFrame(BaseModel):
    """单个有序关键帧的 OCR 文本。"""

    model_config = ConfigDict(extra="forbid")

    timestamp_seconds: float = Field(ge=0)
    text: str = Field(default="", max_length=20_000)


class VideoOcrResult(BaseModel):
    """按时间顺序去重后的 OCR 结果。"""

    model_config = ConfigDict(extra="forbid")

    combined_text: str = Field(default="", max_length=100_000)
    frames: list[VideoOcrFrame] = Field(default_factory=list, max_length=60)


class VideoArtifact(BaseModel):
    """视频本地安全产物元数据，不保存源 URL。"""

    model_config = ConfigDict(extra="forbid")

    local_video_available: bool = False
    relative_path: str | None = Field(default=None, max_length=500)
    sha256: str | None = Field(default=None, min_length=64, max_length=64)
    size: int = Field(default=0, ge=0)


class CollectionVideoContent(BaseModel):
    """独立于 TC3 enrichment 的视频内容生命周期。"""

    model_config = ConfigDict(extra="forbid")

    snapshot_id: str = Field(min_length=1, max_length=128)
    feed_id: str = Field(min_length=1, max_length=128)
    processing_version: int = Field(default=1, ge=1)
    status: VideoProcessingStatus = VideoProcessingStatus.PENDING
    acquisition_status: VideoStageStatus = VideoStageStatus.PENDING
    stt_status: VideoStageStatus = VideoStageStatus.PENDING
    ocr_status: VideoStageStatus = VideoStageStatus.PENDING
    duration_seconds: float = Field(default=0, ge=0)
    artifact: VideoArtifact = Field(default_factory=VideoArtifact)
    transcript: VideoTranscript | None = None
    ocr: VideoOcrResult | None = None
    attempt_count: int = Field(default=0, ge=0)
    last_error_code: str | None = Field(default=None, max_length=200)


def overall_video_status(
    acquisition: VideoStageStatus,
    stt: VideoStageStatus,
    ocr: VideoStageStatus,
) -> VideoProcessingStatus:
    """按阶段状态计算整体状态。

    Args:
        acquisition: 获取阶段。
        stt: 转写阶段。
        ocr: OCR 阶段。

    Returns: 计算出的整体状态。
    """
    if VideoStageStatus.RUNNING in {acquisition, stt, ocr}:
        return VideoProcessingStatus.RUNNING
    if VideoStageStatus.FAILED_TERMINAL in {acquisition, stt, ocr}:
        return VideoProcessingStatus.FAILED_TERMINAL
    if VideoStageStatus.FAILED_RETRYABLE in {acquisition, stt, ocr}:
        return VideoProcessingStatus.FAILED_RETRYABLE
    if all(
        stage in {VideoStageStatus.SUCCEEDED, VideoStageStatus.SKIPPED}
        for stage in (acquisition, stt, ocr)
    ):
        return VideoProcessingStatus.SUCCEEDED
    return VideoProcessingStatus.PENDING
