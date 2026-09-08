# TC4 真实视频定位诊断仪表化 R2

```text
PHASE=TC4-REAL-VIDEO-LOCATOR-DIAGNOSTIC-INSTRUMENTATION-R2
BASELINE_COMMIT=ab26dc8a6f65f2339f699e0f26c11694765d8118
R2_TEST_IMPLEMENTATION_COMMIT=1e0d2a15bb64127ffffe3ec085ba1996d3c51965
R2_SOURCE_COMMIT=623e1836b4e868ee30c8fee0d6dbeb29bbf2f130
R2_TEST_FINALIZATION_COMMIT=aa53abaacbb6870432e99d133cf888d37d16fbdf
```

本阶段只修复失败诊断的保留边界，不改变真实媒体执行行为，不运行真实 XHS canary。

## 现有 producer 与丢失边界

```text
EXISTING_DIAGNOSTIC_PRODUCER=apps/extension/src/browser-media-task-runtime.ts::mediaFailureResponse
PAGE_DIAGNOSTIC_PRODUCER=apps/extension/src/browser-page.ts::onMessage failure handler
EXISTING_DIAGNOSTIC_FIELDS=failure_code, failure_stage, adapter_version, selector_profile, page_kind, matched_anchors, missing_anchors
DIAGNOSTICS_BEFORE_SANITIZATION=background/page-parser failure code and stage plus bounded page compatibility diagnostics
DIAGNOSTICS_AFTER_SANITIZATION_BEFORE_R2=page compatibility diagnostics only; media failure code/stage became null
LOSS_BOUNDARY=packages/xhs-core/src/xhs_core/application/browser_execution.py::_normalize_terminal_result
```

`_normalize_terminal_result` 对失败结果调用 `sanitize_browser_page_diagnostics`；R1 白名单没有 `failure_code` 与 `failure_stage`，导致媒体任务的结构化失败原因无法进入持久化任务快照和 caller 观察结果。

## R2 改动

`packages/xhs-core/src/xhs_core/domain/browser_diagnostics.py` 新增显式、有界 allowlist：

- `failure_stage` 只接受现有 producer 的 `background`、`page_parser`。
- `failure_code` 只接受现有 Extension 错误码：导航、目标 Tab、内容脚本、消息派发/响应、媒体 parser 和 identity mismatch 相关枚举。
- URL、token、Cookie、Authorization、原始异常、未知字段和任意页面内容继续丢弃。

未修改 Extension、parser、navigation、tab selection、message routing、downloader、SQLite schema 或 Source of Truth。成功 `GET_FEED_MEDIA` 的 signed locator 仍只通过 ephemeral channel 传递；长期任务状态只保留 `feed_id`、`note_type` 和 `media_count`。

## Test-first 与验证

```text
R2_DIAGNOSTIC_RED=CONFIRMED
SAFE_STAGE_PRESERVATION=PASS
SAFE_FAILURE_CODE_PRESERVATION=PASS
SECRET_DIAGNOSTIC_REDACTION=PASS
SIGNED_URL_REDACTION=PASS
TOKEN_REDACTION=PASS
COOKIE_REDACTION=PASS
AUTHORIZATION_REDACTION=PASS
RAW_ERROR_SECRET_REDACTION=PASS
UNKNOWN_FIELD_FAIL_CLOSED=PASS
SUCCESS_LOCATOR_PERSISTENCE_UNCHANGED=PASS
GET_FEED_MEDIA_FAILURE_DIAGNOSTIC_PROPAGATION=PASS
RUNTIME_CONTROL_FLOW_CHANGED=NO
```

冻结 baseline 上先加入的 synthetic test `tests/application/test_browser_execution_diagnostics.py::test_get_feed_media_failure_preserves_safe_stage_and_code` 确认了诊断丢失；该 test 在 source 修复前失败，R2 allowlist 加入后通过。

质量门：

```text
RUFF=PASS
PYTEST=PASS
PYTEST_TOTAL=702
PYTEST_FAILED=0
COVERAGE=90.59%
COVERAGE_GATE=PASS
ARCHITECTURE_FILE_SIZE_GATE=PASS
EXTENSION_TYPECHECK=PASS
EXTENSION_LINT=PASS
EXTENSION_TEST=PASS
EXTENSION_TEST_FILES=62
EXTENSION_TESTS=413
EXTENSION_COVERAGE=89.94%
EXTENSION_BUILD=PASS
```

真实运行边界保持未触发：

```text
REAL_VIDEO_CANARY_STARTED=NO
REAL_XHS_MEDIA_REQUEST_SENT=NO
REAL_XHS_MEDIA_DOWNLOADED=NO
REAL_MEDIA_COMMITTED=NO
REAL_USER_DATA_COMMITTED=NO
SECRET_COMMITTED=NO
```

真实视频根因尚未解决；R2 只提升下一次 canary 的失败边界定位能力。
