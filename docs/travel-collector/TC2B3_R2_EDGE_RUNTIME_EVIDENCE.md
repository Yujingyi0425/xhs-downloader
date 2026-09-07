# TC2B3-R2 Self-Launched Edge Runtime Evidence

本文件只记录 synthetic runtime 尝试，不包含真实 XHS 数据、Cookie、用户浏览器 profile、Bearer credential 或任何 secret 值。

```text
PHASE=TC2B3-R2-EDGE-RUNTIME-ACCEPTANCE
REPAIR_BASE=9782379d33ed15ff606ee5a8b671992dd656709f
SOURCE_COMMIT=14bcd5cc90fc11d572eeba5088fbb8203b4ce3e1
TEST_COMMIT=7259fd82f487ae306fd01998d97f2403928ed54f
```

## Disposable runtime probe

```text
EDGE_EXECUTABLE=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe
BROWSER_PRODUCT=Microsoft Edge
BROWSER_VERSION=152.0.4191.66
TEMP_PROFILE_USED=YES
PRODUCTION_EXTENSION_DIST=apps/extension/dist
CDP_NO_EXTENSION_ENDPOINT=REACHABLE
CDP_CONNECTED=HOLD_EXTENSION_LOAD_BLOCKED
SELF_LAUNCHED_EDGE=HOLD_EXTENSION_LOAD_BLOCKED
```

Edge was detected and a disposable profile plus localhost CDP endpoint was reachable. The execution environment rejected the command containing the production `--load-extension` / `--disable-extensions-except` arguments, so no unpacked production extension was loaded. The ordinary no-extension Edge target is not counted as Extension runtime evidence.

```text
PRODUCTION_EXTENSION_LOADED=NO
EXTENSION_SERVICE_WORKER_FOUND=NO
REAL_EXTENSION_RUNTIME_USED=HOLD_RUNTIME_ENVIRONMENT
HUMAN_BROWSER_ACTION_REQUIRED=YES
ORIGIN_HEADER_MANUALLY_SET=NO
```

No mock Origin, hand-written Origin header, Node context, or ordinary webpage fetch was used as a substitute. The minimum fallback is to load `apps/extension/dist` as an unpacked extension in Edge with developer mode, then rerun the synthetic proof from that real Service Worker.

## Runtime closure

```text
EXTENSION_REGISTRATION_PRODUCTION_API=HOLD_EXTENSION_NOT_LOADED
REAL_EXTENSION_ORIGIN_CONTRACT=HOLD_EXTENSION_NOT_LOADED
SYNTHETIC_EXTENSION_TO_API_CONTRACT=HOLD_EXTENSION_NOT_LOADED
SYNTHETIC_API_TO_SQLITE=HOLD_EXTENSION_NOT_LOADED
END_TO_END_CONTRACT_CONTINUITY=HOLD_EXTENSION_NOT_LOADED
PERSISTED_SOURCE_ORDER=HOLD_EXTENSION_NOT_LOADED
RUNTIME_IDEMPOTENT_REPLAY=HOLD_EXTENSION_NOT_LOADED
```

No registration token, Authorization value, xsec token, request body, response headers, snapshot, or database data was emitted or written. No production auth or runtime code was changed.

## Independent sentinel and fresh regression facts

```text
INDEPENDENT_SECRET_SENTINELS=PASS
XSEC_TOKEN_URL_REDACTION=PASS
XSEC_TOKEN_LOG_REDACTION=PASS
XSEC_TOKEN_UI_REDACTION=PASS
CAPABILITY_TOKEN_URL_REDACTION=PASS
CAPABILITY_TOKEN_LOG_REDACTION=PASS
CAPABILITY_TOKEN_UI_REDACTION=PASS

EXTENSION_CHECK=PASS
EXTENSION_LINT=PASS
EXTENSION_TEST=PASS
EXTENSION_TEST_TOTAL=406
EXTENSION_COVERAGE=90.12% statements / 92.95% lines
EXTENSION_BUILD=PASS

RUFF_CHECK=PASS
RUFF_FORMAT=PASS
PYTEST=PASS
PYTEST_TOTAL=658
PYTEST_FAILED=0
COVERAGE=91.34%
COVERAGE_GATE=PASS (>=85%)
```

## Scope audit from R2 repair base

```text
EXTENSION_PRODUCTION_SOURCE_CHANGED=NO
PYTHON_PRODUCTION_SOURCE_CHANGED=NO
AUTH_PROTOCOL_CHANGED=NO
COLLECTION_CAPTURE_CONTRACT_CHANGED=NO
PARSER_SEMANTICS_CHANGED=NO
MANIFEST_PERMISSION_CHANGE=NONE
NEW_DEPENDENCIES=NO
GET_FEED_DETAIL_CALLED=NO
COLLECTION_BROWSER_TASK_CREATED=NO
MEDIA_DOWNLOADED=NO
TC3_WORK_STARTED=NO
```

This R2 attempt added only evidence documentation after the repair base. The prior R1 evidence remains unchanged.
