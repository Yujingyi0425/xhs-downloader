"""浏览器任务执行领域规则测试。"""

import json

import pytest
from pydantic import ValidationError
from xhs_core.domain import (
    BrowserTaskExecutionResult,
    BrowserTaskKind,
    BrowserTaskStatus,
    browser_task_may_write_platform,
    sanitize_browser_page_diagnostics,
    sanitize_browser_task_message,
)


def test_execution_result_only_accepts_terminal_status() -> None:
    """确保执行器只能回传受支持的三种终态。"""
    result = BrowserTaskExecutionResult(
        status=BrowserTaskStatus.FAILED,
        message="页面结构不受支持",
        result={"diagnostic_code": "synthetic-page-shape"},
    )

    assert result.result == {"diagnostic_code": "synthetic-page-shape"}
    with pytest.raises(ValidationError):
        BrowserTaskExecutionResult.model_validate(
            {"status": "running", "message": "尚未结束"}
        )


def test_unknown_effects_are_classified_conservatively() -> None:
    """确保读取任务与平台写任务采用不同的中断策略。"""
    assert not browser_task_may_write_platform(BrowserTaskKind.LIST_FEEDS)
    assert not browser_task_may_write_platform(BrowserTaskKind.DELETE_COOKIES)
    assert browser_task_may_write_platform(BrowserTaskKind.SET_LIKE)
    assert browser_task_may_write_platform(BrowserTaskKind.POST_COMMENT)


def test_page_diagnostics_are_strictly_whitelisted_and_bounded() -> None:
    """确保页面诊断只保留当前适配器的有界结构标识。"""
    sensitive_token = "sensitive-token-value"
    diagnostics = sanitize_browser_page_diagnostics(
        {
            "adapter_version": "xhs-web-2026.07",
            "selector_profile": "initial-state-v1",
            "page_kind": "feed_detail",
            "matched_anchors": [
                "main_container",
                "authorization",
                "main_container",
                "initial_state",
                *["unknown_anchor"] * 100,
            ],
            "missing_anchors": [
                "detail_container",
                "https://example.invalid/private",
                "comment_container",
            ],
            "url": "https://example.invalid/private",
            "token": sensitive_token,
            "raw_page": "<html>用户原文</html>",
            "user_text": "用户原文",
        }
    )

    assert diagnostics == {
        "adapter_version": "xhs-web-2026.07",
        "selector_profile": "initial-state-v1",
        "page_kind": "feed_detail",
        "matched_anchors": ["main_container", "initial_state"],
        "missing_anchors": ["detail_container", "comment_container"],
    }
    serialized = json.dumps(diagnostics, ensure_ascii=False)
    assert len(serialized) < 400
    assert sensitive_token not in serialized
    assert "用户原文" not in serialized
    assert "example.invalid" not in serialized


def test_page_diagnostics_drop_unknown_and_oversized_values() -> None:
    """确保恶意超长或伪装成诊断字段的文本不会进入结果。"""
    diagnostics = sanitize_browser_page_diagnostics(
        {
            "adapter_version": "xhs-web-" + "x" * 100_000,
            "selector_profile": "https://example.invalid/token",
            "page_kind": "用户输入的页面",
            "matched_anchors": [
                *["unknown_anchor"] * 16,
                "initial_state",
            ],
            "missing_anchors": "detail_container",
        }
    )

    assert diagnostics == {"matched_anchors": []}


def test_media_failure_diagnostics_preserve_only_known_stage_and_code() -> None:
    """确保媒体失败阶段和错误码可保留但不扩大诊断白名单。"""
    diagnostics = sanitize_browser_page_diagnostics(
        {
            "failure_stage": "page_parser",
            "failure_code": "MEDIA_PARSER_EMPTY",
            "unknown_stage": "MESSAGE_RECEIVE",
            "unknown_code": "synthetic-secret-code",
            "signed_media_url": "https://example.invalid/signed.mp4",
            "xsec_token": "synthetic-token",
        }
    )

    assert diagnostics == {
        "failure_stage": "page_parser",
        "failure_code": "MEDIA_PARSER_EMPTY",
    }


