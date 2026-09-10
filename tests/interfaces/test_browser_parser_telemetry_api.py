"""浏览器详情 parser 遥测的 API 安全边界测试。"""

from httpx import ASGITransport, AsyncClient
from xhs_adapters.config import AppSettings
from xhs_api.app import create_api

from tests.interfaces.helpers import FakeService


async def test_browser_failure_api_preserves_safe_parser_telemetry_end_to_end(
    tmp_path,
) -> None:
    """确保 parser 遥测经过 API 与持久化后仍只有安全字段。

    Args:
        tmp_path: Pytest 提供的临时目录。
    """
    api = create_api(AppSettings(work_path=tmp_path), lambda _: FakeService())
    extension_id = "synthetic-c7a-parser-telemetry-extension"
    origin = f"chrome-extension://{extension_id}"
    telemetry = {
        "initial_state_anchor_present": True,
        "initial_state_parse_result": "PARSED",
        "note_root_present": True,
        "note_detail_map_present": True,
        "note_detail_map_count": 1,
        "target_wrapper_found": False,
        "target_wrapper_match_mode": "NONE",
        "target_note_present": False,
        "target_note_id_match": False,
        "author_object_present": False,
        "author_id_present": False,
        "image_list_present": False,
        "image_list_length": 0,
        "normalized_note_type": "NOT_REACHED",
        "last_completed_parser_boundary": "NOTE_DETAIL_MAP_FOUND",
        "parser_failure_subtype": "TARGET_WRAPPER_NOT_FOUND",
        "safe_exception_class": "Error",
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
            "failure_stage": "page_parser",
            "failure_code": "PAGE_TASK_ERROR",
            "parser_telemetry": {
                **telemetry,
                "title": "用户原文",
                "raw_exception": "secret raw exception",
                "xsec_token": "secret-token",
            },
        }
        completed = await client.post(
            f"/browser/extension/tasks/{submitted.json()['task_id']}/result",
            headers={
                **headers,
                "X-Browser-Lease": claimed.json()["lease_token"],
            },
            json={
                "status": "failed",
                "message": "synthetic parser telemetry",
                "result": result,
            },
        )
        fetched = await client.get(f"/browser/tasks/{submitted.json()['task_id']}")
        listed = await client.get("/browser/tasks")

    expected = {
        "failure_stage": "page_parser",
        "failure_code": "PAGE_TASK_ERROR",
        "parser_telemetry": telemetry,
    }
    assert completed.status_code == 200
    assert completed.json()["result"] == expected
    assert fetched.json()["result"] == expected
    assert listed.json()[0]["result"] == expected
    exposed = completed.text + fetched.text + listed.text
    assert "用户原文" not in exposed
    assert "secret raw exception" not in exposed
    assert "secret-token" not in exposed
