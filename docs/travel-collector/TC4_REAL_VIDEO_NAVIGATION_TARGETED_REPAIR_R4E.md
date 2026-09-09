# TC4 Real Video Navigation Targeted Repair R4E

## Scope

- Phase: `TC4-REAL-VIDEO-NAVIGATION-TARGETED-REPAIR-R4E`
- Starting head: `74df9a4acfe53286868a1cc90e79c6f324783411`
- Repair class: `B_PENDING_URL_AWARE_BOUNDED_WAIT`
- Base wait: `5000 ms`
- Maximum wait: `10000 ms`
- Poll interval: `250 ms` (unchanged)

The repair is limited to the Extension detail-navigation wait boundary. At the
old five-second boundary, the runtime grants additional bounded wait only when
the target tab still exists, remains `loading`, has a `pendingUrl`, and that
pending URL matches the expected XHS detail identity. `pendingUrl` is used only
for in-flight classification; it cannot produce readiness.

Readiness remains fail-closed and unchanged:

```text
tab.status == complete
AND committed tab.url exists
AND isSupportedDetailPageForFeed(committed tab.url, feed_id)
```

The target tab is still removed by the existing `finally` cleanup. No API,
content script, parser, downloader, persistence, telemetry schema, or R4D
probe code was changed.

## Test-first evidence

- R4E RED confirmed on the R4D head: expected `pendingUrl` still loading past
  the old five-second boundary failed after 20 polls.
- `R4E_TEST_IMPLEMENTATION_COMMIT=d1109749f37cf9e03950d9fb0e7fcd8ca6f75270`
- `R4E_SOURCE_COMMIT=ffbac6c1f1777fa8cb03f0acc9e3bfb376bba19d`
- `R4E_TEST_FINALIZATION_COMMIT=82a02044d969928724b9d02af00386914dddcb1c`
- `R4E_EVIDENCE_COMMIT` is this document's commit.

The targeted matrix covers fast success, expected pending navigation through
the old boundary, commit during grace, pending navigation timeout, missing or
wrong pending URL, pending URL not being ready, wrong committed host, wrong
feed identity, and removed target tab.

## Quality gates

- Extension typecheck: PASS
- Extension lint: PASS
- Extension tests: PASS — 420 tests in 63 files
- Extension coverage: PASS — 90.03% statements, 85.32% branches, 92.13% functions, 92.99% lines
- Extension build: PASS
- R4E targeted tests: PASS — 8 tests
- Python/API source diff: EMPTY
- R4D security and fail-closed evidence: unchanged and PASS

No pending URL, query, token, cookie, authorization material, raw media URL,
or user data is persisted or logged. No real canary has been run for R4E.
Chrome must load the newly built Extension before the single authorized R4E
canary is considered.
