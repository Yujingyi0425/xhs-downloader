"""C7C 浏览器任务边界遥测安全规则。"""

from xhs_core.domain import sanitize_browser_page_diagnostics


def test_c7c_runtime_telemetry_is_bounded_and_secret_safe() -> None:
    """只保留版本、固定边界、失败分类和布尔 marker。"""
    diagnostics = sanitize_browser_page_diagnostics(
        {
            "failure_stage": "background",
            "failure_code": "DETAIL_NAVIGATION_FAILED",
            "browser_runtime_telemetry": {
                "extension_manifest_version": "3.0.0",
                "diagnostic_schema_version": "C7C-1",
                "target_tab_created": True,
                "detail_wait_started": True,
                "detail_wait_result": "FAIL",
                "send_message_attempted": False,
                "send_message_resolved": False,
                "send_message_rejected": False,
                "send_message_failure_class": "NOT_APPLICABLE",
                "content_script_message_received": False,
                "page_task_started": False,
                "parser_invocation_started": False,
                "content_script_response_received": False,
                "page_response_class": "NOT_REACHED",
                "extension_result_built": True,
                "result_submit_attempted": True,
                "result_submit_resolved": False,
                "result_submit_rejected": False,
                "last_completed_runtime_boundary": "RESULT_SUBMIT_ATTEMPTED",
                "raw_exception": "do not persist",
                "raw_url": "https://www.xiaohongshu.com/explore/id?xsec_token=secret",
            },
        }
    )

    assert diagnostics is not None
    telemetry = diagnostics["browser_runtime_telemetry"]
    assert telemetry["extension_manifest_version"] == "3.0.0"
    assert telemetry["detail_wait_result"] == "FAIL"
    assert telemetry["last_completed_runtime_boundary"] == "RESULT_SUBMIT_ATTEMPTED"
    assert "raw_exception" not in telemetry
    assert "raw_url" not in telemetry
    assert "secret" not in str(diagnostics)
