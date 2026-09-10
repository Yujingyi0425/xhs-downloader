"""浏览器任务缺失失败 envelope 的 HTTP 回归。"""

from httpx import ASGITransport, AsyncClient
from xhs_adapters.config import AppSettings
from xhs_api.app import create_api

from tests.interfaces.helpers import FakeService


async def test_browser_failure_api_replaces_missing_result_with_bounded_fallback(
    tmp_path,
) -> None:
    """真实 HTTP 回传省略 result 时仍可 readback 有界失败 envelope。

    Args:
        tmp_path: Pytest 提供的临时目录。
    """
    api = create_api(AppSettings(work_path=tmp_path), lambda _: FakeService())
    extension_id = "synthetic-missing-envelope-extension"
    origin = f"chrome-extension://{extension_id}"
    async with (
        api.router.lifespan_context(api),
        AsyncClient(
            transport=ASGITransport(app=api),
            base_url="http://127.0.0.1:5556",
        ) as client,
    ):
        submitted = await client.post(
            "/browser/tasks",
            json={
                "kind": "get_feed_detail",
                "payload": {
                    "feed_id": "synthetic-feed",
                    "xsec_token": "synthetic-token",
                },
            },
        )
        registered = await client.post(
            "/browser/extension/register",
            headers={"Origin": origin},
            json={"extension_id": extension_id},
        )
        headers = {
            "Origin": origin,
            "Authorization": f"Bearer {registered.json()['token']}",
            "X-Extension-Id": extension_id,
        }
        claimed = await client.post("/browser/extension/tasks/claim", headers=headers)
        completed = await client.post(
            f"/browser/extension/tasks/{submitted.json()['task_id']}/result",
            headers={**headers, "X-Browser-Lease": claimed.json()["lease_token"]},
            json={
                "status": "failed",
                "message": "旧版扩展未返回失败结果",
                "result": None,
            },
        )
        fetched = await client.get(f"/browser/tasks/{submitted.json()['task_id']}")

    expected = {
        "diagnostic_schema_version": "SERVER-1",
        "last_completed_runtime_boundary": "UNKNOWN",
        "failure_stage": "unknown",
        "failure_code": "RUNTIME_ENVELOPE_MISSING",
        "failure_class": "RUNTIME_ENVELOPE_MISSING",
    }
    assert completed.status_code == 200
    assert completed.json()["result"] == expected
    assert fetched.json()["result"] == expected
