# TC4-MVP-B Video Processing Implementation Evidence

```text
PHASE=TC4-MVP-B-VIDEO-PROCESSING-IMPLEMENTATION
BASELINE_COMMIT=1cdeea3a5fc66939e0838b610c726518024ae770
REAL_USER_DATA_USED=NO
REAL_VIDEO_CANARY=NOT_AUTHORIZED
```

## Implemented scope

The candidate adds the dedicated `GET_FEED_MEDIA` read contract, reuses the
existing Extension media parser, generalizes the ephemeral xsec-token channel,
and keeps managed-browser support disabled. Video content has independent core
models, ports, processing orchestration, SQLite storage, a loopback management
API, safe-id artifact storage, PyAV inspection, lazy local STT, and PaddleOCR
adaptation.

The existing TC3 detail result contracts were not changed. No TC3 enrichment
status is mutated by the video service. Source URLs and xsec tokens are only
used transiently and are not part of the video-content record or public API
models.

## Dependency resolution

```text
PYAV_VERSION=18.1.0
FASTER_WHISPER_VERSION=1.2.1
CTRANSLATE2_VERSION=4.8.2
PADDLEOCR_VERSION=2.10.0
PADDLEPADDLE_VERSION=3.3.1
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
SYSTEM_FFMPEG_INSTALLED=NO
SYSTEM_FFPROBE_INSTALLED=NO
UV_LOCK_UPDATED=YES
```

Import smoke for PyAV, faster-whisper, PaddleOCR and PaddlePaddle passed.
Model-download and multilingual synthetic OCR/transcription smokes were not
run in this candidate, so the corresponding runtime gates remain HOLD.

## Verification

```text
NODE_VERSION=24.19.0
PNPM_VERSION=11.19.0
PYTEST_TOTAL=679
PYTEST_FAILED=0
PYTHON_COVERAGE=89.10%
EXTENSION_TESTS=406
EXTENSION_COVERAGE=89.66% statements
EXTENSION_TYPECHECK=PASS
EXTENSION_LINT=PASS
EXTENSION_BUILD=PASS
RUFF_CHECK=PASS
RUFF_FORMAT_CHECK=PASS
```

The full existing regression suites pass. New dedicated synthetic security,
artifact, persistence, processing, and export-v2 test coverage has not yet
been added; therefore this document is evidence of an implementation
candidate, not a TC4-MVP-B PASS declaration.

## Remaining gates

```text
SYNTHETIC_VIDEO_PROCESSING_TESTS=HOLD
PYAV_SYNTHETIC_SMOKE=HOLD
WHISPER_SYNTHETIC_TRANSCRIBE=HOLD
OCR_MULTILINGUAL_SYNTHETIC=HOLD
SYNTHETIC_EXPORT_V2=HOLD
TC4_MVP_B_PASS_CANDIDATE=NO
```

No real collection, real video, token, cookie, or export was processed.
TC4-MVP-C and TC4 remain unauthorized pending human review and closure of the
remaining synthetic/runtime evidence gates.
