"""收藏夹媒体 C3 重试、幂等和部分失败语义测试。"""

import asyncio

import pytest
from xhs_core.application.collection_media import CollectionMediaStatus
from xhs_core.application.collection_media_service import CollectionMediaService
from xhs_core.domain import CollectionMediaBatchStatus

from tests.application.test_collection_media import (
    FakeDetailDownloader,
    image,
    make_detail,
    make_item,
)


class MemoryCollectionMediaRepository:
    """模拟重启前后仍共享数据的合成 repository。"""

    def __init__(self, records=None) -> None:
        self.records = records if records is not None else {}

    async def get(self, request_id):
        """读取合成批次。

        Args:
            request_id: 合成请求标识。

        Returns:
            已保存的合成记录或空值。
        """
        record = self.records.get(request_id)
        return record.model_copy(deep=True) if record else None

    async def save(self, record) -> None:
        """保存合成批次。

        Args:
            record: 待保存的合成记录。
        """
        self.records[record.request_id] = record.model_copy(deep=True)


class DelayedDownloader(FakeDetailDownloader):
    """以非输入顺序完成媒体的合成下载器。"""

    def __init__(self) -> None:
        super().__init__()
        self.completed: list[int] = []

    async def download_detail(self, detail, indexes, on_progress=None):
        """按预设延迟返回 artifact。

        Args:
            detail: 合成作品详情。
            indexes: 待下载的媒体序号。
            on_progress: 未使用的合成进度回调。

        Returns:
            延迟后返回的合成 artifact 列表。
        """
        media_index = next(iter(indexes))
        delays = {1: 0.04, 2: 0.01, 3: 0.03, 4: 0.02}
        await asyncio.sleep(delays[media_index])
        self.completed.append(media_index)
        return await super().download_detail(detail, indexes, on_progress)


def gallery_detail():
    """构造四图合成详情。"""
    return make_detail(media=[image(1), image(2), image(3), image(4)])


@pytest.mark.asyncio
async def test_completion_order_is_not_exposed() -> None:
    """下载完成顺序变化时，读出顺序仍按媒体序号稳定排列。"""
    downloader = DelayedDownloader()
    service = CollectionMediaService(downloader, MemoryCollectionMediaRepository())
    result = await service.execute(make_item(), gallery_detail(), "request-order")
    assert downloader.completed == [2, 4, 3, 1]
    assert [entry.media_index for entry in result.items] == [1, 2, 3, 4]


@pytest.mark.parametrize(
    ("failures", "expected_status", "successes"),
    [
        (set(), CollectionMediaBatchStatus.SUCCEEDED, {1, 2, 3}),
        ({1}, CollectionMediaBatchStatus.PARTIAL, {2, 3}),
        ({2}, CollectionMediaBatchStatus.PARTIAL, {1, 3}),
        ({3}, CollectionMediaBatchStatus.PARTIAL, {1, 2}),
        ({1, 3}, CollectionMediaBatchStatus.PARTIAL, {2}),
        ({1, 2, 3}, CollectionMediaBatchStatus.FAILED, set()),
    ],
)
@pytest.mark.asyncio
async def test_full_partial_failure_matrix(
    failures, expected_status, successes
) -> None:
    """首、中、尾、多项及全失败都保留明确的 per-media 语义。

    Args:
        failures: 本次合成下载应失败的媒体序号。
        expected_status: 预期批次状态。
        successes: 预期成功的媒体序号。
    """
    repository = MemoryCollectionMediaRepository()
    downloader = FakeDetailDownloader(failures=failures)
    service = CollectionMediaService(downloader, repository)
    result = await service.execute(
        make_item(),
        make_detail(media=[image(1), image(2), image(3)]),
        "request-failure",
    )
    record = await repository.get("request-failure")
    assert record is not None
    assert record.status is expected_status
    assert {
        entry.media_index
        for entry in result.items
        if entry.status is CollectionMediaStatus.SUCCEEDED
    } == successes
    assert len(result.items) == 3
    assert all(
        entry.artifact is None
        for entry in result.items
        if entry.status is CollectionMediaStatus.FAILED
    )


@pytest.mark.asyncio
async def test_retry_only_downloads_failed_media_and_preserves_successes() -> None:
    """重试只执行失败序号，成功 artifact 不重复生成。"""
    repository = MemoryCollectionMediaRepository()
    downloader = FakeDetailDownloader(failures={2})
    service = CollectionMediaService(downloader, repository)
    detail = make_detail(media=[image(1), image(2), image(3)])
    first = await service.execute(make_item(), detail, "request-retry")
    first_artifacts = {
        entry.media_index: entry.artifact
        for entry in first.items
        if entry.artifact is not None
    }
    downloader.failures.clear()
    retried = await service.execute(
        make_item(), detail, "request-retry", retry_failed=True
    )
    assert [indexes for _, indexes in downloader.calls] == [{1}, {2}, {3}, {2}]
    assert all(
        entry.status is CollectionMediaStatus.SUCCEEDED
        for entry in retried.items
    )
    assert retried.items[0].artifact == first_artifacts[1]
    assert retried.items[2].artifact == first_artifacts[3]
    record = await repository.get("request-retry")
    assert record is not None
    assert record.status is CollectionMediaBatchStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_repeated_identical_request_is_idempotent() -> None:
    """相同 request identity 直接读回，不再次调用 downloader。"""
    repository = MemoryCollectionMediaRepository()
    downloader = FakeDetailDownloader()
    service = CollectionMediaService(downloader, repository)
    detail = make_detail(media=[image(1), image(2)])
    first = await service.execute(make_item(), detail, "request-idempotent")
    second = await service.execute(make_item(), detail, "request-idempotent")
    assert len(downloader.calls) == 2
    assert second.items == first.items
    assert [entry.media_index for entry in second.items] == [1, 2]


@pytest.mark.asyncio
async def test_request_identity_conflict_is_rejected() -> None:
    """同一 request identity 不得指向另一个作品。"""
    repository = MemoryCollectionMediaRepository()
    service = CollectionMediaService(FakeDetailDownloader(), repository)
    await service.execute(
        make_item("work-a"), make_detail("work-a", media=[image(1)]), "request-conflict"
    )
    with pytest.raises(ValueError, match="conflict"):
        await service.execute(
            make_item("work-b"),
            make_detail("work-b", media=[image(1)]),
            "request-conflict",
        )


@pytest.mark.asyncio
async def test_wrong_media_kind_association_is_rejected() -> None:
    """底层返回错误媒体类型时不建立 artifact 关联。"""
    downloader = FakeDetailDownloader(wrong_kinds={1})
    service = CollectionMediaService(downloader, MemoryCollectionMediaRepository())
    result = await service.execute(
        make_item(), make_detail(media=[image(1)]), "request-kind"
    )
    assert result.items[0].status is CollectionMediaStatus.FAILED
    assert result.items[0].error_code == "artifact_identity_mismatch"
