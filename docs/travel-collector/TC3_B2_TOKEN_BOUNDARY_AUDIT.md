# TC3-B2 Detail Orchestration Token Boundary Audit

PHASE=TC3-B2-A
BASELINE_COMMIT=2cd3fb74623d8afe1835af320d087dcff5f0f937
AUDIT_SCOPE=STATIC_CODE_AUDIT_ONLY
XSEC_SENTINEL=synthetic-tc3-audit-xsec

## Current detail chain

The exact current call chain is:

```text
ReadCapabilityRuntime.get_feed_detail
  -> CapabilityRouter.execute_read
  -> HttpReadProvider.get_feed_detail
     or BrowserReadProvider.get_feed_detail
  -> _BrowserReadExecution.execute
  -> BrowserTaskService.submit
  -> SqliteBrowserTaskRepository.save
  -> browser_task_parameters
  -> browser_task.payload
```

The browser execution return path is:

```text
browser_task.payload
  -> BrowserExecutionService.claim
  -> /browser/extension/tasks/claim
  -> extension browser-task-runner
  -> taskTargetUrl
  -> /browser/extension/tasks/{task_id}/result
  -> BrowserExecutionService.update
  -> SqliteBrowserTaskRepository.save_if_status
```

DETAIL_RUNTIME_ENTRY=apps/api/src/xhs_api/capability_runtime.py:ReadCapabilityRuntime.get_feed_detail
HTTP_DETAIL_PATH=apps/api/src/xhs_api/capability_runtime.py -> xhs_adapters/http_read_provider.py:HttpReadProvider.get_feed_detail
BROWSER_DETAIL_PATH=apps/api/src/xhs_core/application/browser_read_provider.py:BrowserReadProvider.get_feed_detail -> _BrowserReadExecution.execute
BROWSER_TASK_SUBMIT_PATH=xhs_core/application/browser_tasks.py:BrowserTaskService.submit
BROWSER_TASK_STORAGE_PATH=xhs_adapters/sqlite/browser_tasks.py:SqliteBrowserTaskRepository.save -> browser_task_storage.py:browser_task_parameters -> browser_task.payload

## Browser task token persistence

BrowserReadProvider constructs a `GET_FEED_DETAIL` payload containing `feed_id`,
`xsec_token`, and the detail limits. `BrowserTaskService.submit` validates and
freezes that payload. `browser_task_parameters` calls
`sanitize_stored_browser_task`, but the sanitizer only changes failed/review
message and result diagnostics; it does not remove input payload fields.
Therefore the sentinel would be serialized into `browser_task.payload`.

GET_FEED_DETAIL_BROWSER_PAYLOAD_CONTAINS_XSEC=YES
BROWSER_TASK_PAYLOAD_PERSISTED=YES
BROWSER_TASK_SQLITE_CONTAINS_XSEC=YES
BROWSER_TASK_TABLE=browser_task
BROWSER_TASK_COLUMN=payload
BROWSER_TASK_SERIALIZATION_PATH=BrowserTask.model_dump_json via browser_task_parameters
BROWSER_TASK_TOKEN_LIFETIME=queued through terminal record retention

TOKEN_SURVIVES_TASK_SUCCESS=YES
TOKEN_SURVIVES_TASK_FAILURE=YES
TOKEN_SURVIVES_RESTART=YES
TOKEN_CLEANUP_PRESENT=NO

The same payload is retained through queued, claimed, running, succeeded,
failed, and needs_review transitions. Retry requeues the same task payload.
Lease expiry either requeues a read task or moves a possibly-effectful task to
needs_review, but neither branch scrubs the payload. Restart reloads the same
JSON payload. No terminal or lease cleanup removes `xsec_token`.

## Exposure analysis

The token is in transit to the extension in the `BrowserTaskClaim.task` object,
and the extension uses it to construct the detail navigation URL. The existing
management task list/get endpoints return the `BrowserTask` model, including
payload, and the extension result/status endpoints return the updated task.
These routes are access-controlled, but they are still authenticated API
exposures rather than non-exposure.

