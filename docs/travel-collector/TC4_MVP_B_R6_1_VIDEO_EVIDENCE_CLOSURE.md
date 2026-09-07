# TC4-MVP-B-R6.1 Video Evidence Closure

```text
PHASE=TC4-MVP-B-R6.1-VIDEO-EVIDENCE-CLOSURE
BASELINE_COMMIT=b703da1a48c9d50db0eb10d0cae79e2fedf89220
R6_1_BASELINE_COMMIT=b703da1a48c9d50db0eb10d0cae79e2fedf89220
R6_1_TEST_IMPLEMENTATION_COMMIT=25d8d670e9729696789c0b738326986d5efcf4df
R6_1_TEST_FINALIZATION_COMMIT=476f653e51a5fc26c872b3685ca2d5a821e22e5a
R6_1_FINAL_TEST_TREE_COMMIT=476f653e51a5fc26c872b3685ca2d5a821e22e5a
R6_1_ORIGINAL_EVIDENCE_COMMIT=72ff445f5e960d6fc433110c69d5af325e2425b6
R6_1_TEST_PROVENANCE_CORRECTED=PASS
PRODUCTION_SOURCE_CHANGED=NO
```

## Evidence corrections

R6_EXPLICIT_CLEANUP_EVIDENCE_OVERCLAIM=CORRECTED

R6 previously had direct artifact-store cleanup coverage, but not a dedicated
service-level proof for `keep_source=False`. R6.1 adds that proof. R6 source
behavior was not invalidated; the issue was evidence precision and a missing
service-level test.

R6_MEDIA_INDEX_PRESERVATION_OVERCLAIM=CORRECTED

The TC4-MVP-B video artifact identity is `snapshot_id + feed_id`. The current
video subphase does not require long-term persistence of the video resource
index, so the evidence records this as not required rather than claiming index
persistence.

## Dedicated test matrix

| Behavior | Exact test nodeid | Result |
| --- | --- | --- |
| default source retention | `tests/tc4/test_video_boundaries_r4.py::test_video_processing_defaults_to_source_retention` | PASS |
| repository-reopen handoff | `tests/tc4/test_video_handoff_r6.py::test_video_artifact_handoff_survives_repository_reopen` | PASS |
| explicit `keep_source=False` service cleanup | `tests/tc4/test_video_handoff_r6.py::test_video_service_keep_source_false_cleans_and_persists_metadata` | PASS |
| mixed image/video locator selects video | `tests/tc4/test_video_handoff_r6.py::test_video_artifact_store_selects_video_resource_by_kind` | PASS |
| no-video locator fail-closed | `tests/tc4/test_video_locator_r6.py::test_video_artifact_store_without_video_fails_closed` | PASS |
| feed identity mismatch | `tests/tc4/test_video_processing_lifecycle_r3.py::test_video_failures_are_explicit_and_non_success[identity]` | PASS |
| secret redaction | `tests/tc4/test_video_handoff_r6.py::test_video_artifact_handoff_survives_repository_reopen` | PASS |
| retry/resume regression | `tests/tc4/test_video_processing_r1.py::test_shared_retry_is_bounded_and_cleans_tc4_marker` | PASS |
| TC5 runtime isolation | `tests/tc4/test_video_processing_lifecycle_r3.py::test_service_restart_recovers_running_and_fences_stale_worker` | PASS |

The explicit-cleanup service test proves success and acquisition success, physical
source removal, `local_video_available=False`, `relative_path=None`, exact SHA-256
and size retention, repository-reopen persistence, and that STT/OCR are not called.
The mixed locator test proves the video URL is selected over the image URL, exact
video bytes/hash/size are finalized, and a locator without a video raises
`LookupError` rather than succeeding.

```text
EXPLICIT_CLEANUP_SERVICE_PATH=PASS
EXPLICIT_CLEANUP_PHYSICAL_FILE_REMOVED=PASS
EXPLICIT_CLEANUP_PERSISTED_STATE=PASS
EXPLICIT_CLEANUP_RESTART_PERSISTENCE=PASS
EXPLICIT_CLEANUP_MODE=PASS

VIDEO_LOCATOR_INPUT_INDEX=2
VIDEO_MEDIA_SELECTION_BY_KIND=PASS
MEDIA_KIND_VIDEO_PRESERVED=PASS
NON_VIDEO_RESOURCE_NOT_SELECTED=PASS
NO_VIDEO_RESOURCE_FAIL_CLOSED=PASS
MEDIA_INDEX_PERSISTENCE=NOT_REQUIRED_FOR_TC4_MVP_B

TC4_DEFAULT_RETAINS_SOURCE=PASS
TC4_TC5_ARTIFACT_HANDOFF=PASS
FEED_IDENTITY_PRESERVED=PASS
MEDIA_IDENTITY_MISMATCH_FAIL_CLOSED=PASS
ARTIFACT_METADATA_RESTART_PERSISTENCE=PASS
ARTIFACT_SHA256_EXACT=PASS
ARTIFACT_SIZE_EXACT=PASS
TC5_HANDOFF_REQUIRES_XHS_REACCESS=NO
TC5_HANDOFF_REQUIRES_TOKEN=NO
TC5_HANDOFF_REQUIRES_SIGNED_URL=NO
TC4_RAW_DB_SECRET_REDACTION=PASS
TC4_PUBLIC_API_SECRET_REDACTION=PASS
TC4_ARTIFACT_METADATA_SECRET_REDACTION=PASS
TRANSIENT_LOCATOR_NOT_PERSISTED=PASS
SHARED_STREAMING_DOWNLOADER=PASS
RANGE_RESUME=PASS
BOUNDED_RETRY=PASS
ATOMIC_FINALIZE=PASS
```

## Fresh gates and scope

```text
RUFF_CHECK=PASS
RUFF_FORMAT=PASS
PYTEST=PASS
PYTEST_TOTAL=697
PYTEST_FAILED=0
COVERAGE=90.54%
COVERAGE_GATE=PASS
ARCHITECTURE_FILE_SIZE_GATE=PASS
REMOTE_CI_STATUS=NOT_CONFIGURED
R6_1E_FUNCTIONAL_TREE_UNCHANGED=PASS
R6_1_FRESH_REGRESSION_INHERITED=YES

PRODUCTION_SOURCE_CHANGED=NO
WHISPER_RUNTIME_EXECUTED=NO
OCR_RUNTIME_EXECUTED=NO
REAL_XHS_MEDIA_DOWNLOADED=NO
EXTERNAL_XHS_MEDIA_REQUEST_SENT=NO
REAL_USER_DATA_COMMITTED=NO
TC4_REAL_VIDEO_CANARY_STARTED=NO
TC5_WORK_STARTED=NO
TC6_WORK_STARTED=NO
TC4_OVERALL_WORKDETAIL_MAPPING=DEFERRED
TC4_OVERALL_IMAGE_MEDIA_ACQUISITION=DEFERRED
TC4_OVERALL_MULTI_IMAGE_MEDIA_ACQUISITION=DEFERRED
TC4_OVERALL_PASS_CANDIDATE=NO
```

No production source, dependency, manifest, runtime, or test assertion was changed
in R6.1E. No real XHS request or media download was made.
