# TC3-B1：Detail Enrichment Persistence Evidence

本证据对应 TC3-B1，基于 `4713ccb88ea78c82071e232f6fbb9609130f19d1`，只实现收藏条目详情 enrichment 的 domain 与 SQLite persistence contract。没有调用详情能力、创建浏览器任务、访问真实页面或修改 API/Extension。

## Checkpoint provenance

BASELINE_COMMIT=4713ccb88ea78c82071e232f6fbb9609130f19d1  
SOURCE_COMMIT=feb3ba2a135dc8b2aa1ab34f5c38b19fefc1ddde  
TEST_COMMIT=1a3e88c0b8d1e69e0450a510829ad327dd886b98  
EVIDENCE_COMMIT=待提交

## Domain contract

ENRICHMENT_MODEL=`CollectionFeedEnrichment`，身份为 `(snapshot_id, feed_id, enrichment_version)`。  
SANITIZED_DETAIL_MODEL=`CollectionFeedDetail`，由 `FeedDetailResult` 显式构造。  
ENRICHMENT_STATUS_MODEL=`CollectionEnrichmentStatus`：`pending`、`running`、`succeeded`、`failed_retryable`、`failed_terminal`、`needs_reimport`、`needs_review`。  
ENRICHMENT_VERSION=1  
TERMINAL_STATUSES=`succeeded`、`failed_terminal`、`needs_reimport`、`needs_review`  
SNAPSHOT_TIME_DISTINCT_FROM_ENRICHMENT_TIME=PASS：`captured_at` 与成功记录的 `enriched_at` 分开保存；非成功记录的 `enriched_at` 为 NULL。

`CollectionFeedDetail` 只保存 feed_id、标题、正文、note type、作者、互动指标、图片 URL、发布时间、IP location、评论和 comments_has_more。它不包含 `xsec_token` 或 `comments_cursor`。

## Persistence contract

ENRICHMENT_REPOSITORY=`CollectionEnrichmentRepository` / `SqliteCollectionEnrichmentRepository`  
ENRICHMENT_TABLE=`collection_feed_enrichment`  
ENRICHMENT_IDEMPOTENCY_KEY=`(snapshot_id, feed_id, enrichment_version)`  
TABLE_COLUMNS=`snapshot_id`、`feed_id`、`enrichment_version`、`status`、`detail_json`、`attempt_count`、`last_error_code`、`created_at`、`updated_at`、`enriched_at`  
FOREIGN_KEY=`(snapshot_id, feed_id) REFERENCES collection_snapshot_item(snapshot_id, feed_id)`

`ensure_enrichment` 使用 create-if-absent，不重置 status、attempt_count、detail 或 created_at。状态变更使用 `expected status → new status` 的事务内 CAS；CAS 不匹配时 fail closed。进入 running 才增加 attempt_count，重复 running 不重复增加。

成功保存要求 detail 与 enriched_at 同时存在且 last_error_code 为 NULL；非成功状态不保存 detail 或 enriched_at。详情 feed_id 必须与 enrichment feed_id 严格一致，身份不符不写入。

## Security and synthetic proof

XSEC_SENTINEL=`synthetic-xsec-never-persist`  
DETAIL_XSEC_FIELD_PERSISTED=NO  
DETAIL_XSEC_VALUE_PERSISTED=NO  
DETAIL_PERSISTENCE_FORM=`FeedDetailResult → CollectionFeedDetail → detail_json`，没有事后从原始 dump 删除 token。  
SENSITIVE_COLUMNS_IN_ENRICHMENT_TABLE=NONE：schema 不含 `xsec_token`、`access_context` 或 `source_url/tokenized_url`。  
COLLECTION_TOKEN_AT_REST_LOCATION=`collection_feed.latest_xsec_token` only；enrichment 表不保存 token。

## Synthetic tests

`tests/infrastructure/test_collection_enrichment_repository.py` 使用 synthetic snapshot、feed、token 和详情，覆盖：

- status enum、显式脱敏转换、feed identity mismatch；
- create-if-absent 幂等、pending → running CAS、attempt_count 一次递增；
- stale failure 不得覆盖 succeeded；
- failed_retryable、schema sensitive-column audit、orphan FK rejection；
- detail JSON round-trip、partial detail 不落库、重启读取；
- source_order 排序；
- TC2 snapshot、membership、latest access context 在新表初始化后保持不变。

## Fresh quality gate

RUFF_CHECK=PASS  
RUFF_FORMAT=PASS  
PYTEST=PASS  
PYTEST_TOTAL=662  
PYTEST_FAILED=0  
COVERAGE=91.38%  
COVERAGE_GATE=PASS

## Scope audit

TC3_B1_DOMAIN_CHANGED=YES  
TC3_B1_PERSISTENCE_CHANGED=YES  
DETAIL_NETWORK_ORCHESTRATION_CHANGED=NO  
API_ROUTE_ADDED=NO  
API_ROUTES_CHANGED=NO  
EXTENSION_FILES_CHANGED=NO  
MANIFEST_PERMISSION_CHANGE=NONE  
NEW_DEPENDENCIES=NO  
GET_FEED_DETAIL_CALLED=NO  
BROWSER_TASK_CREATED=NO  
MEDIA_DOWNLOADED=NO  
VIDEO_PROCESSING_STARTED=NO  
TC3_B2_WORK_STARTED=NO  
TC4_WORK_STARTED=NO

本阶段未实现 failure classifier、详情编排、重试调度、BrowserTask 创建、详情 API、媒体获取或视频处理。
