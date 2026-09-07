# TC4-MVP-B-R3 Final Synthetic Closure Evidence

```text
PHASE=TC4-MVP-B-R3-FINAL-SYNTHETIC-CLOSURE
BASELINE_COMMIT=deab3918cbe40f25c1fcda9315b50c07bf833aa7
SOURCE_R3_COMMIT=b81ce71
TEST_R3_COMMIT=7c696cc
REAL_USER_DATA_COMMITTED=NO
REAL_XHS_MEDIA_DOWNLOADED=NO
EXTERNAL_XHS_MEDIA_REQUEST_SENT=NO
SYNTHETIC_MEDIA_USED=YES
LOCAL_MODEL_RESOURCE_DOWNLOAD_PERFORMED=YES
```

## Source-fixed and repository-level evidence

```text
SHARED_STREAMING_DOWNLOADER=PASS
SECOND_GENERIC_DOWNLOADER_REMOVED=YES
RANGE_RESUME_SHARED_WITH_TC4=PASS
DOWNLOAD_RETRY_SHARED_WITH_TC4=PASS
STREAM_EXCEPTION_CONTRACT=PASS
URL_MARKER_CLEANUP=PASS
PARTIAL_FILE_POLICY=PASS
ARTIFACT_RUNTIME_PATH=PASS
ATOMIC_FINALIZE=PASS
ARTIFACT_SHA256_EXACT=PASS
ARTIFACT_SIZE_EXACT=PASS

RUNNING_RECOVERY_REPOSITORY_LEVEL=PASS
ATTEMPT_CAS=PASS
CAS_REJECTION_SOURCE_FIX=PASS
```

The ordinary filesystem downloader and TC4 artifact store use the same
streaming primitive. Its retry helper is bounded, retains resumable partial
state for recoverable failures, and cleans the TC4 marker on successful or
exhausted handling. Invalid partial content remains fail-closed.

## Service-level evidence

```text
RUNNING_RESTART_SERVICE_LIFECYCLE=PASS
ATTEMPT_COUNT_MONOTONIC=PASS
STALE_WORKER_REJECTED_AFTER_RESTART=PASS
CAS_REJECTION_SERVICE_LEVEL_TEST=PASS
CAS_REJECTION_RESULT_SEMANTICS=PASS
```

The dedicated lifecycle test persists a RUNNING attempt, creates a fresh
repository/service instance, executes the service workflow, verifies attempt
2 becomes authoritative, and verifies a late attempt-1 service persist returns
the authoritative row without overwriting it.

## Runtime-smoke evidence

```text
PYAV_SYNTHETIC_SMOKE=PASS
WHISPER_SYNTHETIC_MODEL_LOAD=PASS
WHISPER_SYNTHETIC_TRANSCRIBE=PASS
WHISPER_RESULT_SCHEMA=PASS
WHISPER_SEGMENT_TIMESTAMPS_VALID=PASS
WHISPER_RUNTIME_EVIDENCE_REPRODUCIBLE=PASS
```

Whisper smoke command:

```text
uv run python -c "generate 2-second 16 kHz mono synthetic WAV; FasterWhisperTranscriber('tiny').transcribe(path)"
```

The smoke used CPU with `compute_type=int8`; it asserted non-negative
duration, result schema, and `0 <= segment.start <= segment.end`. The generated
WAV and model cache remained outside Git.

PaddleOCR was loaded with the repository's `PaddleOCR(lang="japan")` adapter
and its local model resources were downloaded. Actual inference then failed on
Windows at the PaddlePaddle convolution stage:

```text
PaddlePaddle=3.3.1
PaddleOCR=2.10.0
stage=detector inference
exception=NotFoundError: OneDnnContext does not have the input Filter
```

Therefore:

```text
OCR_MODEL_LOAD=PASS
OCR_ACTUAL_INFERENCE=HOLD
OCR_CHINESE_SYNTHETIC=HOLD
OCR_JAPANESE_SYNTHETIC=HOLD
OCR_ENGLISH_SYNTHETIC=HOLD
OCR_MULTILINGUAL_SYNTHETIC=HOLD
OCR_RESULT_SCHEMA=HOLD
OCR_TEXT_DEDUP=HOLD
```

The parser-only test is not used as actual OCR inference evidence.

## Export and security evidence

```text
SYNTHETIC_EXPORT_V2=HOLD
SOURCE_ORDER_PRESERVED=HOLD
IMAGE_POST_NO_FAKE_VIDEO_CONTENT=HOLD
VIDEO_SUCCESS_SAFE_CONTENT=HOLD
VIDEO_FAILURE_EXPLICIT_STATUS=HOLD
EXPORT_SECRET_REDACTION=HOLD
RAW_DB_SECRET_REDACTION=HOLD
PUBLIC_API_SECRET_REDACTION=HOLD
ARTIFACT_METADATA_SECRET_REDACTION=HOLD
DEDICATED_TC4_TEST_MATRIX=HOLD
```

The repository has no existing export-v2 pipeline to extend in this phase;
the synthetic export end-to-end and its raw-persistence security assertions
remain open. No second exporter was created.

## Fresh gates and scope

```text
ARCHITECTURE_FILE_SIZE_GATE=PASS
RUFF_CHECK=PASS
RUFF_FORMAT=PASS
PYTEST=PASS
PYTEST_TOTAL=687
PYTEST_FAILED=0
COVERAGE=90.28%
COVERAGE_GATE=PASS

EXTENSION_FILES_CHANGED=NO
MANIFEST_PERMISSION_CHANGE=NONE
DEPENDENCY_LOCK_CHANGED=NO
TOKENS_COOKIES_URLS_COMMITTED=NO
GET_FEED_DETAIL_CALLED=NO
BROWSER_TASK_CREATED=NO

TC4_MVP_B_WORK_PERFORMED=YES
TC4_MVP_C_WORK_STARTED=NO
TC4_FINAL_WORK_STARTED=NO
```

```text
TC4_MVP_B_PASS_CANDIDATE=NO
NEXT_PHASE=TC4-MVP-C-REAL-VIDEO-CANARY
TC4_MVP_C_REAL_VIDEO_CANARY_AUTHORIZED=NO
TC4_FINAL_AUTHORIZED=NO
```
