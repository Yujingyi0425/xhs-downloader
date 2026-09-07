# TC4-MVP-B-R5 Contract Reconciliation Evidence

```text
PHASE=TC4-MVP-B-R5-CONTRACT-AND-RUNTIME-RECONCILIATION
BASELINE_COMMIT=89c94f56d3f3ebffa231b06b3b3e6d5df5c9404f
SOURCE_COMMIT=NO_PRODUCTION_SOURCE_CHANGE
SOURCE_R5_COMMIT=bef64cb
TEST_R5_COMMIT=0d5046d
```

## Requirement reconciliation

| Frozen requirement | Implementation symbol | Test nodeid | Result |
|---|---|---|---|
| Shared streaming, resume, retry, atomic finalize | `retry_stream_to_atomic_file`, `FileDownloader`, `SafeVideoArtifactStore` | `tests/tc4/test_video_processing_r1.py::test_shared_retry_is_bounded_and_cleans_tc4_marker` | PASS |
| Safe video artifact and exact metadata | `SafeVideoArtifactStore`, `VideoArtifact` | `tests/tc4/test_video_processing_r1.py::test_artifact_uses_safe_relative_path_and_cleanup` | PASS |
| Restart recovery and attempt fencing | `VideoProcessingService.process_snapshot`, `recover_running`, `save_if_attempt` | `tests/tc4/test_video_processing_lifecycle_r3.py::test_service_restart_recovers_running_and_fences_stale_worker` | PASS |
| Failure is explicit and non-success | `VideoProcessingService._fail_stage` | `tests/tc4/test_video_processing_lifecycle_r3.py::test_video_failures_are_explicit_and_non_success` | PASS |
| TC4 public video response has no secret-adjacent fields | `create_video_router`, `VideoContentResponse` | `tests/tc4/test_video_boundaries_r4.py::test_video_public_read_response_redacts_secret_adjacent_fields` | PASS |
| Synthetic suite has no external media target | TC4 test fixtures | `tests/tc4/test_video_boundaries_r4.py::test_tc4_synthetic_suite_has_no_external_xhs_media_target` | PASS |
| `FeedDetailResult` / enrichment → canonical `WorkDetail` | No mapper found; current path uses `CollectionFeedEnrichment` plus `FeedMediaResult` | No test exists | HOLD |
| Collection image/media batch acquisition | No generic collection acquisition service found | No test exists | HOLD |
| `DownloadTaskCoordinator` / `FileDownloader` reuse for collection acquisition | Existing components serve ordinary `WorkDetail`; video collection path calls `VideoMediaAcquirer` and `SafeVideoArtifactStore` directly | No test exists | HOLD |
| TC4 acquisition independent of TC5 | `VideoProcessingService` now persists acquisition success with STT/OCR marked skipped; composition root no longer injects TC5 components | `tests/tc4/test_video_processing_lifecycle_r3.py::test_service_restart_recovers_running_and_fences_stale_worker` | PASS |
| Export-v2 | No existing export pipeline to extend in TC4 | No test exists | DEFERRED_TC6 |

## Contract answers

1. The persisted `CollectionFeedDetail` contains safe feed identity, title,
   body, note type, author, metrics, image URLs, publication time, location,
   and comments. It does not contain a canonical `WorkDetail` author/source
   mapping or transient media resources sufficient for the frozen download
   contract.
2. `FeedMediaResult` contains transient media locators and is not persisted in
   collection video content. Signed URL and token sentinels are absent from
   the TC4 row, artifact metadata, and public video response.
3. No `FeedDetailResult → WorkDetail` mapper currently exists.
4. The minimal mapper belongs in an adapter/application boundary: it should
   combine safe persisted enrichment with an ephemeral media locator and emit
   canonical core `WorkDetail`/`MediaResource` values without persisting the
   locator.
5. `ReadCapabilityRuntime.get_feed_media()` remains necessary for transient
   media locator refresh until the frozen detail-to-media mapping is restored.
6. Current `get_feed_media()` is used as the video acquisition input; it has
   not replaced the required canonical mapper.
7. Current TC4 collection video code does not use `DownloadTaskCoordinator` or
   `FileDownloader`; it directly calls `VideoMediaAcquirer` and the specialized
   `SafeVideoArtifactStore`.
