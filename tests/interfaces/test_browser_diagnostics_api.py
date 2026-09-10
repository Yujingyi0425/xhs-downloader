"""浏览器任务失败诊断 HTTP 安全边界测试。"""

import json

from aiosqlite import connect
from httpx import ASGITransport, AsyncClient
from xhs_adapters.config import AppSettings
from xhs_api.app import create_api

from tests.interfaces.helpers import FakeService

_EXTENSION_ID = "synthetic-diagnostics-extension"
_ORIGIN = f"chrome-extension://{_EXTENSION_ID}"


async def test_browser_failure_api_never_returns_sensitive_diagnostics(
    tmp_path,
) -> None:
    """确保回传、查询和列表接口都只暴露有界白名单诊断。

    Args:
        tmp_path: Pytest 提供的临时目录。
    """
    api = create_api(AppSettings(work_path=tmp_path), lambda _: FakeService())
    sensitive_token = "sensitive-api-token"
    async with (
        api.router.lifespan_context(api),
        AsyncClient(
            transport=ASGITransport(app=api),
            base_url="http://127.0.0.1:5556",
        ) as client,
    ):
        submitted = await client.post(
            "/browser/tasks",
            json={"kind": "check_login_status", "payload": {}},
        )
        registered = await client.post(
            "/browser/extension/register",
            json={"extension_id": _EXTENSION_ID},
            headers={"Origin": _ORIGIN},
        )
        headers = {
            "Origin": _ORIGIN,
            "Authorization": f"Bearer {registered.json()['token']}",
            "X-Extension-Id": _EXTENSION_ID,
        }
        claimed = await client.post(
            "/browser/extension/tasks/claim",
            headers=headers,
        )
        task_id = submitted.json()["task_id"]
        completed = await client.post(
            f"/browser/extension/tasks/{task_id}/result",
            headers={
                **headers,
                "X-Browser-Lease": claimed.json()["lease_token"],
            },
            json={
                "status": "needs_review",
                "message": (
                    f"页面异常 {sensitive_token} "
                    "https://example.invalid/private 用户输入"
                ),
                "result": {
                    "adapter_version": "xhs-web-2026.07",
                    "selector_profile": "initial-state-v1",
                    "page_kind": "feed_detail",
                    "matched_anchors": [
                        "main_container",
                        "authorization",
                        "main_container",
                        *["initial_state"] * 5_000,
                    ],
                    "missing_anchors": [
                        "detail_container",
                        "raw_page",
                        "comment_container",
                    ],
                    "url": "https://example.invalid/private",
                    "token": sensitive_token,
                    "raw_page": "<html>用户页面原文</html>",
                    "user_text": "用户输入",
                    "oversized": "x" * 100_000,
                },
            },
        )
        fetched = await client.get(f"/browser/tasks/{task_id}")
        listed = await client.get("/browser/tasks")

    expected = {
        "adapter_version": "xhs-web-2026.07",
        "selector_profile": "initial-state-v1",
        "page_kind": "feed_detail",
        "matched_anchors": ["main_container", "initial_state"],
        "missing_anchors": ["detail_container", "comment_container"],
    }
    assert registered.status_code == 200
    assert completed.status_code == 200
    assert completed.json()["result"] == expected
    assert completed.json()["message"] == ("浏览器操作结果无法确认，请人工核对平台状态")
    assert fetched.json()["result"] == expected
    assert fetched.json()["message"] == completed.json()["message"]
    assert listed.json()[0]["result"] == expected
    assert listed.json()[0]["message"] == completed.json()["message"]
    exposed = completed.text + fetched.text + listed.text
    assert sensitive_token not in exposed
    assert "example.invalid" not in exposed
    assert "用户页面原文" not in exposed
    assert "用户输入" not in exposed
    assert len(json.dumps(completed.json()["result"])) < 400


