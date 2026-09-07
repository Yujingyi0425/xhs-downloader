"""收藏夹 HTTP API 的 validation 与失败脱敏测试。"""

import logging

import pytest
from xhs_adapters.config import AppSettings
from xhs_api.app import create_api
from xhs_core.application import CollectionImportService

from tests.interfaces.helpers import FakeService
from tests.interfaces.test_collections_api import (
    _SENTINEL,
    _client,
    _items,
    _register,
)


async def test_collection_api_redacts_validation_error_and_logs(
    tmp_path, caplog
) -> None:
    """Token sentinel 不出现在领域校验错误或日志路径。

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


async def test_collection_api_redacts_injected_failure(
    tmp_path, monkeypatch, caplog
) -> None:
    """注入的 application 失败不会泄露 token 或写入日志。

    Args:
        tmp_path: pytest 提供的临时目录。
        monkeypatch: pytest 属性替换 fixture。
        caplog: pytest 日志捕获 fixture。
    """

    async def fail_import(self, command):
        raise RuntimeError(_SENTINEL)

    monkeypatch.setattr(CollectionImportService, "import_snapshot", fail_import)
    caplog.set_level(logging.DEBUG)
    api = create_api(AppSettings(work_path=tmp_path), lambda _: FakeService())
    async with api.router.lifespan_context(api), await _client(api) as client:
        headers = await _register(client)
        response = await client.post(
            "/collections/board/board-1/imports",
            json={"request_id": "request-failure", "items": _items(1)},
            headers=headers,
        )

    assert response.status_code == 500
    assert _SENTINEL not in response.text
    assert all(_SENTINEL not in record.getMessage() for record in caplog.records)


@pytest.mark.parametrize(
    "payload",
    [
        {"request_id": "request-501", "items": _items(501)},
        {
            "request_id": "request-extra",
            "items": [
                {
                    "feed_id": "feed-a",
                    "xsec_token": _SENTINEL,
                    "source_order": 0,
                    "extra": _SENTINEL,
                }
            ],
        },
        {
            "request_id": "request-malformed",
            "items": [{"feed_id": "feed-a", "xsec_token": _SENTINEL}],
        },
        {
            "request_id": "request-order",
            "items": [
                {"feed_id": "feed-a", "xsec_token": _SENTINEL, "source_order": 1}
            ],
        },
    ],
)
async def test_collection_api_redacts_pre_route_validation(
    tmp_path, payload: dict[str, object]
) -> None:
    """pre-route validation 失败也不会回显 token sentinel。

    Args:
        tmp_path: pytest 提供的临时目录。
        payload: 触发请求模型校验失败的输入。
    """
    api = create_api(AppSettings(work_path=tmp_path), lambda _: FakeService())
    async with api.router.lifespan_context(api), await _client(api) as client:
        headers = await _register(client)
        response = await client.post(
            "/collections/board/board-1/imports", json=payload, headers=headers
        )
        state = await client.get("/collections/board/board-1/latest")

    assert response.status_code == 422
    assert _SENTINEL not in response.text
    assert state.status_code == 404