8. Image collection acquisition is not implemented in the current TC4 path.
9. `VideoProcessingService` now completes TC4 acquisition without invoking
   PyAV, STT, or OCR; those implementations remain preserved as TC5/optional
   prework.
10. The next real-media canary should verify TC4 acquisition only. It is not
    authorized by this R5 run.

## Scope and runtime status

```text
IMPLEMENTATION_ROUTE_CONTRACT_RESTORED=PASS
REQUIREMENTS_ROUTE_CONSISTENT=PASS
ARCHITECTURE_ROUTE_CONSISTENT=PASS
R4_SCOPE_DRIFT_CORRECTED=PASS

TC4_GENERIC_MEDIA_CONTRACT=HOLD
FEED_TO_DOWNLOADABLE_MODEL_MAPPING=HOLD
FEED_IDENTITY_PRESERVED=PASS
MEDIA_KIND_PRESERVED=HOLD
MEDIA_INDEX_PRESERVED=HOLD

WORKDETAIL_REUSED=HOLD
MEDIARESOURCE_REUSED=HOLD
DOWNLOADTASK_REUSED=HOLD
FILEDOWNLOADER_REUSED=HOLD
SECOND_GENERIC_DOWNLOADER=NO

IMAGE_MEDIA_ACQUISITION=HOLD
MULTI_IMAGE_MEDIA_ACQUISITION=HOLD
VIDEO_MEDIA_ACQUISITION=PASS
MEDIA_ORDER_PRESERVED=HOLD
MEDIA_UNAVAILABLE_FAIL_CLOSED=PASS

PARTIAL_MEDIA_FAILURE_EXPLICIT=HOLD
PARTIAL_MEDIA_FAILURE_NOT_READY=HOLD
SUCCESSFUL_SIBLING_ARTIFACTS_PRESERVED=HOLD
FAILED_MEDIA_IDENTITY_PRESERVED=HOLD

TC4_TC5_RUNTIME_DECOUPLED=PASS
TC4_OCR_RUNTIME_DEPENDENCY=NONE
TC4_STT_RUNTIME_DEPENDENCY=NONE
TC4_SUCCESS_REQUIRES_STT=NO
TC4_SUCCESS_REQUIRES_OCR=NO
TC4_SUCCESS_REQUIRES_VIDEO_PREPROCESSING=NO

SHARED_STREAMING_DOWNLOADER=PASS
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

DEDICATED_TC4_TEST_MATRIX=HOLD
ARCHITECTURE_FILE_SIZE_GATE=PASS
```

Whisper implementation is preserved as TC5 prework and was not executed in
R5. OCR and export were not modified or reintroduced into the TC4 gate.

## Fresh verification

```text
RUFF_CHECK=PASS
RUFF_FORMAT=PASS
PYTEST=PASS
PYTEST_TOTAL=693
PYTEST_FAILED=0
COVERAGE=90.49%
COVERAGE_GATE=PASS

WHISPER_PREWORK_PRESERVED=YES
WHISPER_RUNTIME_EXECUTED_IN_R5=NO
OCR_RUNTIME_EXECUTED_IN_R5=NO
TC5_WORK_STARTED=NO
TC6_WORK_STARTED=NO
```

The current full regression result was run after the R5 runtime decoupling;
no Extension, manifest, or dependency lockfile changed in this phase.

```text
REAL_XHS_MEDIA_DOWNLOADED=NO
EXTERNAL_XHS_MEDIA_REQUEST_SENT=NO
REAL_USER_DATA_COMMITTED=NO
EXTENSION_FILES_CHANGED=NO
DEPENDENCY_LOCK_CHANGED=NO
TC4_MVP_B_WORK_PERFORMED=YES
TC4_REAL_MEDIA_CANARY_WORK_STARTED=NO
TC5_WORK_STARTED=NO
TC6_WORK_STARTED=NO
```

```text
TC4_MVP_B_PASS_CANDIDATE=NO
NEXT_PHASE=TC4-REAL-MEDIA-CANARY
NEXT_PHASE_AUTHORIZED=NO
TC4_REAL_MEDIA_CANARY_AUTHORIZED=NO
TC5_AUTHORIZED=NO
TC6_AUTHORIZED=NO
```
