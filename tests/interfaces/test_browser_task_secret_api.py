"""Browser task API xsec secret boundary tests."""

from httpx import ASGITransport, AsyncClient
from xhs_adapters.config import AppSettings
from xhs_api.app import create_api

from tests.interfaces.helpers import FakeService

TEST_ONLY_FAKE_XSEC_TOKEN = "TEST_ONLY_FAKE_XSEC_TOKEN"
_EXTENSION_ID = "synthetic-browser-extension"
_ORIGIN = f"chrome-extension://{_EXTENSION_ID}"


async def _register(client: AsyncClient) -> dict[str, str]:
    response = await client.post(
        "/browser/extension/register",
        json={"extension_id": _EXTENSION_ID},
        headers={"Origin": _ORIGIN},
    )
    assert response.status_code == 200
    return {
        "Origin": _ORIGIN,
        "Authorization": f"Bearer {response.json()['token']}",
        "X-Extension-Id": _EXTENSION_ID,
    }


async def test_browser_api_task_readback_redacts_xsec_input(tmp_path) -> None:
    """确保通用任务 API 只在领取时交付短期 xsec 输入。

    Args:
        tmp_path: Pytest temporary directory.
    """
    api = create_api(AppSettings(work_path=tmp_path), lambda _: FakeService())
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
                "kind": "get_feed_media",
                "payload": {
                    "feed_id": "synthetic-feed",
                    "xsec_token": TEST_ONLY_FAKE_XSEC_TOKEN,
                },
            },
        )
        task_id = submitted.json()["task_id"]
        fetched = await client.get(f"/browser/tasks/{task_id}")
        headers = await _register(client)
        claimed = await client.post(
            "/browser/extension/tasks/claim",
            headers=headers,
        )

    assert submitted.status_code == 202
    assert "xsec_token" not in submitted.json()["payload"]
    assert "xsec_token" not in fetched.json()["payload"]
    assert (
        claimed.json()["task"]["payload"]["xsec_token"]
        == TEST_ONLY_FAKE_XSEC_TOKEN
    )
