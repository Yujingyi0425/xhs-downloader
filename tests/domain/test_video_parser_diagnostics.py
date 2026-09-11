"""视频定位器与受管运行时身份的安全诊断测试。"""

import json

from xhs_core.domain.browser_diagnostics import sanitize_browser_page_diagnostics


def test_video_diagnostics_keep_safe_shape_and_drop_raw_media_data() -> None:
    """只保留固定诊断字段并丢弃原始媒体数据。"""
    safe = sanitize_browser_page_diagnostics(
        {
            "failure_stage": "page_parser",
            "failure_code": "MEDIA_PARSER_EMPTY",
            "managed_adapter_generation": "v2",
            "diagnostic_schema_version": "MANAGED-2",
            "media_parser_diagnostics": {
                "locator_candidate_source": "STATIC_STATE",
                "url_host_class": "XHS_MEDIA_HOST",
                "url_path_shape_class": "VIDEO_FILE",
                "signed_query_present": "YES",
                "video_variant_count": 2,
                "raw_url": "https://example.invalid/video?xsec_token=secret",
                "raw_state": {"token": "secret"},
            },
        }
    )

    assert safe is not None
    assert safe["managed_adapter_generation"] == "v2"
    assert safe["diagnostic_schema_version"] == "MANAGED-2"
    assert safe["media_parser_diagnostics"] == {
        "locator_candidate_source": "STATIC_STATE",
        "url_host_class": "XHS_MEDIA_HOST",
        "url_path_shape_class": "VIDEO_FILE",
        "signed_query_present": "YES",
        "video_variant_count": 2,
    }
    assert "secret" not in json.dumps(safe)
