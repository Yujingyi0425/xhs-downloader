# TC4-MVP-C1 Collection Feed Detail Mapper Evidence

```text
PHASE=TC4-MVP-C1-COLLECTION-FEED-DETAIL-TO-WORKDETAIL-MAPPER
SYNTHETIC_ONLY=YES
REAL_USER_DATA=NO
TOKEN=NO
COOKIE=NO
```

## Mapping boundary

`collection_feed_detail_to_work_detail` receives a sanitized
`CollectionFeedDetail` and its `CollectionSnapshotItem` identity context. It
returns the existing canonical `WorkDetail` model without changing any
collection, download, artifact, retry, or browser runtime contract.

`CollectionSnapshotItem.source_order` remains the order of an item inside a
collection. `MediaResource.index` is independently assigned from `1..N` in
the order of media URLs inside one work.

The mapper derives only stable identity URLs from validated `feed_id` and
`author.user_id`. It preserves optional text, metrics, avatar, and publication
time when present. A video detail is represented as `WorkType.VIDEO` without a
fabricated video URL; video acquisition remains outside C1.

## Fail-closed checks

- Collection snapshot identity and detail `feed_id` must be present.
- Collection item and detail `feed_id` must match exactly.
- Author identity must be present.
- Image media references must be absolute HTTP(S) URLs.
- Empty media is represented as an empty list.
- Unknown note types remain `WorkType.UNKNOWN`.

## Verification

```text
MAPPER_UNIT_TESTS=11/11 PASS
IDENTITY_TESTS=PASS
MEDIA_ORDER_TESTS=PASS
SECRET_SAFETY_TESTS=PASS
TC1_REGRESSION=124/124 PASS
TC2_REGRESSION=10/10 PASS
TC3_RELEVANT_REGRESSION=11/11 PASS
REAL_VIDEO_RUNTIME_EXECUTED=NO
```

Commands were run with the repository virtual environment and the bundled
Node runtime. The project-wide coverage threshold was not used for the
single-file mapper run; the targeted tests themselves passed.

```text
TOKEN_PERSISTED=NO
SECRET_COMMITTED=NO
REAL_USER_DATA_COMMITTED=NO
RUNTIME_PERMISSION_ATTESTATION=DEFERRED_ENVIRONMENT_LIMITATION
TC5=NOT_AUTHORIZED
TC6=NOT_AUTHORIZED
```
