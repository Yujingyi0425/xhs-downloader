# TC4-MVP-C2 Collection Image Media Pipeline Evidence

```text
PHASE=TC4-MVP-C2-COLLECTION-IMAGE-MEDIA-PIPELINE
SYNTHETIC_ONLY=YES
REAL_USER_DATA=NO
TOKEN=NO
COOKIE=NO
REAL_WEBSITE_ACCESSED=NO
REAL_VIDEO_RUNTIME_EXECUTED=NO
```

## Existing infrastructure audit

```text
FILE_DOWNLOADER_DEFINITION=
  xhs_adapters.filesystem.downloader.FileDownloader.download(WorkDetail, indexes)
  filters configured media kinds, creates deterministic paths, streams to an
  atomic target, and returns DownloadArtifact with SHA-256 and media identity.

DOWNLOAD_TASK_COORDINATOR_DEFINITION=
  xhs_core.application.download_tasks.DownloadTaskCoordinator
  persists URL-based DownloadTask records, schedules workers, publishes progress,
  recovers queued/running work, and supports explicit retry.

DOWNLOAD_REQUEST_DEFINITION=
  xhs_api.models.TaskRequest: url, indexes, force, client_request_id.

DOWNLOAD_RESULT_DEFINITION=
  xhs_core.domain.models.DownloadOutcome: message, canonical WorkDetail,
  DownloadArtifact list, and skipped flag.

ARTIFACT_MODEL_DEFINITION=
  xhs_core.domain.models.DownloadArtifact: path, sha256, size, media_index, kind.

RETRY_MODEL_DEFINITION=
  FileDownloader uses retry_stream_to_atomic_file with deterministic partial
  marker paths and configured retry attempts; DownloadTaskCoordinator separately
  persists attempts and requeues failed URL tasks.
```

The existing `FileDownloader` remains the only file downloader. A small
`DownloadService.download_detail` entry point adapts an already canonical
`WorkDetail` to it without reparsing a page or changing ordinary download
record semantics. `DownloadTaskCoordinator` is not directly reused for C2
because its public input is a URL and its worker intentionally reparses that
URL; C2 therefore keeps collection orchestration above the same
`DownloadService`/`FileDownloader` path. Full collection task persistence and
retry/idempotency closure remain outside this phase.

```text
EXISTING_SINGLE_FILE_DOWNLOAD_REUSABLE=YES
EXISTING_RETRY_REUSABLE=YES
EXISTING_RESUME_REUSABLE=YES
EXISTING_ARTIFACT_PERSISTENCE_REUSABLE=YES
```

## C2 implementation boundary

`CollectionMediaCoordinator` accepts a `CollectionSnapshotItem` and the C1
canonical `WorkDetail`. It validates collection/work identity, creates one
deterministic task per image `MediaResource`, preserves input media order, and
records non-image media as deferred. Each image is sent independently through
the existing detail-download port so a failed image does not erase successful
siblings. Results retain `snapshot_id`, `source_order`, `work_id`,
`media_index`, `kind`, and the returned artifact.

The adapter supplies the validated work ID in the naming input, while the
existing downloader still supplies its normal index-based filename and atomic
artifact behavior. Missing suffixes become `auto`; non-alphanumeric or overly
long suffixes are rejected before a filesystem path can be formed. Artifact
media index and kind are checked against the planned task before association.

Video media is only returned as deferred. No video URL acquisition, browser
task, media download, physical canary, or runtime attestation was executed.

```text
COLLECTION_IMAGE_PIPELINE_IMPLEMENTED=YES
SINGLE_IMAGE_PIPELINE=PASS
MULTI_IMAGE_PIPELINE=PASS
MEDIA_ORDER_PRESERVED=PASS
MEDIA_TASK_IDENTITY_STABLE=PASS
WRONG_WORK_ASSOCIATION_REJECTED=PASS
WRONG_MEDIA_INDEX_ASSOCIATION_REJECTED=PASS
SINGLE_IMAGE_FILENAME_STABLE=PASS
MULTI_IMAGE_FILENAME_STABLE=PASS
REPEATED_PLANNING_FILENAME_STABLE=PASS
ONE_MEDIA_FAILURE_DOES_NOT_CORRUPT_OTHER_RESULTS=PASS
REPEATED_MEDIA_PLANNING_STABLE=PASS
ARTIFACT_ASSOCIATION_IMPLEMENTED=YES
FULL_PARTIAL_FAILURE_MODEL=DEFERRED_TO_TC4_MVP_C3
FULL_RETRY_IDEMPOTENCY_CLOSURE=DEFERRED
FULL_ARTIFACT_PERSISTENCE_CLOSURE=DEFERRED
VIDEO_DOWNLOAD_EXECUTED=NO
```

## Verification

```text
C2_TESTS=10/10 PASS
TC1_REGRESSION=124/124 PASS
TC2_REGRESSION=10/10 PASS
TC3_RELEVANT_REGRESSION=11/11 PASS
C1_MAPPER_REGRESSION=11/11 PASS
DOWNLOADER_REGRESSION=19/19 PASS
RUFF=PASS
DIFF_CHECK=PASS
```

All new fixtures use synthetic IDs and `example.invalid` media URLs. No test
performs network access or writes a real-user artifact.

```text
TOKEN_PERSISTED=NO
SECRET_COMMITTED=NO
REAL_USER_DATA_COMMITTED=NO
TC5=NOT_AUTHORIZED
TC6=NOT_AUTHORIZED
NEXT_RECOMMENDED_PHASE=TC4-MVP-C3-COLLECTION-MEDIA-IDENTITY-ORDERING-AND-PARTIAL-FAILURE-CLOSURE
NEXT_PHASE_AUTHORIZED=NO
```
