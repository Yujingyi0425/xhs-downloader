"""收藏夹媒体 artifact SQLite 持久化与重启读回测试。"""

from pathlib import Path

import pytest
from aiosqlite import connect
from xhs_adapters.sqlite import SqliteCollectionMediaArtifactRepository
from xhs_core.application.collection_media import CollectionMediaStatus
from xhs_core.application.collection_media_service import CollectionMediaService
from xhs_core.domain import CollectionMediaBatchStatus

from tests.application.test_collection_media import (
    FakeDetailDownloader,
    image,
    make_detail,
    make_item,
)


@pytest.mark.asyncio
async def test_artifact_record_round_trip_preserves_identity_and_metadata(
    tmp_path: Path,
) -> None:
    """单图持久化后保留身份、顺序、摘要和大小，且不保存 locator。

    Args:
        tmp_path: Pytest 提供的合成临时目录。
    """
    database = tmp_path.joinpath("state", "collection.db")
    repository = SqliteCollectionMediaArtifactRepository(database)
    service = CollectionMediaService(FakeDetailDownloader(), repository)
    result = await service.execute(
        make_item(), make_detail(media=[image(1)]), "request-persist"
    )
    reopened = SqliteCollectionMediaArtifactRepository(database)
    stored = await reopened.get("request-persist")
    assert stored is not None
    assert stored.status is CollectionMediaBatchStatus.SUCCEEDED
    artifact = stored.items[0].artifact
    assert artifact is not None
    assert result.items[0].artifact == artifact
    assert artifact.media_index == 1
    assert artifact.kind.value == "图片"
    assert artifact.sha256 == "a" * 64
    assert artifact.size == 10
    assert artifact.path == "synthetic/work-a/1.jpg"
    async with connect(database) as connection:
        cursor = await connection.execute(
            "SELECT payload FROM collection_media_artifact WHERE request_id=?",
            ("request-persist",),
        )
        payload = (await cursor.fetchone())[0]
    assert "example.invalid" not in payload
    assert "xsec_token" not in payload


@pytest.mark.asyncio
async def test_multi_artifact_readback_and_retry_survive_repository_reopen(
    tmp_path: Path,
) -> None:
    """部分成功重启后只重试失败媒体，并恢复稳定顺序。

    Args:
        tmp_path: Pytest 提供的合成临时目录。
    """
    database = tmp_path.joinpath("collection.db")
    first_downloader = FakeDetailDownloader(failures={2})
    first = CollectionMediaService(
        first_downloader,
        SqliteCollectionMediaArtifactRepository(database),
    )
    detail = make_detail(media=[image(1), image(2), image(3)])
    initial = await first.execute(make_item(), detail, "request-restart")
    assert [entry.status for entry in initial.items] == [
        CollectionMediaStatus.SUCCEEDED,
        CollectionMediaStatus.FAILED,
        CollectionMediaStatus.SUCCEEDED,
    ]

    second_downloader = FakeDetailDownloader()
    second = CollectionMediaService(
        second_downloader,
        SqliteCollectionMediaArtifactRepository(database),
    )
    recovered = await second.execute(
        make_item(), detail, "request-restart", retry_failed=True
    )
    assert [indexes for _, indexes in second_downloader.calls] == [{2}]
    assert [entry.media_index for entry in recovered.items] == [1, 2, 3]
    assert all(
        entry.status is CollectionMediaStatus.SUCCEEDED
        for entry in recovered.items
    )

    third = SqliteCollectionMediaArtifactRepository(database)
    stored = await third.get("request-restart")
    assert stored is not None
    assert stored.status is CollectionMediaBatchStatus.SUCCEEDED
    assert [entry.media_index for entry in stored.items] == [1, 2, 3]
    assert [entry.artifact.sha256 for entry in stored.items if entry.artifact] == [
        "a" * 64,
        "a" * 64,
        "a" * 64,
    ]


@pytest.mark.asyncio
async def test_invalid_persisted_payload_is_ignored(tmp_path: Path) -> None:
    """损坏或违反身份约束的历史 payload 不被恢复为成功结果。

    Args:
        tmp_path: Pytest 提供的合成临时目录。
    """
    database = tmp_path.joinpath("collection.db")
    repository = SqliteCollectionMediaArtifactRepository(database)
    assert await repository.get("initialize") is None
    async with connect(database) as connection:
        await connection.execute(
            """
            INSERT INTO collection_media_artifact
                (request_id, snapshot_id, work_id, payload)
            VALUES (?, ?, ?, ?)
            """,
            ("broken", "snapshot", "work-a", '{"request_id": "broken"}'),
        )
        await connection.commit()
    assert await repository.get("broken") is None
