# TC2B3-R1 Runtime Evidence

本文件只记录 synthetic runtime evidence；不包含真实 XHS 数据、Cookie、个人路径、Bearer credential 或任何 secret 值。

```text
PHASE=TC2B3-R1-RUNTIME-CLOSURE
REPAIR_BASE=66ae7f8fc66804c0ed075b127b5038c312dbce40
SOURCE_COMMIT=14bcd5cc90fc11d572eeba5088fbb8203b4ce3e1
TEST_COMMIT=7259fd82f487ae306fd01998d97f2403928ed54f
```

## Browser runtime probe

```text
BROWSER_PRODUCT=Microsoft Edge executable detected; no connected Edge runtime
BROWSER_VERSION=152.0.4191.66
BUILT_EXTENSION_ARTIFACT=apps/extension/dist
API_BIND_ADDRESS=NOT_STARTED_FOR_RUNTIME_PROOF
TEMPORARY_DATABASE=NOT_CREATED
REAL_EXTENSION_RUNTIME_USED=HOLD_NO_CONNECTED_BROWSER_RUNTIME
ORIGIN_HEADER_MANUALLY_SET=NO
```

The host has an Edge executable, but the available browser connection exposed no controllable Chromium-family runtime or loaded unpacked extension. Consequently no real Service Worker request was executed. No mock Origin, ordinary web-page fetch, or hand-written Origin header is counted as runtime evidence.

## Independent secret sentinels

```text
INDEPENDENT_SECRET_SENTINELS=PASS
XSEC_TOKEN_URL_REDACTION=PASS
XSEC_TOKEN_LOG_REDACTION=PASS
XSEC_TOKEN_UI_REDACTION=PASS
CAPABILITY_TOKEN_URL_REDACTION=PASS
CAPABILITY_TOKEN_LOG_REDACTION=PASS
CAPABILITY_TOKEN_UI_REDACTION=PASS
```

The test fixture uses separate synthetic xsec and capability sentinel constants and asserts they are unequal. HTTP construction sends the capability only in the Authorization header and xsec only in the in-memory JSON payload; fixed error/UI paths do not echo either value.

## Runtime closure status

```text
EXTENSION_REGISTRATION_PRODUCTION_API=HOLD_RUNTIME_NOT_EXECUTED
REAL_EXTENSION_ORIGIN_CONTRACT=HOLD_NO_BROWSER_RUNTIME
SYNTHETIC_EXTENSION_TO_API_CONTRACT=HOLD_RUNTIME_NOT_EXECUTED
SYNTHETIC_API_TO_SQLITE=HOLD_RUNTIME_NOT_EXECUTED
END_TO_END_CONTRACT_CONTINUITY=HOLD_RUNTIME_NOT_EXECUTED
PERSISTED_SOURCE_ORDER=HOLD_RUNTIME_NOT_EXECUTED
RUNTIME_IDEMPOTENT_REPLAY=HOLD_RUNTIME_NOT_EXECUTED
```

The production API and SQLite composition were not bypassed or replaced. Since a real Extension Service Worker could not be loaded, registration, authenticated collection POST, read-back, and replay remain unverified. No auth rule, manifest permission, or production behavior was changed to compensate.

## Fresh local gates

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

The fresh Extension run used the repository scripts `pnpm check`, `pnpm lint`, `pnpm test`, and `pnpm build`. The fresh Python run used the repository Ruff and full pytest gates. No tests were skipped, removed, or weakened.

## Scope audit from repair base

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

Only the independent-sentinel test repair and this runtime evidence document were added after the repair base. The previous `TC2B3_EXTENSION_EVIDENCE.md` remains unchanged and retains its historical HOLD facts.
