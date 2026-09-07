# TC4-MVP-B-R4 In-Scope Synthetic Closure Evidence

```text
PHASE=TC4-MVP-B-R4-IN-SCOPE-SYNTHETIC-CLOSURE
BASELINE_COMMIT=4fddf778d7f49d92545a82673095a015b864ea05
SOURCE_COMMIT=NO_PRODUCTION_SOURCE_CHANGE
TEST_COMMIT=e0c6ebf
REAL_XHS_MEDIA_DOWNLOADED=NO
EXTERNAL_XHS_MEDIA_REQUEST_SENT=NO
REAL_USER_DATA_COMMITTED=NO
EXTENSION_FILES_CHANGED=NO
DEPENDENCY_LOCK_CHANGED=NO
```

## Scope reconciliation

```text
TC4_SCOPE_REALIGNED=PASS
WHISPER_OWNER_PHASE=TC5
WHISPER_SYNTHETIC_PREWORK=PASS
OCR_TC4_GATE=NOT_REQUIRED
OCR_OWNER_PHASE=OPTIONAL_FUTURE
OCR_OPTIONAL_RUNTIME_STATUS=HOLD_WINDOWS_COMPATIBILITY
SYNTHETIC_EXPORT_V2=DEFERRED_TC6
EXPORT_SECRET_REDACTION=DEFERRED_TC6
```

Whisper prework used the local `faster-whisper` CPU int8 path with a generated
WAV, an actual tiny model load/transcription, schema validation, and segment
timestamp assertions. PaddleOCR model loading remains recorded as prework;
its Windows inference failure (`OneDnnContext does not have the input Filter`)
is an optional compatibility limitation and does not block TC4. No OCR engine,
dependency, or lockfile was changed in R4. Export-v2 is owned by TC6 and was
not reimplemented here.

## TC4 gates

```text
SHARED_STREAMING_DOWNLOADER=PASS
RANGE_RESUME_SHARED_WITH_TC4=PASS
DOWNLOAD_RETRY_SHARED_WITH_TC4=PASS
STREAM_EXCEPTION_CONTRACT=PASS
PARTIAL_FILE_POLICY=PASS
URL_MARKER_CLEANUP=PASS
ARTIFACT_RUNTIME_PATH=PASS
ATOMIC_FINALIZE=PASS
ARTIFACT_SHA256_EXACT=PASS
ARTIFACT_SIZE_EXACT=PASS
RUNNING_RESTART_SERVICE_LIFECYCLE=PASS
ATTEMPT_COUNT_MONOTONIC=PASS
STALE_WORKER_REJECTED_AFTER_RESTART=PASS
ATTEMPT_CAS=PASS
TC4_RAW_DB_SECRET_REDACTION=PASS
ARTIFACT_METADATA_SECRET_REDACTION=PASS
PUBLIC_API_SECRET_REDACTION=PASS
IMAGE_POST_NO_FAKE_VIDEO_CONTENT=PASS
VIDEO_SUCCESS_SAFE_CONTENT=PASS
VIDEO_FAILURE_EXPLICIT_STATUS=PASS
TC4_FEED_IDENTITY_PRESERVED=PASS
```

The raw database assertion is limited to TC4 video-content persistence and
does not reject the separately authorized `collection_feed.latest_xsec_token`
state. Synthetic token and signed-media URL sentinels are absent from the TC4
database row, artifact metadata, and public video-read response.

## Dedicated test matrix with exact nodeids

```text
TC4-01=tests/tc4/test_video_processing_r1.py::test_shared_retry_is_bounded_and_cleans_tc4_marker
TC4-02=tests/infrastructure/test_downloader.py::test_download_resumes_matching_partial_file
TC4-03=tests/tc4/test_video_processing_r1.py::test_shared_retry_is_bounded_and_cleans_tc4_marker
TC4-04=tests/tc4/test_video_processing_r1.py::test_shared_retry_is_bounded_and_cleans_tc4_marker
TC4-05=tests/infrastructure/test_downloader.py::test_download_writes_atomic_artifact
TC4-06=tests/infrastructure/test_downloader.py::test_download_writes_atomic_artifact
TC4-07=tests/infrastructure/test_downloader.py::test_download_writes_atomic_artifact
TC4-08=tests/tc4/test_video_processing_r1.py::test_artifact_uses_safe_relative_path_and_cleanup
TC4-09=tests/tc4/test_video_processing_lifecycle_r3.py::test_service_restart_recovers_running_and_fences_stale_worker
TC4-10=tests/tc4/test_video_processing_lifecycle_r3.py::test_service_restart_recovers_running_and_fences_stale_worker
TC4-11=tests/tc4/test_video_processing_r1.py::test_late_attempt_cas_returns_authoritative_row
TC4-12=tests/tc4/test_video_processing_lifecycle_r3.py::test_service_restart_recovers_running_and_fences_stale_worker
TC4-13=tests/tc4/test_video_processing_lifecycle_r3.py::test_service_restart_recovers_running_and_fences_stale_worker
TC4-14=tests/tc4/test_video_processing_r1.py::test_artifact_uses_safe_relative_path_and_cleanup
TC4-15=tests/tc4/test_video_boundaries_r4.py::test_video_public_read_response_redacts_secret_adjacent_fields
TC4-16=tests/tc4/test_video_processing_lifecycle_r3.py::test_service_restart_recovers_running_and_fences_stale_worker
TC4-17=tests/tc4/test_video_processing_lifecycle_r3.py::test_service_restart_recovers_running_and_fences_stale_worker
TC4-18=tests/tc4/test_video_processing_lifecycle_r3.py::test_video_failures_are_explicit_and_non_success
TC4-19=tests/tc4/test_video_processing_lifecycle_r3.py::test_service_restart_recovers_running_and_fences_stale_worker
TC4-20=tests/tc4/test_video_boundaries_r4.py::test_tc4_synthetic_suite_has_no_external_xhs_media_target
DEDICATED_TC4_TEST_MATRIX=PASS
```

All listed nodeids exist at the current HEAD. Every handwritten TC4 test file
is below 300 lines; no whitelist or architecture-test weakening was used.

## Fresh verification

```text
RUFF_CHECK=PASS
RUFF_FORMAT=PASS
PYTEST=PASS
PYTEST_TOTAL=693
PYTEST_FAILED=0
COVERAGE=90.49%
COVERAGE_GATE=PASS
ARCHITECTURE_FILE_SIZE_GATE=PASS
```

```text
TC4_MVP_B_WORK_PERFORMED=YES
TC4_MVP_C_WORK_STARTED=NO
TC4_FINAL_WORK_STARTED=NO
GET_FEED_DETAIL_CALLED=NO
BROWSER_TASK_CREATED=NO
TC4_MVP_B_PASS_CANDIDATE=YES
NEXT_PHASE=TC4-REAL-MEDIA-CANARY
NEXT_PHASE_AUTHORIZED=NO
TC5_AUTHORIZED=NO
TC6_AUTHORIZED=NO
```
