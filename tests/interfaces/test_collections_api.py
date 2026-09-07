"""收藏夹 HTTP API 的合成集成测试。"""

import logging

import pytest
from httpx import ASGITransport, AsyncClient
from xhs_adapters.config import AppSettings
from xhs_api.app import create_api

from tests.interfaces.helpers import FakeService

_EXTENSION_ID = "synthetic-collection-extension"
_ORIGIN = f"chrome-extension://{_EXTENSION_ID}"
_SENTINEL = "synthetic-secret-token-never-leak"


def _reordered_items(count: int) -> list[dict[str, object]]:
    """Return the same feed set in reverse order with valid source_order."""
    return [
        {
            "feed_id": f"feed-{index}",
            "xsec_token": "synthetic-token",
            "source_order": order,
        }
        for order, index in enumerate(reversed(range(count)))
    ]


def _items(count: int, token: str = "synthetic-token") -> list[dict[str, object]]:
    return [
        {
            "feed_id": f"feed-{index}",
            "xsec_token": token,
            "source_order": index,
        }
        for index in range(count)
    ]


async def _register(client: AsyncClient) -> dict[str, str]:
    response = await client.post(
        "/publication/extension/register",
        json={"extension_id": _EXTENSION_ID},
        headers={"Origin": _ORIGIN},
    )
    assert response.status_code == 200
    return {
        "Origin": _ORIGIN,
        "Authorization": f"Bearer {response.json()['token']}",
        "X-Extension-Id": _EXTENSION_ID,
    }


async def _client(api, base_url: str = "http://127.0.0.1:5556"):
    return AsyncClient(transport=ASGITransport(app=api), base_url=base_url)


@pytest.mark.parametrize("count", [0, 1, 50, 500])
async def test_collection_import_supports_synthetic_sizes(tmp_path, count: int) -> None:
    """收藏导入 API 支持空集、1、50 和 500 条 synthetic items。

    Args:
        tmp_path: pytest 提供的临时目录。
        count: 本次 synthetic 导入的条目数。
    """
    api = create_api(AppSettings(work_path=tmp_path), lambda _: FakeService())
    async with api.router.lifespan_context(api), await _client(api) as client:
        headers = await _register(client)
        response = await client.post(
            "/collections/board/synthetic-board/imports",
            json={"request_id": f"request-{count}", "items": _items(count)},
            headers=headers,
        )

    assert response.status_code == 201
    body = response.json()
    assert body["item_count"] == count
    assert "xsec_token" not in response.text
    assert body["diff"] == {
        "added_count": count,
        "retained_count": 0,
        "removed_count": 0,
    }


async def test_collection_api_replays_conflict_and_reorder_semantics(tmp_path) -> None:
    """收藏 API 保持 retry、冲突和重排 fingerprint 语义。

    Args:
        tmp_path: pytest 提供的临时目录。
    """
    api = create_api(AppSettings(work_path=tmp_path), lambda _: FakeService())
    async with api.router.lifespan_context(api), await _client(api) as client:
        headers = await _register(client)
        first_payload = {"request_id": "request-1", "items": _items(3)}
        first = await client.post(
            "/collections/board/board-1/imports",
            json=first_payload,
            headers=headers,
        )
        replay = await client.post(
            "/collections/board/board-1/imports",
            json={**first_payload, "items": _items(3, _SENTINEL)},
            headers=headers,
        )
        conflict = await client.post(
            "/collections/board/board-1/imports",
            json={"request_id": "request-1", "items": _items(2)},
            headers=headers,
        )
        reordered = await client.post(
            "/collections/board/board-1/imports",
            json={
                "request_id": "request-2",
                "items": _reordered_items(3),
            },
            headers=headers,
        )

    assert replay.status_code == 201
    assert replay.json()["snapshot_id"] == first.json()["snapshot_id"]
    assert conflict.status_code == 409
    assert _SENTINEL not in conflict.text
    assert reordered.json()["board_revision"] == 2
    assert reordered.json()["diff"] == {
        "added_count": 0,
        "retained_count": 3,
        "removed_count": 0,
    }
    assert reordered.json()["fingerprint"] != first.json()["fingerprint"]
    assert _SENTINEL not in replay.text


