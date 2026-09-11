"""原始笔记抽取的安全、可重启领域记录。"""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class NoteExtractionStatus(StrEnum):
    """一条笔记的原始抽取状态。"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"


class ExtractionMediaType(StrEnum):
    """笔记媒体类型。"""

    IMAGE = "image"
    VIDEO = "video"
    UNKNOWN = "unknown"


class TextProvenanceSource(StrEnum):
    """抽取文本的原始来源。"""

    NOTE_TITLE = "NOTE_TITLE"
    NOTE_BODY = "NOTE_BODY"
    IMAGE_OCR = "IMAGE_OCR"
    VIDEO_ASR = "VIDEO_ASR"
    VIDEO_KEYFRAME_OCR = "VIDEO_KEYFRAME_OCR"
    PAGE_SUBTITLE = "PAGE_SUBTITLE"


class TextProvenance(BaseModel):
    """一段带来源的原始文本；不保存来源 URL。"""

    model_config = ConfigDict(extra="forbid")

    source: TextProvenanceSource
    text: str = Field(max_length=100_000)
    media_index: int | None = Field(default=None, ge=1)
    timestamp_seconds: float | None = Field(default=None, ge=0)


class ExtractionArtifact(BaseModel):
    """与 feed/media 序号绑定的本地产物元数据。"""

    model_config = ConfigDict(extra="forbid")

    feed_id: str = Field(min_length=1, max_length=128)
    media_index: int = Field(ge=1)
    path: str = Field(min_length=1, max_length=500)
    artifact_ref: str = Field(min_length=1, max_length=200)
    sha256: str = Field(min_length=64, max_length=64)
    size: int = Field(ge=0)


class ImageOcrRecord(BaseModel):
    """单张图片 OCR 结果和状态。"""

    model_config = ConfigDict(extra="forbid")

    media_index: int = Field(ge=1)
    artifact: ExtractionArtifact
    status: str = Field(pattern=r"^(SUCCESS|NO_TEXT|FAILED)$")
    text: str = Field(default="", max_length=100_000)
    error_code: str | None = Field(default=None, max_length=200)
    confidence: float | None = Field(default=None, ge=0, le=1)


class NoteExtractionRecord(BaseModel):
    """一条 snapshot/feed 的完整原始抽取记录。"""

    model_config = ConfigDict(extra="forbid")

    snapshot_id: str = Field(min_length=1, max_length=128)
    feed_id: str = Field(min_length=1, max_length=128)
    extraction_version: int = Field(default=1, ge=1)
    media_type: ExtractionMediaType = ExtractionMediaType.UNKNOWN
    title: str | None = Field(default=None, max_length=500)
    body: str | None = Field(default=None, max_length=20_000)
    author_metadata: dict[str, str | None] = Field(default_factory=dict)
    publish_time: int | None = Field(default=None, ge=0)
    update_time: int | None = Field(default=None, ge=0)
    tags_topics: list[str] | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=200)
    extraction_status: NoteExtractionStatus = NoteExtractionStatus.PENDING
    extraction_error_codes: list[str] = Field(default_factory=list, max_length=30)
    text_provenance: list[TextProvenance] = Field(default_factory=list, max_length=500)
    combined_text: str | None = Field(default=None, max_length=200_000)
    image_ocr: list[ImageOcrRecord] = Field(default_factory=list, max_length=100)
    media_artifacts: list[ExtractionArtifact] = Field(
        default_factory=list, max_length=100
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
