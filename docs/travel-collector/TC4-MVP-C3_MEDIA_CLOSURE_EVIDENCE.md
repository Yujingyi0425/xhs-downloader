# TC4-MVP-C3 Collection Media Closure Evidence

```text
PHASE=TC4-MVP-C3-COLLECTION-MEDIA-IDENTITY-ORDERING-AND-PARTIAL-FAILURE-CLOSURE
START_HEAD=5973e91398fa790eec86e134a28b94eff9105773
SYNTHETIC_ONLY=YES
REAL_WEBSITE_ACCESSED=NO
REAL_USER_DATA_USED=NO
REAL_VIDEO_RUNTIME_EXECUTED=NO
```

## Production boundary audit

```text
MEDIA_IDENTITY_DEFINITION=
  CollectionMediaTask.identity = snapshot_id + work_id + media_index + kind;
  persisted CollectionMediaItemRecord repeats snapshot_id, source_order,
  work_id, media_index and kind beside the artifact.

MEDIA_ORDERING_DEFINITION=
  canonical MediaResource input order is retained by the planner; coordinator
  results are reconstructed by task order; persisted readback is sorted by the
  frozen one-based media_index contract.

PARTIAL_FAILURE_MODEL=
  CollectionMediaItemRecord stores succeeded/failed plus artifact or a
  redacted error_code; CollectionMediaBatchStatus is succeeded, partial,
  failed, or deferred.

ARTIFACT_PERSISTENCE_BOUNDARY=
  CollectionMediaArtifactRepository stores CollectionMediaBatchRecord in
  SQLite. The record contains only artifact path, sha256, size, media_index,
  kind, stable collection identity, status and safe error code.

RETRY_IDEMPOTENCY_BOUNDARY=
  CollectionMediaService uses caller-provided stable request_id. Existing
  requests read back without downloading; retry_failed selects only media
  without a successful artifact and merges new results in planned order.
```

The existing `FileDownloader`, `retry_stream_to_atomic_file`, Range resume,
atomic completion, and URL-based `DownloadTaskCoordinator` semantics were not
rewritten. C3 adds an independent collection-media record/repository and a
service-level reconciliation boundary. The existing downloader remains the
only file downloader, and the composition-root factory reuses the same
`DownloadService`/`FileDownloader` path.

## Closure checks

```text
MEDIA_IDENTITY_CLOSURE=PASS
DETERMINISTIC_ORDERING_CLOSURE=PASS
FULL_PARTIAL_FAILURE_MODEL=PASS
RETRY_IDEMPOTENCY_CLOSURE=PASS
ARTIFACT_PERSISTENCE_CLOSURE=PASS
RESTART_READBACK_CLOSURE=PASS

VALID_WORK_MEDIA_ASSOCIATION=PASS
WRONG_WORK_ASSOCIATION_REJECTED=PASS
WRONG_MEDIA_INDEX_ASSOCIATION_REJECTED=PASS
WRONG_MEDIA_KIND_ASSOCIATION_REJECTED=PASS
DUPLICATE_MEDIA_IDENTITY_HANDLED=PASS

ORDER_STABLE_ON_SUCCESS=PASS
ORDER_STABLE_WITH_PARTIAL_FAILURE=PASS
ORDER_STABLE_AFTER_RETRY=PASS
ORDER_STABLE_AFTER_PERSISTENCE_READBACK=PASS

SUCCESSFUL_MEDIA_NOT_DUPLICATED=PASS
RETRY_DOES_NOT_CREATE_DUPLICATE_ARTIFACT=PASS
RETRY_ARTIFACT_IDENTITY_STABLE=PASS
RETRY_FILENAME_STABLE=PASS
REPEATED_IDENTICAL_REQUEST_IDEMPOTENT=PASS

ARTIFACT_PERSISTENCE_SINGLE=PASS
ARTIFACT_PERSISTENCE_MULTI=PASS
ARTIFACT_PERSISTENCE_PARTIAL_SUCCESS=PASS
ARTIFACT_PERSISTENCE_AFTER_RETRY=PASS
ARTIFACT_RESTART_READBACK=PASS
ARTIFACT_SHA256_PRESERVED=PASS
ARTIFACT_SIZE_PRESERVED=PASS
ARTIFACT_MEDIA_INDEX_PRESERVED=PASS
ARTIFACT_KIND_PRESERVED=PASS
```

All-success, first/middle/last failure, multiple failure and all-failure
cases are covered. Failed media retain only safe error codes; successful
artifacts remain available during retry and are not downloaded again.
Persistence validation rejects duplicate identities, absolute/drive/traversal
paths, inconsistent batch status, and non-enumerated error-code text. No
signed URL, raw URL query, Cookie, authorization value or token field is part
of the persisted record.

## Verification

```text
C3_TARGETED_TESTS=14/14 PASS
C2_MEDIA_REGRESSION=10/10 PASS
C1_MAPPER_REGRESSION=11/11 PASS
DOWNLOADER_REGRESSION=8/8 PASS
TC1_EXTENSION_REGRESSION=124/124 PASS
TC2_REGRESSION=10/10 PASS
TC3_RELEVANT_REGRESSION=11/11 PASS
PYTHON_FULL_SUITE=746/746 PASS
ARCHITECTURE_TESTS=PASS
RUFF=PASS
DIFF_CHECK=PASS
ALL_RELEVANT_REGRESSION=PASS
```

```text
TC4_SECRET_PERSISTENCE=PASS
TC4_TOKEN_PERSISTED=NO
RAW_PENDING_URL_PERSISTED=NO
SIGNED_MEDIA_URL_PERSISTED=NO
RAW_URL_QUERY_PERSISTED=NO
COOKIE_PERSISTED=NO
AUTHORIZATION_PERSISTED=NO
SECRET_COMMITTED=NO
REAL_USER_DATA_COMMITTED=NO
VIDEO_DOWNLOAD_EXECUTED=NO
REAL_VIDEO_RUNTIME_EXECUTED=NO
TOTAL_PHYSICAL_CANARY_COUNT=5
NEW_PHYSICAL_CANARY_EXECUTED=NO
TC5_AUTHORIZED=NO
TC6_AUTHORIZED=NO
```

## Remaining capability audit after C1/C2/C3

```text
TC4_MVP_REMAINING_CAPABILITIES=
  real-video acquisition/runtime validation; production collection scan-to-
  enrichment-to-media API/UI wiring; any broader collection batch scheduler;
  optional future media types; later TC5 video preprocessing and TC6 export.

COLLECTION_IMAGE_MVP_READY=NO
EXACT_BLOCKERS=
  user-facing production wiring from the existing collection scan/enrichment
  flow into CollectionMediaService is not yet exposed as a complete UI/API
  workflow; real-video runtime remains deferred but is not an image-MVP blocker.

REAL_VIDEO_RUNTIME_BLOCKS_IMAGE_MVP=NO
NEXT_RECOMMENDED_PHASE=TC4-MVP-C4-COLLECTION-IMAGE-PRODUCTION-WIRING
NEXT_PHASE_AUTHORIZED=NO
```
