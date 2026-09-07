"""收藏夹 HTTP API 的敏感输入与公开输出模型。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, SecretStr
from xhs_core.domain import CollectionStatus


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


class CollectionDiffCounts(BaseModel):
    """相邻快照的非敏感差异计数。"""

    model_config = ConfigDict(extra="forbid")

    added_count: int = Field(ge=0)
    retained_count: int = Field(ge=0)
    removed_count: int = Field(ge=0)


class CollectionSnapshotResponse(BaseModel):
    """不包含 token 的收藏快照响应。"""

    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    source_type: str
    board_id: str
    board_revision: int = Field(ge=1)
    captured_at: datetime
    item_count: int = Field(ge=0)
    fingerprint: str
    status: CollectionStatus
    diff: CollectionDiffCounts


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
