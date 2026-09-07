# TC2B2 Collection HTTP API Evidence

本文只记录 synthetic API facts，不包含真实 board、feed、token、收藏标题、用户路径或真实页面数据。

```text
PHASE=TC2B2-COLLECTION-HTTP-API
BASELINE_COMMIT=af89827e0de457114fda5726b51490765b5a6daf
```

## API boundary

```text
API_ROUTES=
POST /collections/{source_type}/{board_id}/imports
GET /collections/{source_type}/{board_id}/latest
GET /collections/{source_type}/{board_id}/snapshots
GET /collections/{source_type}/{board_id}/snapshots/{snapshot_id}
API_ROUTER_REGISTERED=PASS
PRODUCTION_DEPENDENCY_WIRING=PASS
IMPORT_EXT_AUTH=PASS
READ_LOCALHOST_ONLY=PASS
PUBLIC_ACCESS_CONTEXT_ENDPOINT=NONE
```

Import path identity comes only from `source_type` and `board_id`; the body accepts only `request_id` and sensitive item input. Public response DTOs are structurally separate and contain no `xsec_token`, `CollectionFeedAccessContext`, or token query field.

All collection endpoints reuse the existing Extension capability authentication, which requires a valid registered extension credential and a loopback client. Invalid requests return fixed, token-free error details.

## Synthetic API result

```text
IMPORT_EMPTY=PASS
IMPORT_1=PASS
IMPORT_50=PASS
IMPORT_500=PASS
IDEMPOTENT_REPLAY=PASS
IDEMPOTENCY_CONFLICT_409=PASS
REORDER_SEMANTICS=PASS
RESTART_PERSISTENCE=PASS
LATEST_READ=PASS
HISTORY_READ=PASS
SNAPSHOT_READ=PASS
ITEMS_ORDERED=PASS
```

## Token safety result

```text
TOKEN_SUCCESS_RESPONSE_REDACTION=PASS
TOKEN_READ_RESPONSE_REDACTION=PASS
TOKEN_VALIDATION_ERROR_REDACTION=PASS
TOKEN_EXCEPTION_LOG_REDACTION=PASS
```

The actual sentinel `synthetic-secret-token-never-leak` is exercised in API retry and validation paths; it does not occur in public responses or captured log messages.

## Test mapping

| Contract | pytest nodeid |
|---|---|
| import 0/1/50/500 and success response redaction | `tests/interfaces/test_collections_api.py::test_collection_import_supports_synthetic_sizes` |
| replay, 409 conflict, reorder and token-only retry | `tests/interfaces/test_collections_api.py::test_collection_api_replays_conflict_and_reorder_semantics` |
| latest/history/snapshot reads, restart-shaped persistence and ordered items | `tests/interfaces/test_collections_api.py::test_collection_api_reads_latest_history_and_ordered_snapshot` |
| extension authentication and loopback boundary | `tests/interfaces/test_collections_api.py::test_collection_api_requires_extension_and_only_accepts_loopback` |
| validation and log redaction | `tests/interfaces/test_collections_api.py::test_collection_api_redacts_validation_error_and_logs` |

## Scope

```text
EXTENSION_FILES_CHANGED=NO
MANIFEST_PERMISSION_CHANGE=NONE
GET_FEED_DETAIL_CALLED=NO
BROWSER_TASK_CREATED=NO
MEDIA_DOWNLOADED=NO
PUBLIC_ACCESS_CONTEXT_ENDPOINT=NONE
NEW_DEPENDENCIES=NO
```

## Formal quality gate

```text
RUFF_CHECK=PASS
RUFF_FORMAT=PASS
PYTEST=PASS
PYTEST_TOTAL=653
PYTEST_FAILED=0
COVERAGE=91.30%
COVERAGE_GATE=PASS (>=85%)
```
