# TC2B3-R3 Manual Edge Runtime Closure

本文只记录 synthetic runtime facts，不包含 capability token、Authorization 值、xsec_token 值、Cookie、真实 XHS 数据或用户 Edge profile 数据。

```text
PHASE=TC2B3-R3-MANUAL-EDGE-RUNTIME-CLOSURE
REPAIR_BASE=65cbb239dba3a82087b4bc416f8675fc3f0fa3bf
SOURCE_COMMIT=14bcd5cc90fc11d572eeba5088fbb8203b4ce3e1
TEST_COMMIT=7259fd82f487ae306fd01998d97f2403928ed54f
```

## Real Edge runtime

```text
CDP_ENDPOINT_REACHABLE=PASS
PRODUCTION_EXTENSION_LOADED=PASS
EXTENSION_SERVICE_WORKER_FOUND=PASS
REAL_EXTENSION_RUNTIME_USED=PASS
BROWSER_PRODUCT=Microsoft Edge
BROWSER_VERSION=Edg/152.0.4191.66
CDP_PORT=9223
EXTENSION_ID=njdchompnmmngamijeleaeleadpoeolf
ORIGIN_HEADER_MANUALLY_SET=NO
```

The production unpacked artifact was loaded by the user in a disposable Edge profile. CDP found the production target `chrome-extension://<extension-id>/background.js`; the actual extension ID was read from `chrome.runtime.id`. Runtime evaluation returned safe metadata only.

## Production API and SQLite continuity

```text
EXTENSION_REGISTRATION_PRODUCTION_API=PASS
REGISTRATION_HTTP_STATUS=200
REAL_EXTENSION_ORIGIN_CONTRACT=PASS
SYNTHETIC_EXTENSION_TO_API_CONTRACT=PASS
COLLECTION_POST_HTTP_STATUS=201
SYNTHETIC_API_TO_SQLITE=PASS
PERSISTED_SOURCE_ORDER=PASS
END_TO_END_CONTRACT_CONTINUITY=PASS
```

The real Service Worker used the browser network stack without adding an Origin header. Registration and collection import were accepted by the production API. The API used a temporary synthetic SQLite state bound to `127.0.0.1`; no user database was used.

Safe runtime metadata:

```text
BOARD_ID=synthetic-runtime-board
REQUEST_ID=863a63a2-cc2d-4dd9-bca4-ed9691a67ab8
SNAPSHOT_ID=56178c02-52d3-4fdc-99a0-5c4af40c77e2
BOARD_REVISION=1
ITEM_COUNT=3
PERSISTED_ITEMS=0:synthetic-feed-a,1:synthetic-feed-b,2:synthetic-feed-c
```

Read-back through latest, snapshot detail, and items endpoints returned item_count 3 and the exact persisted order above. History contained one snapshot at revision 1.

## Idempotent replay

```text
RUNTIME_IDEMPOTENT_REPLAY=PASS
REPLAY_HTTP_STATUS=201
REPLAY_SAME_SNAPSHOT=PASS
REPLAY_SAME_BOARD_REVISION=PASS
HISTORY_AFTER_REPLAY_COUNT=1
```

The replay reused the same request ID, board ID, membership, xsec values, and source order. It did not create a second revision.

## Secret and scope gates

```text
INDEPENDENT_SECRET_SENTINELS=PASS
XSEC_TOKEN_URL_REDACTION=PASS
XSEC_TOKEN_LOG_REDACTION=PASS
XSEC_TOKEN_UI_REDACTION=PASS
CAPABILITY_TOKEN_URL_REDACTION=PASS
CAPABILITY_TOKEN_LOG_REDACTION=PASS
CAPABILITY_TOKEN_UI_REDACTION=PASS

EXTENSION_PRODUCTION_SOURCE_CHANGED=NO
PYTHON_PRODUCTION_SOURCE_CHANGED=NO
TEST_FILES_CHANGED=NO
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

## Fresh regression gates

```text
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

All runtime and regression tests used synthetic data. No test was skipped, removed, or weakened.
