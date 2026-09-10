# TC4 MVP C6：选择性收藏图片处理证据

```text
PHASE=TC4-MVP-C6-SELECTIVE-COLLECTION-IMAGE-PROCESSING
START_HEAD=368c14ec2fc96ad1f3c14a4028e484f4dd18d8ca
C5_SOURCE_HEAD=24ded805dcfc38f0c0b232c37973a782721ec932
C5_EVIDENCE_HEAD=368c14ec2fc96ad1f3c14a4028e484f4dd18d8ca
C6_SOURCE_HEAD=79bd89a
```

## 选择模型

```text
COLLECTION_ITEM_STABLE_IDENTITY=CollectionSnapshotItem.feed_id
SNAPSHOT_ITEM_IDENTITY=snapshot_id + feed_id
WORKDETAIL_STABLE_IDENTITY=WorkDetail.work_id
PROCESS_IMAGES_SELECTION_MODEL=optional selected_feed_ids
```

`selected_feed_ids` 复用现有 snapshot membership 的稳定 feed identity。请求不使用 UI 数组位置、临时索引、标题或展示文本，也不携带 token、Cookie、Authorization 或原始媒体 locator。

省略 `selected_feed_ids` 时仍处理整个 snapshot；传入选择时，只处理属于该 snapshot 的指定 feed，并按 snapshot 原有 `source_order` 返回结果。

## 实现范围

```text
POST /xhs/collections/snapshots/{snapshot_id}/process-images
→ CollectionImageProductionService.process_snapshot
→ CollectionDetailEnrichmentService.enrich_snapshot
→ C5 bounded get_feed_detail readiness/identity path
→ collection_feed_detail_to_work_detail
→ existing CollectionMediaService
→ existing artifact persistence
```

本轮没有新增 downloader、coordinator 或第二套 artifact store。API 层只新增可选的非敏感 selection 字段；selection 校验在 provider 调用前完成。

## Selection 验证

```text
VALID_SELECTED_ITEM=PASS
MULTIPLE_SELECTED_ITEMS=PASS
UNKNOWN_SELECTED_ITEM_REJECTED=PASS
WRONG_SNAPSHOT_ITEM_REJECTED=PASS
DUPLICATE_SELECTION_HANDLED=PASS
SELECTION_ORDER_DETERMINISTIC=PASS

SELECTIVE_PARTIAL_FAILURE_MODEL=PASS
ONE_SELECTED_ITEM_FAILURE_DOES_NOT_ABORT_SELECTION=PASS

REPEATED_SELECTIVE_REQUEST_STABLE=PASS
DUPLICATE_ARTIFACT_CREATED=NO
SUCCESSFUL_ITEM_NOT_REDOWLOADED_UNNECESSARILY=PASS

BACKWARD_COMPATIBLE_DEFAULT_BEHAVIOR=PASS
```

## Existing pipeline and video boundary

```text
SELECTIVE_PATH_USES_C5_ENRICHMENT=PASS
SELECTIVE_PATH_USES_CANONICAL_WORKDETAIL=PASS
SELECTIVE_PATH_USES_EXISTING_IMAGE_PIPELINE=PASS
SELECTIVE_PATH_USES_EXISTING_ARTIFACT_PERSISTENCE=PASS

SELECTED_VIDEO_ITEM_BEHAVIOR=DEFERRED
VIDEO_PROVIDER_INVOKED=NO
VIDEO_ACQUISITION_TRIGGERED=NO
SELECTED_VIDEO_DOES_NOT_BLOCK_IMAGES=PASS
```

这里的 `VIDEO_PROVIDER_INVOKED=NO` 指视频专用 acquisition/provider 没有被调用；选择性生产仍复用既有通用详情 enrichment 来识别已选条目的 canonical 类型，之后由现有 media coordinator 将视频保持 deferred。没有进入 `get_feed_media`、R4E 或视频下载路径。

## Synthetic production-component E2E

```text
C6_SELECTIVE_IMAGE_E2E_SYNTHETIC=PASS
```

合成快照包含单图、图集、视频和未选择图片；请求以不同顺序选择三个 feed。测试证明：结果按 snapshot 顺序返回，单图和图集进入现有 artifact pipeline，视频 deferred，未选择条目没有 provider/download 调用；使用同一 SQLite 数据库重新组装 service 后可读回结果且不重复下载。

测试材料全部为合成数据和 `example.invalid` locator，不含真实收藏内容。

## 验证结果

```text
FULL_PYTEST=761/761
PYTHON_COVERAGE=90.58%
RUFF=PASS

EXTENSION_TYPECHECK=PASS
EXTENSION_LINT=PASS
EXTENSION_TEST=424/424
EXTENSION_BUILD=PASS

TC4_SECRET_PERSISTENCE=PASS
TC4_TOKEN_PERSISTED=NO
RAW_PENDING_URL_PERSISTED=NO
SIGNED_MEDIA_URL_PERSISTED=NO
RAW_URL_QUERY_PERSISTED=NO
COOKIE_PERSISTED=NO
AUTHORIZATION_PERSISTED=NO
REAL_USER_DATA_COMMITTED=NO
SECRET_COMMITTED=NO
```

## Runtime boundary

```text
SELECTIVE_IMAGE_PROCESSING_SOURCE_READY=YES
BOUNDED_IMAGE_RUNTIME_SMOKE_READY=YES
REAL_WEBSITE_SMOKE_AFTER_C6=NOT_EXECUTED
COLLECTION_IMAGE_MVP_RUNTIME_READY=NO
```

真实网站 smoke 尚未执行。本阶段只完成可供下一步人工选择 1–2 个 feed 的 bounded API 能力；没有访问真实网站、没有重新扫描 64 条收藏，也没有新增 physical canary。

## 冻结边界

```text
TOTAL_PHYSICAL_CANARY_COUNT=5
NEW_VIDEO_PHYSICAL_CANARY_EXECUTED=NO
TC4_OVERALL_PASS=NO
TC5_AUTHORIZED=NO
TC6_AUTHORIZED=NO
```