def test_parser_telemetry_preserves_only_safe_bounded_fields() -> None:
    """确保 parser 遥测只保留固定枚举、布尔值和计数。"""
    diagnostics = sanitize_browser_page_diagnostics(
        {
            "failure_stage": "page_parser",
            "failure_code": "PAGE_TASK_ERROR",
            "parser_telemetry": {
                "initial_state_anchor_present": True,
                "initial_state_parse_result": "PARSED",
                "note_root_present": True,
                "note_detail_map_present": True,
                "note_detail_map_count": 1,
                "target_wrapper_found": True,
                "target_wrapper_match_mode": "EXACT_KEY",
                "target_note_present": True,
                "target_note_id_match": False,
                "author_object_present": True,
                "author_id_present": True,
                "image_list_present": True,
                "image_list_length": 1,
                "normalized_note_type": "IMAGE",
                "last_completed_parser_boundary": "TARGET_NOTE_FOUND",
                "parser_failure_subtype": "TARGET_NOTE_ID_MISMATCH",
                "safe_exception_class": "Error",
                "title": "用户原文",
                "raw_exception": "secret raw exception",
                "xsec_token": "secret-token",
                "image_list_length_overflow": 1001,
            },
        }
    )

    assert diagnostics == {
        "failure_stage": "page_parser",
        "failure_code": "PAGE_TASK_ERROR",
        "parser_telemetry": {
            "initial_state_anchor_present": True,
            "initial_state_parse_result": "PARSED",
            "note_root_present": True,
            "note_detail_map_present": True,
            "note_detail_map_count": 1,
            "target_wrapper_found": True,
            "target_wrapper_match_mode": "EXACT_KEY",
            "target_note_present": True,
            "target_note_id_match": False,
            "author_object_present": True,
            "author_id_present": True,
            "image_list_present": True,
            "image_list_length": 1,
            "normalized_note_type": "IMAGE",
            "last_completed_parser_boundary": "TARGET_NOTE_FOUND",
            "parser_failure_subtype": "TARGET_NOTE_ID_MISMATCH",
            "safe_exception_class": "Error",
        },
    }
    serialized = json.dumps(diagnostics, ensure_ascii=False)
    assert "用户原文" not in serialized
    assert "secret raw exception" not in serialized
    assert "secret-token" not in serialized


def test_navigation_diagnostics_preserve_bounded_fields_and_drop_secrets() -> None:
    """确保导航遥测只保留批准的有界事实。"""
    diagnostics = sanitize_browser_page_diagnostics(
        {
            "failure_stage": "background",
            "failure_code": "DETAIL_NAVIGATION_FAILED",
            "target_tab_exists": True,
            "last_tab_status": "loading",
            "last_route_class": "/explore/<feed_id>",
            "url_host_is_xhs": True,
            "expected_route_matched": True,
            "elapsed_ms": 5000,
            "tab_removed": False,
            "full_url": "https://www.xiaohongshu.com/explore/feed?xsec_token=secret",
            "xsec_token": "secret-token",
            "Cookie": "secret-cookie",
            "Authorization": "Bearer secret",
            "signed_url": "https://example.invalid/signed.mp4",
            "raw_error": "secret-token",
            "totally_new_secretish_field": "secret",
        }
    )

    assert diagnostics == {
        "failure_stage": "background",
        "failure_code": "DETAIL_NAVIGATION_FAILED",
        "target_tab_exists": True,
        "last_tab_status": "loading",
        "last_route_class": "/explore/<feed_id>",
        "url_host_is_xhs": True,
        "expected_route_matched": True,
        "elapsed_ms": 5000,
        "tab_removed": False,
    }


def test_navigation_diagnostics_reject_invalid_bounded_values() -> None:
    """确保导航遥测不会接受未知枚举或越界整数。"""
    diagnostics = sanitize_browser_page_diagnostics(
        {
            "target_tab_exists": "true",
            "last_tab_status": "interactive",
            "last_route_class": "/explore/real-feed-id",
            "url_host_is_xhs": 1,
            "expected_route_matched": False,
            "elapsed_ms": 60_001,
            "tab_removed": False,
        }
    )

    assert diagnostics == {
        "expected_route_matched": False,
        "tab_removed": False,
    }


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (
            BrowserTaskStatus.FAILED,
            "浏览器任务执行失败，可安全重试",
        ),
        (
            BrowserTaskStatus.NEEDS_REVIEW,
            "浏览器操作结果无法确认，请人工核对平台状态",
        ),
    ],
)
def test_terminal_failure_messages_are_server_controlled(
    status: BrowserTaskStatus,
    expected: str,
) -> None:
    """确保失败消息不会保留 URL、令牌或用户原文。

    Args:
        status: 待清洗的失败终态。
        expected: 服务端固定安全摘要。
    """
    unsafe = "https://example.invalid token=secret 用户原文"

    assert sanitize_browser_task_message(status, unsafe) == expected
