"""收藏夹 HTTP API 的合成集成测试。"""

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
    assert body["request_id"] == f"request-{count}"
    assert "xsec_token" not in response.text
    assert body["diff"] == {
        "added": sorted(f"feed-{index}" for index in range(count)),
        "removed": [],
        "retained": [],
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
        different_board = await client.post(
            "/collections/board/board-2/imports",
            json=first_payload,
            headers=headers,
        )
        same_membership = await client.post(
            "/collections/board/board-1/imports",
            json={"request_id": "request-2", "items": _items(3)},
            headers=headers,
        )
        reordered = await client.post(
            "/collections/board/board-1/imports",
            json={
                "request_id": "request-3",
                "items": _reordered_items(3),
            },
            headers=headers,
        )

    assert replay.status_code == 201
    assert replay.json()["snapshot_id"] == first.json()["snapshot_id"]
    assert replay.json()["diff"] == first.json()["diff"]
    assert conflict.status_code == 409
    assert different_board.status_code == 409
    assert _SENTINEL not in conflict.text
    assert same_membership.json()["board_revision"] == 2
    assert reordered.json()["board_revision"] == 3
    assert reordered.json()["diff"] == {
        "added": [],
        "retained": ["feed-0", "feed-1", "feed-2"],
        "removed": [],
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
        latest = await client.get("/collections/board/board-1/latest")
        history = await client.get("/collections/board/board-1/snapshots")
        detail = await client.get(f"/collections/board/board-1/snapshots/{second_id}")
        items = await client.get(
            f"/collections/board/board-1/snapshots/{second_id}/items"
        )
        missing = await client.get("/collections/board/board-1/snapshots/missing")
        bounded_history = await client.get(
            "/collections/board/board-1/snapshots?limit=1"
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
    assert "xsec_token" not in latest.text + history.text + detail.text + items.text
    assert items.json() == detail.json()["items"]
    assert missing.status_code == 404
    assert [item["board_revision"] for item in bounded_history.json()["items"]] == [2]


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
            missing_auth = await local.get("/collections/board/board-1/latest")
            local_read = await local.get("/collections/board/board-1/latest")
            wrong_origin = await local.post(
                "/collections/board/board-1/imports",
                json={"request_id": "request-origin", "items": []},
                headers={**headers, "Origin": "chrome-extension://wrong-id"},
            )
            invalid_auth = await local.post(
                "/collections/board/board-1/imports",
                json={"request_id": "request-invalid-auth", "items": []},
                headers={**headers, "Authorization": "Bearer invalid"},
            )
            missing_import_auth = await local.post(
                "/collections/board/board-1/imports",
                json={"request_id": "request-missing-auth", "items": []},
                headers={"Origin": _ORIGIN, "X-Extension-Id": _EXTENSION_ID},
            )
        async with AsyncClient(
            transport=ASGITransport(app=api, client=("203.0.113.9", 40002)),
            base_url="http://127.0.0.1:5556",
        ) as remote:
            remote_read = await remote.get(
                "/collections/board/board-1/latest", headers=headers
            )
            remote_import = await remote.post(
                "/collections/board/board-1/imports",
                json={"request_id": "request-remote", "items": []},
                headers=headers,
            )

    assert missing_auth.status_code == 404
    assert local_read.status_code == 404
    assert wrong_origin.status_code == 403
    assert invalid_auth.status_code == 401
    assert missing_import_auth.status_code == 401
    assert remote_read.status_code == 403
    assert remote_import.status_code == 403
