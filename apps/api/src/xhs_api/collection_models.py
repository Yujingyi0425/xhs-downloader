"""收藏夹 HTTP API 的敏感输入与公开输出模型。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, SecretStr
from xhs_core.domain import (
    CollectionEnrichmentStatus,
    CollectionFeedDetail,
    CollectionStatus,
    CollectionVideoContent,
)


class CollectionImportItemRequest(BaseModel):
    """收藏导入中的单条敏感输入。"""

    model_config = ConfigDict(extra="forbid")

    feed_id: str = Field(min_length=1, max_length=256)
    xsec_token: SecretStr = Field(min_length=1, repr=False)
    source_order: int = Field(ge=0)


class CollectionImportRequest(BaseModel):
    """收藏夹导入请求；board 身份只来自路径。"""

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1, max_length=128)
    items: list[CollectionImportItemRequest] = Field(
        default_factory=list, max_length=500
    )


class CollectionDiffResponse(BaseModel):
    """相邻快照的非敏感 membership 差异。"""

    model_config = ConfigDict(extra="forbid")

    added: list[str]
    removed: list[str]
    retained: list[str]


class CollectionSnapshotResponse(BaseModel):
    """不包含 token 的收藏快照响应。"""

    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    source_type: str
    board_id: str
    board_revision: int = Field(ge=1)
    request_id: str
    captured_at: datetime
    item_count: int = Field(ge=0)
    fingerprint: str
    status: CollectionStatus
    diff: CollectionDiffResponse


class CollectionSnapshotListItem(BaseModel):
    """历史列表中的不含 token 的快照摘要。"""

    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    board_revision: int = Field(ge=1)
    captured_at: datetime
    item_count: int = Field(ge=0)
    fingerprint: str
    status: CollectionStatus


class CollectionSnapshotListResponse(BaseModel):
    """收藏夹历史快照列表。"""

    model_config = ConfigDict(extra="forbid")

    items: list[CollectionSnapshotListItem]


class CollectionSnapshotItemResponse(BaseModel):
    """快照中的有序 feed membership，不包含 token。"""

    model_config = ConfigDict(extra="forbid")

    feed_id: str
    source_order: int = Field(ge=0)


class CollectionSnapshotDetailResponse(CollectionSnapshotResponse):
    """带有序 membership 的不含 token 的快照详情。"""

    items: list[CollectionSnapshotItemResponse]


class CollectionEnrichRequest(BaseModel):
    """收藏详情 enrichment 的本机管理请求。"""

    model_config = ConfigDict(extra="forbid")

    comment_limit: int = Field(default=10, ge=0, le=100)
    include_replies: bool = False
    reply_limit: int = Field(default=10, ge=0, le=100)
    limit: int | None = Field(default=None, ge=1, le=500)


class CollectionEnrichmentItemResponse(BaseModel):
    """收藏详情 enrichment 的安全条目响应。"""

    feed_id: str
    source_order: int
    status: CollectionEnrichmentStatus
    attempt_count: int
    last_error_code: str | None = None
    detail: CollectionFeedDetail | None = None


class CollectionEnrichmentSummaryResponse(BaseModel):
    """收藏详情 enrichment 的安全批次响应。"""

    snapshot_id: str
    total: int
    succeeded: int
    already_succeeded: int
    failed_retryable: int
    failed_terminal: int
    needs_reimport: int
    needs_review: int
    running_skipped: int
    concurrent_skipped: int
    items: list[CollectionEnrichmentItemResponse]


class CollectionEnrichAcceptedResponse(BaseModel):
    """后台 enrichment 触发响应。"""

    snapshot_id: str
    job_status: str


class VideoProcessRequest(BaseModel):
    """视频处理批次的本机管理参数。"""

    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=1, ge=1, le=3)
    keep_source: bool = False


class VideoProcessAcceptedResponse(BaseModel):
    """视频处理任务已接收响应。"""

    snapshot_id: str
    job_status: str


class VideoContentResponse(BaseModel):
    """不含源 URL、token 或模型调试信息的视频内容响应。"""

    model_config = ConfigDict(extra="forbid")

    source_order: int = Field(ge=0)
    content: CollectionVideoContent