async def test_collection_api_reads_latest_history_and_ordered_snapshot(
    tmp_path,
) -> None:
    """收藏 API 可读取 latest、history 和有序 snapshot detail。

    Args:
        tmp_path: pytest 提供的临时目录。
    """
    settings = AppSettings(work_path=tmp_path)
    api = create_api(settings, lambda _: FakeService())
    async with api.router.lifespan_context(api), await _client(api) as client:
        headers = await _register(client)
        first = await client.post(
            "/collections/board/board-1/imports",
            json={"request_id": "request-1", "items": _items(2)},
            headers=headers,
        )
        second = await client.post(
            "/collections/board/board-1/imports",
            json={"request_id": "request-2", "items": _reordered_items(2)},
            headers=headers,
        )
        second_id = second.json()["snapshot_id"]

    restarted_api = create_api(settings, lambda _: FakeService())
    async with (
        restarted_api.router.lifespan_context(restarted_api),
        await _client(restarted_api) as client,
    ):
        headers = await _register(client)
        latest = await client.get("/collections/board/board-1/latest", headers=headers)
        history = await client.get(
            "/collections/board/board-1/snapshots", headers=headers
        )
        detail = await client.get(
            f"/collections/board/board-1/snapshots/{second_id}", headers=headers
        )

    assert first.status_code == 201
    assert second.status_code == 201
    assert latest.status_code == 200
    assert latest.json()["snapshot_id"] == second.json()["snapshot_id"]
    assert [item["source_order"] for item in latest.json()["items"]] == [0, 1]
    assert [item["board_revision"] for item in history.json()["items"]] == [2, 1]
    assert detail.status_code == 200
    assert detail.json()["items"] == [
        {"feed_id": "feed-1", "source_order": 0},
        {"feed_id": "feed-0", "source_order": 1},
    ]
    assert "xsec_token" not in latest.text + history.text + detail.text


async def test_collection_api_requires_extension_and_only_accepts_loopback(
    tmp_path,
) -> None:
    """收藏导入与读取均复用扩展认证及本机访问边界。

    Args:
        tmp_path: pytest 提供的临时目录。
    """
    api = create_api(AppSettings(work_path=tmp_path), lambda _: FakeService())
    async with api.router.lifespan_context(api):
        async with await _client(api) as local:
            headers = await _register(local)
            missing_auth = await local.get(
                "/collections/board/board-1/latest", headers={"Origin": _ORIGIN}
            )
        async with AsyncClient(
            transport=ASGITransport(app=api, client=("203.0.113.9", 40002)),
            base_url="http://127.0.0.1:5556",
        ) as remote:
            remote_read = await remote.get(
                "/collections/board/board-1/latest", headers=headers
            )

    assert missing_auth.status_code == 401
    assert remote_read.status_code == 403


async def test_collection_api_redacts_validation_error_and_logs(
    tmp_path, caplog
) -> None:
    """Token sentinel 不出现在成功、校验错误或日志路径。

    Args:
        tmp_path: pytest 提供的临时目录。
        caplog: pytest 日志捕获 fixture。
    """
    caplog.set_level(logging.DEBUG)
    api = create_api(AppSettings(work_path=tmp_path), lambda _: FakeService())
    async with api.router.lifespan_context(api), await _client(api) as client:
        headers = await _register(client)
        invalid = await client.post(
            "/collections/board/board-1/imports",
            json={
                "request_id": "request-invalid",
                "items": [
                    {
                        "feed_id": "feed-a",
                        "xsec_token": "   ",
                        "source_order": 0,
                    }
                ],
            },
            headers=headers,
        )
        duplicate = await client.post(
            "/collections/board/board-1/imports",
            json={
                "request_id": "request-duplicate",
                "items": [
                    {
                        "feed_id": "feed-a",
                        "xsec_token": _SENTINEL,
                        "source_order": 0,
                    },
                    {
                        "feed_id": "feed-a",
                        "xsec_token": _SENTINEL,
                        "source_order": 1,
                    },
                ],
            },
            headers=headers,
        )

    assert invalid.status_code == 422
    assert duplicate.status_code == 422
    assert _SENTINEL not in invalid.text + duplicate.text
    assert all(_SENTINEL not in record.getMessage() for record in caplog.records)
