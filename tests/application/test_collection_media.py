"""收藏夹图像媒体管线的合成测试。"""

from collections.abc import Callable

import pytest
from xhs_core.application.collection_media import (
    CollectionMediaCoordinator,
    CollectionMediaStatus,
)
from xhs_core.domain import (
    Author,
    CollectionSnapshotItem,
    DownloadArtifact,
    MediaKind,
    MediaResource,
    WorkDetail,
    WorkType,
)
from xhs_core.domain.models import DownloadProgress


class FakeDetailDownloader:
    """只在内存中返回产物的下载端口替身。"""

    def __init__(
        self,
        *,
        failures: set[int] | None = None,
        wrong_indexes: set[int] | None = None,
    ) -> None:
        self.failures = failures or set()
        self.wrong_indexes = wrong_indexes or set()
        self.calls: list[tuple[WorkDetail, set[int]]] = []

    async def download_detail(
        self,
        detail: WorkDetail,
        indexes: set[int],
        on_progress: Callable[[DownloadProgress], None] | None = None,
    ) -> list[DownloadArtifact]:
        """返回可控的合成 artifact 或抛出合成传输错误。"""
        del on_progress
        self.calls.append((detail, indexes))
        media_index = next(iter(indexes))
        if media_index in self.failures:
            raise RuntimeError("synthetic transport failure")
        returned_index = (
            media_index + 1
            if media_index in self.wrong_indexes
            else media_index
        )
        return [
            DownloadArtifact(
                path=f"synthetic/{detail.work_id}/{returned_index}.jpg",
                sha256="a" * 64,
                size=10,
                media_index=returned_index,
                kind=MediaKind.IMAGE,
            )
        ]


def make_item(work_id: str = "work-a", source_order: int = 0) -> CollectionSnapshotItem:
    """构造不含 token、Cookie 或真实用户数据的收藏条目。"""
    return CollectionSnapshotItem(
        snapshot_id="synthetic-snapshot",
        feed_id=work_id,
        source_order=source_order,
    )


def make_detail(
    work_id: str = "work-a",
    *,
    media: list[MediaResource] | None = None,
    title: str = "相同标题",
    work_type: WorkType = WorkType.GALLERY,
) -> WorkDetail:
    """构造合成 canonical 详情。"""
    return WorkDetail(
        work_id=work_id,
        source_url=f"https://www.xiaohongshu.com/explore/{work_id}",
        title=title,
        description="合成详情",
        work_type=work_type,
        author=Author(
            author_id="synthetic-author",
            nickname="合成作者",
            profile_url="https://example.invalid/author",
        ),
        media=media or [],
    )


def image(index: int, suffix: str = "jpg") -> MediaResource:
    """构造一个合成图片媒体。"""
    return MediaResource(
        index=index,
        kind=MediaKind.IMAGE,
        url=f"https://example.invalid/image-{index}.{suffix or 'jpg'}",
        suffix=suffix,
    )


@pytest.mark.asyncio
async def test_single_image_success() -> None:
    """单图任务成功并只调用一次底层下载端口。"""
    downloader = FakeDetailDownloader()
    result = await CollectionMediaCoordinator(downloader).execute(
        make_item(), make_detail(media=[image(1)])
    )
    assert result.snapshot_id == "synthetic-snapshot"
    assert result.source_order == 0
    assert result.work_id == "work-a"
    assert [entry.status for entry in result.items] == [CollectionMediaStatus.SUCCEEDED]
    assert result.items[0].artifact is not None
    assert downloader.calls[0][0].title.endswith("_work-a")
    assert [indexes for _, indexes in downloader.calls] == [{1}]


@pytest.mark.asyncio
async def test_multi_image_n_and_order_are_preserved() -> None:
    """多图任务按 canonical 媒体输入顺序执行并返回。"""
    downloader = FakeDetailDownloader()
    detail = make_detail(media=[image(1), image(2, "png"), image(3, "webp")])
    result = await CollectionMediaCoordinator(downloader).execute(make_item(), detail)
    assert [entry.media_index for entry in result.items] == [1, 2, 3]
    assert [entry.artifact.media_index for entry in result.items if entry.artifact] == [
        1,
        2,
        3,
    ]
    assert [indexes for _, indexes in downloader.calls] == [{1}, {2}, {3}]


