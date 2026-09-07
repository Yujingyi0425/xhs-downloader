"""收藏夹 HTTP API 的认证与访问边界测试。"""

from httpx import ASGITransport, AsyncClient
from xhs_adapters.config import AppSettings
from xhs_api.app import create_api

from tests.interfaces.helpers import FakeService
from tests.interfaces.test_collections_api import (
    _EXTENSION_ID,
    _ORIGIN,
    _client,
    _register,
)


async def test_collection_api_requires_extension_and_only_accepts_loopback(
    tmp_path,
) -> None:
    """收藏导入与读取均遵循各自认证及本机访问边界。

    Args:
        tmp_path: pytest 提供的临时目录。
    """
    api = create_api(AppSettings(work_path=tmp_path), lambda _: FakeService())
    async with api.router.lifespan_context(api):
        async with await _client(api) as local:
            headers = await _register(local)
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

    assert local_read.status_code == 404
    assert wrong_origin.status_code == 403
    assert invalid_auth.status_code == 401
    assert missing_import_auth.status_code == 401
    assert remote_read.status_code == 403
    assert remote_import.status_code == 403
