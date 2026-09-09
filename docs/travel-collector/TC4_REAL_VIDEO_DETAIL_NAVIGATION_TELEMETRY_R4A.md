# TC4 Real Video Detail Navigation Telemetry R4A

## Scope

R4A adds bounded diagnostics around the existing detail-navigation wait. It does
not change the navigation predicate, polling interval, timeout, media locator
selection, or successful locator persistence.

The producer is the real `executeInNewTab` path in
`apps/extension/src/browser-task-runner.ts`, which passes a creation observation
to `waitForMediaDetailPage` in
`apps/extension/src/browser-media-task-runtime.ts`.

## Approved bounded schema

Only these navigation facts may cross the extension-to-application boundary:

- `target_tab_exists`: boolean
- `last_tab_status`: `loading`, `complete`, `unknown`, or `missing`
- `last_route_class`: bounded route class without a real identifier
- `url_host_is_xhs`: boolean
- `expected_route_matched`: boolean
- `elapsed_ms`: integer from 0 through 60000
- `tab_removed`: boolean

The route classes are fixed enums: `/blank`, `/explore/<feed_id>`,
`/discovery/item/<feed_id>`, `/board/<board_id>`, `/other-xhs`, `/non-xhs`, and
`/unknown`.

Creation observation fields (`created_tab_id`, `create_returned`, and
`chrome_runtime_last_error_present`) remain internal diagnostic context and are
not serialized in the task result.

## Fail-closed redaction

`packages/xhs-core/src/xhs_core/domain/browser_diagnostics.py` retains only the
approved stage, failure code, and bounded fields above. Unknown fields and
invalid enum, boolean, or elapsed values are dropped. Raw URLs, query strings,
feed identifiers, signed media URLs, tokens, cookies, authorization values, raw
errors, and DOM content are not persisted.

## Verification

- `R4A_DIAGNOSTIC_RED=CONFIRMED`: targeted tests failed before the producer and
  sanitizer implementation.
- Extension targeted telemetry tests: PASS (5/5).
- Extension full tests: PASS (415/415); coverage 89.92% statements and 85.18%
  branches.
- Python targeted diagnostics tests: PASS (9/9).
- Python full tests: PASS after a transient retry of an unrelated async claim
  timing test (703 passed on the full run before the retry).
- Python Ruff check: PASS.
- Changed-file Ruff format check: PASS.
- Architecture/file-size tests: PASS (5/5).
- Extension typecheck, lint, and build: PASS.

## Commit provenance

- Test implementation: `02c7b2f93a718e110674db8139b2939f63fecacd`
- Test finalization: `d67c58de71b434705927f918e7e12cde8f59e70c`
- Source implementation: `217399656ae8e049cebb217d9b4c73eeec97a3e2`

No real-video canary output, credentials, secret material, or media artifact is
included in this evidence.
