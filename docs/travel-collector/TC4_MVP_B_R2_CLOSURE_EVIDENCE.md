# TC4-MVP-B-R2 Closure Evidence

```text
PHASE=TC4-MVP-B-R2-CLOSURE
BASELINE_COMMIT=858be78cbb811e9ab703565524049a101148c6d6
SOURCE_R2_COMMIT=1f55186
TEST_R2_COMMIT=2dc22d8
REAL_USER_DATA_COMMITTED=NO
REAL_XHS_MEDIA_DOWNLOADED=NO
EXTERNAL_XHS_MEDIA_REQUEST_SENT=NO
SYNTHETIC_MEDIA_USED=YES
LOCAL_MODEL_RESOURCE_DOWNLOAD_PERFORMED=YES
```

## Fresh regression

```text
RUFF_CHECK=PASS
RUFF_FORMAT=PASS
PYTEST=PASS
PYTEST_TOTAL=685
PYTEST_FAILED=0
COVERAGE=89.63%
COVERAGE_GATE=PASS
ARCHITECTURE_FILE_SIZE_GATE=PASS
```

The run used the repository's installed `uv` executable and completed without
real XHS access. Existing downloader regression tests and the dedicated TC4
synthetic tests passed.

## Shared downloader and lifecycle closure

```text
SHARED_STREAMING_DOWNLOADER=PASS
SECOND_GENERIC_DOWNLOADER_REMOVED=YES
RANGE_RESUME_SHARED_WITH_TC4=PASS
DOWNLOAD_RETRY_SHARED_WITH_TC4=HOLD
URL_MARKER_CLEANUP=PASS
STREAMING_DOWNLOAD=PASS
RANGE_RESUME=PASS
ATOMIC_FINALIZE=PASS
PARTIAL_FAILURE_NO_FALSE_FINAL_FILE=PASS
ARTIFACT_RUNTIME_PATH=PASS
ARTIFACT_SHA256_EXACT=PASS
ARTIFACT_SIZE_EXACT=PASS

RUNNING_RESTART_RECOVERY=PASS
ATTEMPT_CAS=PASS
CAS_REJECTION_RESULT_SEMANTICS=PASS
```

The shared primitive owns streaming, Range selection, partial-file handling,
marker cleanup, atomic finalization, hashing, and size calculation. The
ordinary downloader's bounded retry wrapper remains intact. TC4 currently
does not have a dedicated retry-exhaustion integration path through the shared
primitive, so `DOWNLOAD_RETRY_SHARED_WITH_TC4` remains HOLD.

## Local model runtime

```text
PYAV_SYNTHETIC_SMOKE=PASS
WHISPER_SYNTHETIC_MODEL_LOAD=PASS
WHISPER_SYNTHETIC_TRANSCRIBE=PASS
WHISPER_RESULT_SCHEMA=PASS
WHISPER_SEGMENT_TIMESTAMPS_VALID=PASS

OCR_MODEL_LOAD=PASS
OCR_CHINESE_SYNTHETIC=HOLD
OCR_JAPANESE_SYNTHETIC=HOLD
OCR_ENGLISH_SYNTHETIC=HOLD
OCR_MULTILINGUAL_SYNTHETIC=HOLD
OCR_TEXT_DEDUP=PASS
```

Whisper was loaded and run against a generated local WAV using CPU int8.
PaddleOCR model resources were downloaded and the configured detector and
Japanese recognizer loaded, but actual inference failed on this Windows
runtime with PaddlePaddle `OneDnnContext does not have the input Filter`.
Parser-only OCR checks are not used as runtime inference evidence.

## Export and test-matrix status

```text
SYNTHETIC_EXPORT_V2=HOLD
SOURCE_ORDER_PRESERVED=HOLD
EXPORT_SECRET_REDACTION=HOLD
DEDICATED_TC4_TEST_MATRIX=HOLD
```

The complete export-v2 end-to-end smoke and the full responsibility-split R2
matrix have not been implemented, so TC4-MVP-B is not a PASS candidate.

## Scope

```text
EXTENSION_FILES_CHANGED=NO
MANIFEST_PERMISSION_CHANGE=NONE
NEW_DEPENDENCIES=NO
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