BROWSER_TASK_XSEC_AT_REST=YES
BROWSER_TASK_XSEC_PUBLIC_API_EXPOSURE=YES_AUTHENTICATED_TASK_AND_CLAIM_RESPONSES
BROWSER_TASK_XSEC_LOG_EXPOSURE=NO_BY_STATIC_AUDIT
BROWSER_TASK_XSEC_UI_EXPOSURE=YES_BROWSER_NAVIGATION_URL

The browser task logger records sanitized status messages and task IDs, not the
payload. The extension does not render the token as application UI, but the
detail URL containing it is present in the browser navigation context.

## HTTP path

`HttpReadProvider.get_feed_detail` validates the token, puts it in the encoded
HTTPS detail URL, and passes it to `FeedDetailStateParser`. The provider states
that it does not persist requests or responses and does not log tokens.
However, `FeedDetailResult` currently includes `xsec_token`, and the unified
`/xhs/feeds/detail` response returns that result unchanged in `data`.

HTTP_PATH_PERSISTS_XSEC=NO
HTTP_PATH_LOGS_XSEC=NO_BY_STATIC_AUDIT
HTTP_PATH_RETURNS_XSEC=YES
HTTP_PATH_PUBLIC_API_EXPOSURE=YES_AUTHENTICATED_MANAGEMENT_RESPONSE

TC3 must call `CollectionFeedDetail.from_feed_detail()` before persistence;
that B1 model excludes `xsec_token` and `comments_cursor`.

## Route strategy

The current `RouteStrategy` enum and router map contain all four strategies:

ROUTE_STRATEGIES=http_only, browser_only, http_first, browser_first
HTTP_ONLY_AVAILABLE=YES
BROWSER_ONLY_AVAILABLE=YES
HTTP_THEN_BROWSER_AVAILABLE=YES
BROWSER_THEN_HTTP_AVAILABLE=YES
TC3_RUNTIME_CAN_FALLBACK_TO_BROWSER=YES_IF_ROUTE_STRATEGY_IS_HTTP_FIRST_AND_HTTP_FAILURE_IS_SAFE_TO_FALLBACK

The runtime passes the same token to both provider closures. The selected
strategy therefore controls whether a browser task can be created; TC3 cannot
assume HTTP-only unless it explicitly chooses and justifies that policy.

## Extension detail transport

`apps/extension/src/browser-task-runner.ts:taskTargetUrl` reads `feed_id` and
`xsec_token` from the claimed task and constructs:

```text
https://www.xiaohongshu.com/explore/{encoded_feed_id}?xsec_token={encoded_token}&xsec_source=pc_feed
```

EXTENSION_DETAIL_NEEDS_XSEC=YES
EXTENSION_XSEC_USED_IN_NAVIGATION_URL=YES

This is in-browser transport/use and is separate from the additional database
persistence issue. TC3 does not need to remove the token from the navigation
request itself.

## Request ID and refresh conflict

BrowserTaskService compares an existing request with the same `request_id` by
kind, normalized payload, and target driver. The normalized payload includes
the raw `xsec_token`.

BROWSER_TASK_REQUEST_ID_PAYLOAD_SENSITIVE=YES
TOKEN_REFRESH_CAN_CAUSE_REQUEST_ID_CONFLICT=YES

The safe proposal is to derive the request ID from the immutable enrichment
identity `(snapshot_id, feed_id, enrichment_version)` and submit each identity
at most once. A refreshed token belongs to a newly imported snapshot and thus a
new enrichment identity. If a token changes within the same snapshot, do not
reuse the old task request ID with a different payload; fail closed and require
a new snapshot/reimport. Never put the raw token in a request ID. A raw-token
hash would still create an unnecessary sensitive-derived identifier and is not
needed by the snapshot identity model.

OLD_NEEDS_REIMPORT_REOPENED=NO
NEW_SNAPSHOT_USES_REFRESHED_ACCESS_CONTEXT=YES

## Token-at-rest policy interpretation

Frozen B1 facts are that `collection_feed_enrichment` and `CollectionFeedDetail`
do not store the token, while TC2 retains the latest collection access context.
The generic BrowserTask implementation is a separate, currently token-bearing
storage path. Its existing authenticated access control does not make the
token non-persistent and does not satisfy a policy requiring no second
token-at-rest location.

