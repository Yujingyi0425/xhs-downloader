"""收藏图片生产 API 的合成契约测试。"""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from xhs_api.collection_images import create_collection_image_router
from xhs_core.application import CollectionImageBatchResult, CollectionImageItemResult


class FakeCredentials:
    """接受合成扩展令牌的凭据端口替身。"""

    async def validate(self, identity, token):
        """校验合成凭据。

        Args:
            identity: 扩展安装身份。
            token: 扩展能力令牌。

        Returns:
            凭据是否有效。
        """
        return identity == "synthetic-extension" and token == "synthetic-token"


class FakeRepository:
    """提供 API 路由所需的最小快照身份读取。"""

    async def get_snapshot(self, snapshot_id):
        """读取合成快照。

        Args:
            snapshot_id: 待读取的快照标识。

        Returns:
            合成快照身份或空值。
        """
        if snapshot_id != "snapshot-1":
            return None
        return SimpleNamespace(board_id="board-1")


class FakeProduction:
    """返回确定性的安全图片生产状态。"""

    def __init__(self):
        self.result = CollectionImageBatchResult(
            snapshot_id="snapshot-1",
            status="ready",
            items=(
                CollectionImageItemResult(
                    feed_id="feed-1",
                    source_order=0,
                    enrichment_status="succeeded",
                    media_status="media_succeeded",
                    image_count=1,
                    success_count=1,
                ),
            ),
        )
        self.process_calls = 0
        self.read_calls = 0

    async def process_snapshot(self, snapshot_id, *, retry_failed=False):
        """记录一次生产调用。

        Args:
            snapshot_id: 待处理的快照标识。
            retry_failed: 是否重试失败项。

        Returns:
            合成图片生产结果。
        """
        self.process_calls += 1
        return self.result

    async def read_snapshot(self, snapshot_id):
        """记录一次只读调用。

        Args:
            snapshot_id: 待读取的快照标识。

        Returns:
            合成图片生产结果。
        """
        self.read_calls += 1
        return self.result


@pytest.mark.asyncio
async def test_image_process_endpoint_authenticates_and_returns_safe_status() -> None:
    """图片生产端点校验扩展凭据与 board 身份，并返回状态摘要。"""
    app = FastAPI()
    production = FakeProduction()
    app.state.collection_repository = FakeRepository()
    app.state.collection_images = production
    app.include_router(create_collection_image_router(FakeCredentials()))
    headers = {
        "Authorization": "Bearer synthetic-token",
        "X-Extension-Id": "synthetic-extension",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://127.0.0.1:5556"
    ) as client:
        processed = await client.post(
            "/xhs/collections/snapshots/snapshot-1/process-images",
            json={"board_id": "board-1"},
            headers=headers,
        )
        read = await client.get(
            "/xhs/collections/snapshots/snapshot-1/image-media", headers=headers
        )
        wrong_board = await client.post(
            "/xhs/collections/snapshots/snapshot-1/process-images",
            json={"board_id": "board-2"},
            headers=headers,
        )
        unauthorized = await client.post(
            "/xhs/collections/snapshots/snapshot-1/process-images",
            json={"board_id": "board-1"},
        )

    assert processed.status_code == 200
    assert processed.json()["items"][0]["success_count"] == 1
    assert read.status_code == 200
    assert read.json()["snapshot_id"] == "snapshot-1"
    assert wrong_board.status_code == 404
    assert unauthorized.status_code == 401
    assert production.process_calls == 1
    assert production.read_calls == 1
