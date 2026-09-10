"""收藏夹媒体编排的纯数据模型。"""

from dataclasses import dataclass
from enum import StrEnum

from xhs_core.domain.models import DownloadArtifact, MediaKind


class CollectionMediaStatus(StrEnum):
    """收藏媒体单项的 C2/C3 状态。"""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEFERRED = "deferred"


@dataclass(frozen=True)
class CollectionMediaTask:
    """一个稳定的收藏夹图像媒体逻辑任务。"""

    snapshot_id: str
    source_order: int
    work_id: str
    source_url: str
    media_index: int
    kind: MediaKind
    media_url: str
    suffix: str

    @property
    def identity(self) -> tuple[str, str, int, MediaKind]:
        """返回不依赖随机数和完成顺序的任务身份。

        Returns:
            snapshot、work、media index 和 kind 组成的稳定身份。
        """
        return (self.snapshot_id, self.work_id, self.media_index, self.kind)

    @property
    def filename_identity(self) -> str:
        """返回用于防止同标题冲突的稳定文件身份提示。

        Returns:
            由 work ID、media index 和 suffix 组成的文件身份。
        """
        return f"{self.work_id}_{self.media_index}.{self.suffix}"


@dataclass(frozen=True)
class DeferredCollectionMedia:
    """本阶段不执行的媒体项。"""

    work_id: str
    media_index: int | None
    kind: MediaKind | None
    reason: str


@dataclass(frozen=True)
class CollectionMediaPlan:
    """一个收藏条目的图像任务计划。"""

    tasks: tuple[CollectionMediaTask, ...]
    deferred: tuple[DeferredCollectionMedia, ...]


@dataclass(frozen=True)
class CollectionMediaItemResult:
    """一个媒体任务的安全结果及其 collection 关联。"""

    snapshot_id: str
    source_order: int
    work_id: str
    media_index: int
    kind: MediaKind
    status: CollectionMediaStatus
    artifact: DownloadArtifact | None = None
    error_code: str | None = None


@dataclass(frozen=True)
class CollectionMediaBatchResult:
    """一个收藏条目的有序媒体结果。"""

    snapshot_id: str
    source_order: int
    work_id: str
    items: tuple[CollectionMediaItemResult, ...]
    deferred: tuple[DeferredCollectionMedia, ...]
