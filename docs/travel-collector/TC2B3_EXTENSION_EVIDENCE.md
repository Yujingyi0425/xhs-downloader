# TC2B3 Extension Collection Import Evidence

本文只记录 synthetic collection import evidence，不包含真实收藏夹、真实 feed、真实 token、Cookie 或个人路径。

```text
PHASE=TC2B3-EXTENSION-INTEGRATION
BASELINE_COMMIT=8b48cd513f31769a4b1e06eefa3c206b7b34f6e0
SOURCE_COMMIT=14bcd5cc90fc11d572eeba5088fbb8203b4ce3e1
TEST_COMMIT=14bcd5cc90fc11d572eeba5088fbb8203b4ce3e1
```

## Capture to import boundary

```text
CAPTURE_RESULT_REUSED=PASS
CAPTURE_CONTROLLER_REMAINS_CAPTURE_ONLY=PASS
CURRENT_BOARD_CONTRACT_PRESERVED=PASS
PARTIAL_CAPTURE_IMPORTED=NO
REQUEST_MAPPING=CollectionCaptureResult.items -> ordered API items
SOURCE_TYPE_BOARD=PASS
SOURCE_ORDER_PRESERVED=PASS
FEED_ID_UNIQUE=PASS
XSEC_SOURCE_REQUIRED=NO
```

The mapper accepts only a successful result with a non-null board ID. It iterates the final capture Map in insertion order and emits only `feed_id`, `xsec_token`, and contiguous `source_order`; title, author, cover, source URL, profile data, and `xsec_source` are excluded.

```text
IMPORT_0=PASS
IMPORT_1=PASS
IMPORT_50=PASS
IMPORT_500=PASS
IMPORT_501_PLUS_FAIL_CLOSED=PASS
NEW_SCAN_NEW_REQUEST_ID=PASS
RETRY_SAME_REQUEST_ID=PASS
NETWORK_RETRY_SAME_REQUEST_ID=PASS
```

Test references:

```text
apps/extension/src/collection-import.test.ts > TC2B3 collection import contract > maps 0 items in capture order
apps/extension/src/collection-import.test.ts > TC2B3 collection import contract > fails closed above the API limit
apps/extension/src/collection-panel.test.ts > TC1C-R1 collection panel lifecycle > imports only after success and retries the same observation
```

## Authentication and HTTP behavior

```text
EXISTING_CAPABILITY_CREDENTIAL_REUSED=PASS
AUTH_PROTOCOL_CHANGED=NO
IMPORT_401_REFRESH_ONCE=PASS
IMPORT_401_SAME_REQUEST_ID=PASS
IMPORT_403_FAIL_CLOSED=PASS
IMPORT_409_NO_AUTO_REKEY=PASS
IMPORT_422_REDACTED=PASS
IMPORT_5XX_NETWORK_RETRYABLE=PASS
SENDER_BOARD_IDENTITY_CHECK=PASS
REAL_EXTENSION_ORIGIN_CONTRACT=HOLD_RUNTIME_BROWSER_EVIDENCE_UNAVAILABLE
```

The privileged POST is issued by the background boundary with `credentials: omit`, the existing capability credential, `X-Extension-Id`, and optional installation identity. Origin is not manually spoofed. Sender validation requires the XHS board URL and matching board ID. The current browser session had no usable built-extension tab, so production acceptance of the browser-generated Extension Origin remains unverified.

## UI lifecycle and safety

```text
DOUBLE_SUBMIT_GUARD=PASS
STALE_SESSION_GUARD=PASS
CLOSED_PANEL_LATE_RESULT_GUARD=PASS
SCAN_SUCCESS_DISTINCT_FROM_SAVE_SUCCESS=PASS
SUCCESS_UI_NON_SENSITIVE=PASS
FAILURE_UI_DISTINCT=PASS
RETRY_UI_SAME_OBSERVATION=PASS
XSEC_TOKEN_PERSISTED_IN_EXTENSION=NO
XSEC_TOKEN_URL_REDACTION=PASS
XSEC_TOKEN_LOG_REDACTION=PASS
XSEC_TOKEN_UI_REDACTION=PASS
CAPABILITY_TOKEN_URL_REDACTION=PASS
CAPABILITY_TOKEN_LOG_REDACTION=PASS
CAPABILITY_TOKEN_UI_REDACTION=PASS
```

HTTP failures are converted to fixed, non-sensitive UI messages. Neither capture items nor import payloads are written to Extension storage.

## Cross-runtime and scope

```text
SYNTHETIC_EXTENSION_TO_API_CONTRACT=HOLD_RUNTIME_EVIDENCE_REQUIRED
SYNTHETIC_API_TO_SQLITE=HOLD_RUNTIME_EVIDENCE_REQUIRED
END_TO_END_CONTRACT_CONTINUITY=HOLD_RUNTIME_EVIDENCE_REQUIRED
PERSISTED_SOURCE_ORDER=HOLD_RUNTIME_EVIDENCE_REQUIRED
```

The TypeScript mapper and the existing Python production API use the same synthetic field contract. A live built-extension-to-production-API-to-SQLite request was not executed in this environment; therefore the runtime-shaped continuity gate remains HOLD.

```text
COLLECTION_CAPTURE_CONTRACT_CHANGED=NO
PARSER_SEMANTICS_CHANGED=NO
PYTHON_PRODUCTION_SOURCE_CHANGED=NO
MANIFEST_PERMISSION_CHANGE=NONE
NEW_DEPENDENCIES=NO
GET_FEED_DETAIL_CALLED=NO
COLLECTION_BROWSER_TASK_CREATED=NO
MEDIA_DOWNLOADED=NO
TC3_WORK_STARTED=NO
```

## Fresh gates

```text
EXTENSION_CHECK=PASS
EXTENSION_LINT=PASS
EXTENSION_TEST=PASS
EXTENSION_TEST_FILES=59
EXTENSION_TEST_TOTAL=405
EXTENSION_COVERAGE_STATEMENTS=90.12%
EXTENSION_COVERAGE_LINES=92.95%
EXTENSION_BUILD=PASS

RUFF_CHECK=PASS
RUFF_FORMAT=PASS
PYTEST=PASS
PYTEST_TOTAL=658
PYTEST_FAILED=0
COVERAGE=91.34%
COVERAGE_GATE=PASS (>=85%)
```

Fresh commands used the repository package scripts and formal Python Gate. No test was skipped, removed, or weakened.
