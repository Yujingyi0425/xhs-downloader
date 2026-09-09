# TC4 Real Video Detail Navigation Telemetry Propagation R4B

## Entry and scope

- R4A candidate entered at `2879484902fe8cf5625bef2c595b4b295a3fc926`.
- The last Human-Gated baseline remains
  `8586c17bbdae411160d1c7828dd328e458711a51`.
- No detail-navigation, readiness, URL predicate, content-script, parser, or
  downloader behavior was changed in R4B.

## Read-only propagation trace

The approved fields use one flat failure-result object throughout the current
source chain:

| Boundary | Production symbol/path | Current source trace |
| --- | --- | --- |
| A | `waitForMediaDetailPage` / `tabTelemetry` | present |
| B | `mediaFailureResponse` | present and spread into `result` |
| C | `executeBrowserTaskClaim` → `reportBrowserTaskResult` | result passed through |
| D | `BrowserTaskResultRequest.result` | accepts `dict[str, JsonValue]` |
| E | `complete_task` → `BrowserExecutionService.update` | result passed through |
| F | `_normalize_terminal_result` → `sanitize_browser_page_diagnostics` | approved fields retained |
| G | `normalized_result` → `persisted_result` | no failure projection |
| H | `BrowserTask.model_dump_json()` | full safe snapshot serialized |
| I | `save_browser_task_if_snapshot` | snapshot written to SQLite |
| J | `parse_browser_task` / `sanitize_stored_browser_task` | safe snapshot read back |
| K | `/browser/tasks` readback | result is caller-visible |

R2 fields and R4A fields share the same flat container, sanitizer call, and
persistence path. The producer callsite passes navigation telemetry to the
failure response builder.

## Runtime loss boundary

The R4A canary readback contained only the R2 failure stage/code fields. The
live API process had started before the R4A sanitizer source was updated, while
the current source and built extension artifact already contained the R4A
fields. This identifies the observed first runtime loss as the stale API
sanitizer process, classified as `OTHER_EXACT_SINGLE_BOUNDARY`:

`API_RUNTIME_NOT_RELOADED_AFTER_R4A`

The minimal repair was one restart of the existing repository API process. No
production source file was changed.

## Regression and security

`tests/interfaces/test_browser_diagnostics_api.py` now exercises the real HTTP
result submission, application normalization, SQLite persistence, and task
readback contract. It verifies all approved navigation fields survive while
unknown fields, tokens, and full URLs are dropped.

- R4B propagation regression: PASS.
- Targeted diagnostics/API tests: PASS.
- Full Python suite: 705 passed.
- Coverage: 90.62%, gate PASS.
- Ruff and architecture/file-size gates: PASS.
- Changed-file format: PASS.
- The known unrelated full-repository format exception remains unchanged.

No credentials, real identifiers, signed URLs, raw errors, user data, or media
artifacts are included in this evidence.