async def test_browser_failure_api_preserves_navigation_telemetry_end_to_end(
    tmp_path,
) -> None:
    """确保 R4A 导航遥测经过 API、规范化、SQLite 和 readback 后仍存在。

    Args:
        tmp_path: Pytest 临时目录。
    """
    api = create_api(AppSettings(work_path=tmp_path), lambda _: FakeService())
    extension_id = "synthetic-r4b-telemetry-extension"
    origin = f"chrome-extension://{extension_id}"
    telemetry = {
        "target_tab_exists": True,
        "last_tab_status": "loading",
        "last_route_class": "/explore/<feed_id>",
        "url_host_is_xhs": True,
        "expected_route_matched": True,
        "elapsed_ms": 1234,
        "tab_removed": False,
    }
    async with (
        api.router.lifespan_context(api),
        AsyncClient(
            transport=ASGITransport(app=api),
            base_url="http://127.0.0.1:5556",
        ) as client,
    ):
        submitted = await client.post(
            "/browser/tasks",
            json={"kind": "check_login_status", "payload": {}},
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
        claimed = await client.post(
            "/browser/extension/tasks/claim",
            headers=headers,
        )
        result = {
            "failure_stage": "background",
            "failure_code": "DETAIL_NAVIGATION_FAILED",
            **telemetry,
            "unknown_field": "drop-me",
            "xsec_token": "synthetic-token",
            "full_url": "https://www.xiaohongshu.com/explore/synthetic",
            "r4d_submission_probe": True,
            "r4d_has_target_tab_exists": True,
            "r4d_has_last_tab_status": True,
            "r4d_has_last_route_class": True,
            "r4d_has_url_host_is_xhs": True,
            "r4d_has_expected_route_matched": True,
            "r4d_has_elapsed_ms": True,
            "r4d_has_tab_removed": True,
        }
        completed = await client.post(
            f"/browser/extension/tasks/{submitted.json()['task_id']}/result",
            headers={
                **headers,
                "X-Browser-Lease": claimed.json()["lease_token"],
            },
            json={
                "status": "failed",
                "message": "synthetic navigation telemetry",
                "result": result,
            },
        )
        fetched = await client.get(f"/browser/tasks/{submitted.json()['task_id']}")
        listed = await client.get("/browser/tasks")

    expected = {
        "failure_stage": "background",
        "failure_code": "DETAIL_NAVIGATION_FAILED",
        "failure_class": "DETAIL_NAVIGATION",
        "diagnostic_schema_version": "SERVER-1",
        "last_completed_runtime_boundary": "UNKNOWN",
        **telemetry,
    }
    assert completed.status_code == 200
    assert completed.json()["result"] == expected
    assert fetched.json()["result"] == expected
    assert listed.json()[0]["result"] == expected
    assert all(not key.startswith("r4d_") for key in completed.json()["result"])
    exposed = completed.text + fetched.text + listed.text
    assert "synthetic-token" not in exposed
    assert "https://www.xiaohongshu.com/explore/synthetic" not in exposed


async def test_browser_api_sanitizes_legacy_terminal_snapshot(tmp_path) -> None:
    """确保升级前旧 SQLite 终态不会通过 list/get API 泄露。

    Args:
        tmp_path: Pytest 提供的临时目录。
    """
    settings = AppSettings(work_path=tmp_path)
    initial_api = create_api(settings, lambda _: FakeService())
    async with (
        initial_api.router.lifespan_context(initial_api),
        AsyncClient(
            transport=ASGITransport(app=initial_api),
            base_url="http://127.0.0.1:5556",
        ) as client,
    ):
        submitted = await client.post(
            "/browser/tasks",
            json={"kind": "check_login_status", "payload": {}},
        )

    secret = "legacy-api-sensitive-token"
    legacy = submitted.json()
    legacy.update(
        {
            "status": "failed",
            "message": (f"页面异常 {secret} https://example.invalid/private 用户原文"),
            "result": {
                "adapter_version": "xhs-web-2026.07",
                "selector_profile": "semantic-dom-v1",
                "page_kind": "home",
                "matched_anchors": ["main_container", "authorization"],
                "missing_anchors": ["initial_state", "raw_page"],
                "url": "https://example.invalid/private",
                "token": secret,
                "raw_page": "<html>用户原文</html>",
            },
        }
    )
    database = settings.state_dir.joinpath("downloads.db")
    async with connect(database) as connection:
        await connection.execute(
            """
            UPDATE browser_task SET status = ?, payload = ?
            WHERE task_id = ?
            """,
            ("failed", json.dumps(legacy), legacy["task_id"]),
        )
        await connection.commit()

    upgraded_api = create_api(settings, lambda _: FakeService())
    async with (
        upgraded_api.router.lifespan_context(upgraded_api),
        AsyncClient(
            transport=ASGITransport(app=upgraded_api),
            base_url="http://127.0.0.1:5556",
        ) as client,
    ):
        listed = await client.get("/browser/tasks")
        fetched = await client.get(f"/browser/tasks/{legacy['task_id']}")
    async with connect(database) as connection:
        row = await (
            await connection.execute(
                "SELECT payload FROM browser_task WHERE task_id = ?",
                (legacy["task_id"],),
            )
        ).fetchone()

    assert listed.status_code == 200
    assert fetched.status_code == 200
    assert listed.json()[0]["message"] == "浏览器任务执行失败，可安全重试"
    assert fetched.json()["message"] == listed.json()[0]["message"]
    exposed = listed.text + fetched.text + (row[0] if row else "")
    assert secret not in exposed
    assert "example.invalid" not in exposed
    assert "用户原文" not in exposed
