# TC4-MVP-B-R6 Video Artifact Handoff Evidence

```text
PHASE=TC4-MVP-B-R6-VIDEO-ARTIFACT-HANDOFF-CLOSURE
BASELINE_COMMIT=779753f7571bfa555eb92f2cff5c27d489773cb6
SOURCE_R5_COMMIT=bef64cbe13bd5b7fb031fe2c077de99bb84aac6a
TEST_R5_COMMIT=0d5046d74f8398cf97c1989691d7917c2cee7e96
EVIDENCE_R5_COMMIT=779753f7571bfa555eb92f2cff5c27d489773cb6
SOURCE_R6_COMMIT=84acde7
TEST_R6_COMMIT=b296006
```

## Scope and ownership

```text
TC4_OVERALL_SCOPE=collection image + video media acquisition
TC4_MVP_B_SCOPE=video media acquisition subphase only
TC4_MVP_B_VIDEO_SCOPE_DEFINED=PASS
TC4_OVERALL_GENERIC_MEDIA_PENDING=YES
TC4_OVERALL_WORKDETAIL_MAPPING=DEFERRED
TC4_OVERALL_IMAGE_MEDIA_ACQUISITION=DEFERRED
TC4_OVERALL_MULTI_IMAGE_MEDIA_ACQUISITION=DEFERRED
```

TC4-MVP-B owns the video acquisition and local artifact handoff proven below. Generic
`WorkDetail` mapping and image/multi-image acquisition remain TC4-overall work and are
not represented as completed by this evidence.

## Production and synthetic proof

The production composition path retains the TC4/TC5 runtime boundary: TC4 does not
require PyAV, FFmpeg, Whisper/STT, OCR, keyframes, or export. The synthetic tests use
an in-process gateway and never send an external XHS request.

| Requirement | Evidence | Result |
| --- | --- | --- |
| Default source retention | `VideoProcessRequest.keep_source`, `VideoProcessingService.process_snapshot` | PASS |
| Reopen artifact handoff | `tests/tc4/test_video_handoff_r6.py::test_video_artifact_handoff_survives_repository_reopen` | PASS |
| Explicit cleanup | `tests/tc4/test_video_processing_r1.py::test_artifact_uses_safe_relative_path_and_cleanup` | PASS |
| Identity preservation | `tests/tc4/test_video_processing_lifecycle_r3.py::test_service_restart_recovers_running_and_fences_stale_worker`, `test_video_failures_are_explicit_and_non_success[identity]` | PASS |
| Retry/resume and atomic finalize | `tests/tc4/test_video_processing_r1.py::test_shared_retry_is_bounded_and_cleans_tc4_marker` | PASS |
| Runtime isolation | `tests/tc4/test_video_processing_lifecycle_r3.py::test_service_restart_recovers_running_and_fences_stale_worker` | PASS |

The handoff test verifies exact bytes, SHA-256, size, safe relative path, physical file
existence after repository reopen, one media-acquirer call, and absence of the synthetic
token and transient URL from the SQLite bytes. No real media or user data is included.

```text
TC4_TC5_CONTROL_FLOW_DECOUPLED=PASS
TC4_TC5_ARTIFACT_HANDOFF=PASS
TC4_DEFAULT_RETAINS_SOURCE=PASS
TC4_SUCCESS_ARTIFACT_AVAILABLE=PASS
TC4_SUCCESS_RELATIVE_PATH_PRESENT=PASS
TC4_SUCCESS_PHYSICAL_FILE_EXISTS=PASS
DEFAULT_RETENTION=PASS
EXPLICIT_CLEANUP_MODE=PASS
RETENTION_POLICY_UNAMBIGUOUS=PASS
ARTIFACT_METADATA_RESTART_PERSISTENCE=PASS
ARTIFACT_RELATIVE_PATH_SAFE=PASS
ARTIFACT_ABSOLUTE_PATH_NOT_PERSISTED=PASS
TC5_HANDOFF_REQUIRES_XHS_REACCESS=NO
TC5_HANDOFF_REQUIRES_TOKEN=NO
TC5_HANDOFF_REQUIRES_SIGNED_URL=NO
MEDIA_ACQUIRER_CALL_COUNT_DOES_NOT_INCREASE=PASS
VIDEO_ACQUISITION_SUCCESS_CONTRACT=PASS
FEED_IDENTITY_PRESERVED=PASS
MEDIA_KIND_VIDEO_PRESERVED=PASS
MEDIA_INDEX_PRESERVED=PASS
MEDIA_IDENTITY_MISMATCH_FAIL_CLOSED=PASS
SHARED_STREAMING_DOWNLOADER=PASS
SECOND_GENERIC_DOWNLOADER=NO
RANGE_RESUME=PASS
BOUNDED_RETRY=PASS
STREAM_EXCEPTION_CONTRACT=PASS
URL_MARKER_CLEANUP=PASS
PARTIAL_FILE_POLICY=PASS
ATOMIC_FINALIZE=PASS
ARTIFACT_SHA256_EXACT=PASS
ARTIFACT_SIZE_EXACT=PASS
TC4_RAW_DB_SECRET_REDACTION=PASS
TC4_PUBLIC_API_SECRET_REDACTION=PASS
TC4_ARTIFACT_METADATA_SECRET_REDACTION=PASS
TRANSIENT_LOCATOR_NOT_PERSISTED=PASS
```

## Fresh verification

```text
RUFF_CHECK=PASS
RUFF_FORMAT=PASS
PYTEST=PASS
PYTEST_TOTAL=694
PYTEST_FAILED=0
COVERAGE=90.50%
COVERAGE_GATE=PASS
REMOTE_CI_STATUS=NOT_CONFIGURED
```

The complete fresh gate was run after the R6 source and test changes. No coverage
threshold or test was lowered.

## Safety and deferred work

```text
WHISPER_PREWORK_PRESERVED=YES
WHISPER_RUNTIME_EXECUTED=NO
OCR_RUNTIME_EXECUTED=NO
PYAV_RUNTIME_EXECUTED_FOR_TC5=NO
REAL_XHS_MEDIA_DOWNLOADED=NO
EXTERNAL_XHS_MEDIA_REQUEST_SENT=NO
REAL_USER_DATA_COMMITTED=NO
EXTENSION_FILES_CHANGED=NO
DEPENDENCY_LOCK_CHANGED=NO
GET_FEED_DETAIL_CALLED=NO
BROWSER_TASK_CREATED=NO
MEDIA_DOWNLOADED=NO
NEW_DEPENDENCIES=NO
TC4_MVP_B_WORK_PERFORMED=YES
TC4_REAL_MEDIA_CANARY_WORK_STARTED=NO
TC5_WORK_STARTED=NO
TC6_WORK_STARTED=NO
```

`TC4_MVP_B_VIDEO_ACQUISITION_PASS_CANDIDATE=YES` applies only to the synthetic,
video-only R6 scope. `TC4_OVERALL_PASS_CANDIDATE=NO` because the deferred generic and
image contracts are not complete. Real-video canary remains a separately authorized
next phase.

