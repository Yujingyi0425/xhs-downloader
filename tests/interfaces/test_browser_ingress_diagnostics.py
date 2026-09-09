"""R4D 浏览器任务结果 ingress presence-only 诊断测试。"""

from xhs_api.browser_ingress_diagnostics import observe_r4d_submission


def test_r4d_ingress_observer_records_presence_only(caplog) -> None:
    """只记录 probe 与 R4A 字段是否存在，不记录字段值。

    Args:
        caplog: Pytest 日志捕获 fixture。
    """
    result = {
        "r4d_submission_probe": True,
        "target_tab_exists": False,
        "last_tab_status": "missing",
        "last_route_class": "/unknown",
        "url_host_is_xhs": False,
        "expected_route_matched": False,
        "elapsed_ms": 123,
        "tab_removed": True,
        "xsec_token": "must-not-be-logged",
    }

    with caplog.at_level("INFO"):
        observed = observe_r4d_submission("synthetic-task", result)

    assert observed == {
        "probe_present": True,
        "target_tab_exists_present": True,
        "last_tab_status_present": True,
        "last_route_class_present": True,
        "url_host_is_xhs_present": True,
        "expected_route_matched_present": True,
        "elapsed_ms_present": True,
        "tab_removed_present": True,
    }
    assert "must-not-be-logged" not in caplog.text
    assert "target_tab_exists=False" not in caplog.text
    assert "last_tab_status=missing" not in caplog.text
    assert "probe_present=True" in caplog.text