def test_repeated_planning_is_deterministic_and_filename_safe() -> None:
    """重复规划稳定，且不同作品不会共享文件名身份提示。"""
    coordinator = CollectionMediaCoordinator(FakeDetailDownloader())
    plan_a = coordinator.plan(
        make_item("work-a"), make_detail("work-a", media=[image(1)])
    )
    plan_b = coordinator.plan(
        make_item("work-a"), make_detail("work-a", media=[image(1)])
    )
    other = coordinator.plan(
        make_item("work-b"), make_detail("work-b", media=[image(1)])
    )
    assert plan_a == plan_b
    assert plan_a.tasks[0].identity == (
        "synthetic-snapshot",
        "work-a",
        1,
        MediaKind.IMAGE,
    )
    assert plan_a.tasks[0].filename_identity != other.tasks[0].filename_identity


@pytest.mark.asyncio
async def test_one_media_failure_does_not_discard_gallery_successes() -> None:
    """单项失败只标记该项，其余图像仍能完成。"""
    downloader = FakeDetailDownloader(failures={2})
    result = await CollectionMediaCoordinator(downloader).execute(
        make_item(), make_detail(media=[image(1), image(2), image(3)])
    )
    assert [entry.status for entry in result.items] == [
        CollectionMediaStatus.SUCCEEDED,
        CollectionMediaStatus.FAILED,
        CollectionMediaStatus.SUCCEEDED,
    ]
    assert result.items[1].error_code == "download_failed"
    assert result.items[0].artifact is not None
    assert result.items[2].artifact is not None


def test_missing_suffix_defaults_to_auto_and_invalid_suffix_fails_closed() -> None:
    """缺少扩展名可确定性退化，路径片段则拒绝。"""
    coordinator = CollectionMediaCoordinator(FakeDetailDownloader())
    plan = coordinator.plan(make_item(), make_detail(media=[image(1, "")]))
    assert plan.tasks[0].suffix == "auto"
    with pytest.raises(ValueError, match="suffix"):
        coordinator.plan(make_item(), make_detail(media=[image(1, "../jpg")]))


def test_work_identity_mismatch_is_rejected() -> None:
    """收藏 membership 与 canonical 详情不一致时 fail closed。"""
    with pytest.raises(ValueError, match="do not match"):
        CollectionMediaCoordinator(FakeDetailDownloader()).plan(
            make_item("work-a"), make_detail("work-b", media=[image(1)])
        )


def test_duplicate_media_index_is_rejected() -> None:
    """重复媒体序号不能产生歧义任务。"""
    with pytest.raises(ValueError, match="unique"):
        CollectionMediaCoordinator(FakeDetailDownloader()).plan(
            make_item(), make_detail(media=[image(1), image(1, "png")])
        )


@pytest.mark.asyncio
async def test_wrong_media_index_association_is_rejected() -> None:
    """底层返回错误媒体序号时不得错误归属 artifact。"""
    downloader = FakeDetailDownloader(wrong_indexes={1})
    result = await CollectionMediaCoordinator(downloader).execute(
        make_item(), make_detail(media=[image(1)])
    )
    assert result.items[0].status is CollectionMediaStatus.FAILED
    assert result.items[0].error_code == "artifact_identity_mismatch"
    assert result.items[0].artifact is None


def test_video_media_is_deferred_without_acquisition() -> None:
    """视频媒体只进入延后队列，不触发下载端口。"""
    downloader = FakeDetailDownloader()
    detail = make_detail(
        work_type=WorkType.VIDEO,
        media=[
            MediaResource(
                index=1,
                kind=MediaKind.VIDEO,
                url="https://example.invalid/video.mp4",
                suffix="mp4",
            )
        ],
    )
    plan = CollectionMediaCoordinator(downloader).plan(make_item(), detail)
    assert plan.tasks == ()
    assert plan.deferred[0].reason == "media_kind_deferred"
    assert downloader.calls == []


def test_empty_video_is_deferred_without_video_runtime() -> None:
    """没有视频地址时也只记录明确的延后状态。"""
    downloader = FakeDetailDownloader()
    plan = CollectionMediaCoordinator(downloader).plan(
        make_item(), make_detail(work_type=WorkType.VIDEO)
    )
    assert plan.tasks == ()
    assert len(plan.deferred) == 1
    assert plan.deferred[0].reason == "video_acquisition_deferred"
