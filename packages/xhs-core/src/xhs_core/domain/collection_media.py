"""收藏夹媒体结果的持久化模型。"""

from enum import StrEnum
from pathlib import PurePosixPath

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import DownloadArtifact, MediaKind


class CollectionMediaBatchStatus(StrEnum):
    """收藏夹媒体批次的汇总状态。"""

    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    DEFERRED = "deferred"


class CollectionMediaItemStatus(StrEnum):
    """收藏夹媒体单项的持久化状态。"""

    SUCCEEDED = "succeeded"
    FAILED = "failed"


class CollectionMediaDeferredRecord(BaseModel):
    """本阶段未执行的媒体记录。"""

    model_config = ConfigDict(extra="forbid")

    work_id: str = Field(min_length=1, max_length=128)
    media_index: int | None = Field(default=None, ge=1)
    kind: MediaKind | None = None
    reason: str = Field(min_length=1, max_length=200)


class CollectionMediaItemRecord(BaseModel):
    """一个可重启恢复的媒体结果记录。"""

    model_config = ConfigDict(extra="forbid")

    snapshot_id: str = Field(min_length=1, max_length=128)
    source_order: int = Field(ge=0)
    work_id: str = Field(min_length=1, max_length=128)
    media_index: int = Field(ge=1)
    kind: MediaKind
    status: CollectionMediaItemStatus
    artifact: DownloadArtifact | None = None
    error_code: str | None = Field(
        default=None,
        max_length=200,
        pattern=r"^[a-z0-9_]+$",
    )

    def validate_invariants(self) -> None:
        """验证单项状态与 artifact 之间的关系。"""
        if self.status is CollectionMediaItemStatus.SUCCEEDED:
            if self.artifact is None or self.error_code is not None:
                raise ValueError("成功媒体必须有 artifact 且不得有 error_code")
            if (
                self.artifact.media_index != self.media_index
                or self.artifact.kind is not self.kind
            ):
                raise ValueError("artifact 媒体身份不匹配")
        elif self.artifact is not None:
            raise ValueError("失败媒体不得保留 artifact")


class CollectionMediaBatchRecord(BaseModel):
    """可持久化、可重启读回的收藏夹媒体批次。"""

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1, max_length=128)
    snapshot_id: str = Field(min_length=1, max_length=128)
    source_order: int = Field(ge=0)
    work_id: str = Field(min_length=1, max_length=128)
    status: CollectionMediaBatchStatus
    items: list[CollectionMediaItemRecord] = Field(max_length=100)
    deferred: list[CollectionMediaDeferredRecord] = Field(max_length=100)

    @field_validator("items")
    @classmethod
    def validate_items(
        cls, items: list[CollectionMediaItemRecord]
    ) -> list[CollectionMediaItemRecord]:
        """拒绝重复媒体身份并验证每项状态。

        Args:
            items: 待持久化的媒体结果列表。

        Returns:
            通过身份校验的原始列表。
        """
        identities: set[tuple[str, int, MediaKind]] = set()
        for item in items:
            item.validate_invariants()
            identity = (item.work_id, item.media_index, item.kind)
            if identity in identities:
                raise ValueError("重复媒体身份")
            identities.add(identity)
        return items

    @field_validator("items", "deferred")
    @classmethod
    def validate_no_paths_or_urls(cls, values):
        """仅允许 artifact 元数据，拒绝将 locator 混入持久化模型。

        Args:
            values: 待检查的 artifact 或 deferred 列表。

        Returns:
            通过路径校验的原始列表。
        """
        for value in values:
            if isinstance(value, CollectionMediaItemRecord) and value.artifact:
                path = PurePosixPath(value.artifact.path.replace("\\", "/"))
                has_drive = (
                    len(path.parts) > 0
                    and len(path.parts[0]) == 2
                    and path.parts[0][1] == ":"
                )
                if path.is_absolute() or has_drive or ".." in path.parts:
                    raise ValueError("artifact path must remain relative")
        return values

    def validate_invariants(self) -> None:
        """验证批次状态和身份一致性。"""
        for item in self.items:
            if (
                item.snapshot_id != self.snapshot_id
                or item.source_order != self.source_order
                or item.work_id != self.work_id
            ):
                raise ValueError("媒体记录与批次身份不匹配")
        success = any(
            item.status is CollectionMediaItemStatus.SUCCEEDED for item in self.items
        )
        failed = any(
            item.status is CollectionMediaItemStatus.FAILED for item in self.items
        )
        if failed and success:
            expected = CollectionMediaBatchStatus.PARTIAL
        elif failed:
            expected = CollectionMediaBatchStatus.FAILED
        elif self.deferred and not self.items:
            expected = CollectionMediaBatchStatus.DEFERRED
        elif self.deferred:
            expected = CollectionMediaBatchStatus.PARTIAL
        else:
            expected = CollectionMediaBatchStatus.SUCCEEDED
        if self.status is not expected:
            raise ValueError("批次状态与媒体结果不匹配")
