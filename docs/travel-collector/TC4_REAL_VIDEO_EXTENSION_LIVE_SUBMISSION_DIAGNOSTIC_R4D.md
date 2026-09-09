# TC4 Real Video Extension Live Submission Diagnostic R4D

## Scope

- Phase: `TC4-REAL-VIDEO-EXTENSION-LIVE-SUBMISSION-DIAGNOSTIC-R4D`
- Mode: `TWO-SIDED-PRESENCE-ONLY-RUNTIME-PROBE`
- Start head: `ff2459d449f52b16c01645d79449ddbe11d35051`
- Baseline: `8586c17bbdae411160d1c7828dd328e458711a51`
- Physical canaries before R4D: `2`
- Authorized R4D canaries: `1` maximum; no retry

This phase adds diagnostic visibility at the existing Extension task-result
submission boundary and the API task-result HTTP ingress boundary. It does not
change navigation, task selection, media acquisition, persistence policy, or
the formal browser-result schema.

## Presence-only design

For failed and `needs_review` task results, the Extension adds a transient
`r4d_submission_probe` marker and boolean `r4d_has_*` keys. Each boolean only
states whether one of the seven R4A telemetry keys was present in the result;
the telemetry values themselves are not copied into the probe keys. Successful
results retain their existing request contract.

At API ingress, the diagnostic observer records only the same presence
booleans plus the safe internal task id. The existing result sanitizer remains
unchanged and unknown `r4d_*` fields are not persisted or exposed in task
readback.

No cookies, authorization material, xsec tokens, raw URLs, raw request bodies,
or media/user data are written by this diagnostic.

## Provenance

- `R4D_TEST_COMMIT=bd19f98` — direct Extension/API presence and fail-closed tests
- `R4D_DIAGNOSTIC_SOURCE_COMMIT=90295b2` — Extension submission probe and API ingress observer
- `R4D_EVIDENCE_COMMIT` — this document

## Quality gates

- Extension check/typecheck: PASS
- Extension lint: PASS
- Extension tests: PASS — 417 tests in 63 files
- Extension coverage: PASS — 89.93% statements, 85.16% branches, 92.12% functions, 92.97% lines
- Extension build: PASS
- Python ruff check: PASS
- R4D-changed Python format check: PASS
- Full Python tests: PASS — 706 passed
- Full Python coverage: PASS — 90.63%
- Unknown diagnostic fields fail closed at persistence: PASS

## Runtime status before canary

The API must be restarted at the final R4D source head. The rebuilt project
Extension must also be manually reloaded in Chrome before a canary is eligible.
Until both runtime components are confirmed current, no R4D canary is run and
no live-submission conclusion is claimed.

This document intentionally records instrumentation readiness only. The final
R4D evidence must append the single canary task id, API ingress presence-only
observations, persisted telemetry observations, first-loss boundary, and root
cause classification without recording secret or raw media values.
