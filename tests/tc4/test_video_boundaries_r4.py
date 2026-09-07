"""TC4 public response and synthetic boundary tests."""

from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from xhs_api.videos import create_video_router
from xhs_core.domain import CollectionSnapshotItem, CollectionVideoContent


class _Repository:
    async def get_snapshot(self, _snapshot_id):
        return object()

    async def list_snapshot_items(self, _snapshot_id):
        return [
            CollectionSnapshotItem(
                snapshot_id="snapshot", feed_id="feed", source_order=0
            )
        ]


class _Service:
    async def list_snapshot(self, _snapshot_id):
        return [CollectionVideoContent(snapshot_id="snapshot", feed_id="feed")]


class _Coordinator:
    def start(self, _key, _factory):
        return True


@pytest.mark.asyncio
async def test_video_public_read_response_redacts_secret_adjacent_fields() -> None:
    """验证 TC4 视频读取 API 不返回 token、URL 或请求头。

    Returns:
        None.
    """
    app = FastAPI()
    app.include_router(create_video_router(_Service(), _Repository(), _Coordinator()))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://127.0.0.1:5556"
    ) as client:
        response = await client.get("/xhs/collections/snapshots/snapshot/videos")
    assert response.status_code == 200
    body = response.text
    for secret in (
        "xsec_token",
        "source_url",
        "Authorization",
        "synthetic-xsec-never-copy",
        "transient-signed-secret-media",
    ):
        assert secret not in body


def test_tc4_synthetic_suite_has_no_external_xhs_media_target() -> None:
    """验证 TC4 synthetic tests 只使用 example.invalid 目标。

    Returns:
        None.
    """
    root = Path(__file__).parent
    for path in root.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "xiaohongshu" + ".com" not in text
        assert "api." + "openai.com" not in text