TOKEN_AT_REST_POLICY_INTERPRETATION=TC3 MUST NOT ADD OR RELY ON THE EXISTING PLAINTEXT BROWSER_TASK PAYLOAD AS A SECOND TOKEN-AT-REST STORE

## Options

OPTION_A_HTTP_ONLY=Avoids BrowserTask token-at-rest, but bypasses the existing router strategy and browser fallback; HTTP may be unavailable or incomplete for detail and can reduce real success rate. Not recommended without a measured HTTP-completeness proof.

OPTION_B_SECRET_HANDOFF=Keep BrowserTask metadata persistent while resolving the token through a short-lived in-memory claim-time handoff. Strongest fit for the boundary, but requires explicit ownership, expiry, single-consumer behavior, and process/restart failure semantics; an in-memory-only handoff cannot survive process restart and needs fail-closed recovery.

OPTION_C_TERMINAL_SCRUB=Temporarily persists the token and clears it at terminal state. This still creates a second token-at-rest location, and crash-before-scrub, restart, lease expiry, failure, and needs_review leave difficult recovery windows. It does not meet a strict no-second-at-rest policy.

OPTION_D=No existing secret store, encrypted payload, or ephemeral capability store suitable for this detail handoff was found. Reusing the existing collection access context as a new secret subsystem would need a separately authorized design and must not expose it through the public task API.

RECOMMENDED_B2_TOKEN_STRATEGY=B
WHY=It preserves the existing capability routing semantics while separating persistent task metadata from the short-lived detail token; HTTP-only and terminal-scrub alternatives either reduce capability behavior or violate the at-rest boundary.
SECURITY_PROPERTIES=No raw detail token in browser_task payload, task list/get response, claim metadata, or task logs; token is bounded to claim-time execution and is cleared on completion or failure.
RESTART_PROPERTIES=An in-memory handoff intentionally does not survive restart; an orphaned task must fail closed and require a new snapshot/reimport rather than recover a token from persistent task data.
IDEMPOTENCY_PROPERTIES=Stable request ID uses enrichment identity only; token refresh cannot be encoded into or leaked by the request ID, and same-identity payload changes fail closed.
FILES_LIKELY_CHANGED=TC3-B2 application orchestration, a narrowly scoped secret handoff/claim contract, synthetic tests, and evidence; no manifest change and no public access-context endpoint.

## B2 success-path proposal (design only)

B2_SUCCESS_PATH_PROPOSAL=snapshot_id -> list_snapshot_items(source_order) -> ensure_enrichment(key) -> skip terminal -> get_feed_access_context(feed_id) -> missing context marks current enrichment needs_reimport without reopening terminal state -> CAS pending/failed_retryable to running -> register claim-time detail token handoff -> submit bounded GET_FEED_DETAIL task or select HTTP provider under the approved strategy -> validate returned feed_id -> CollectionFeedDetail.from_feed_detail -> save_detail -> succeeded; never persist raw token in BrowserTask metadata
ORCHESTRATION_MAX_IN_FLIGHT=3

The B2 implementation must leave complex retry policy, lease-expiry
reconciliation, risk classification, deleted-feed classification, account
mismatch classification, and partial-batch recovery to B3. It must not create
500 concurrent tasks; the current extension poll loop processes at most four
tasks sequentially per poll, and no stricter browser-worker concurrency setting
was found in the frozen code.

API_ROUTE_ADDED=NO

## Scope

PRODUCTION_SOURCE_CHANGED=NO
TEST_FILES_CHANGED=NO
DB_SCHEMA_CHANGED=NO
EXTENSION_FILES_CHANGED=NO
MANIFEST_PERMISSION_CHANGE=NONE
NEW_DEPENDENCIES=NO
GET_FEED_DETAIL_CALLED=NO
REAL_XHS_REQUEST=NO
REAL_XSEC_TOKEN_USED=NO
MEDIA_DOWNLOADED=NO
VIDEO_PROCESSING_STARTED=NO
TC3_B2_IMPLEMENTATION_STARTED=NO
TC4_WORK_STARTED=NO
