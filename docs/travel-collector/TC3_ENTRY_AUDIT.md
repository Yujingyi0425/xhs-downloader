# TC3-A：Detail Enrichment Entry Audit

本审计基于冻结基线 `1a137778375ad75e7330b0b69e5c8b8888007980`。本阶段只确认现有入口、边界、可复用能力和实现缺口；不实现详情 enrichment，不修改生产源码、测试、数据库 schema、扩展或 manifest。

## 1. Existing detail entry

DETAIL_ENTRYPOINT=`apps/api/src/xhs_api/capability_reads.py:70`，路由为 `POST /xhs/feeds/detail`。它要求本机管理访问，并从请求体接收 `feed_id`、`xsec_token`、评论参数。

DETAIL_SERVICE=`apps/api/src/xhs_api/capability_runtime.py:117:ReadCapabilityRuntime.get_feed_detail`。该服务按现有 capability route strategy 在 HTTP 与 Browser provider 之间执行，并以 `feed_id` 核对结果身份。

DETAIL_ADAPTER=`packages/xhs-adapters/src/xhs_adapters/http_read_provider.py:172:HttpReadProvider.get_feed_detail`（HTTP 路径）；`packages/xhs-core/src/xhs_core/application/browser_read_provider.py:109:BrowserReadProvider.get_feed_detail`（BrowserTask 路径）。

DETAIL_BROWSER_TASK_KIND=`packages/xhs-core/src/xhs_core/domain/browser_tasks.py:18:BrowserTaskKind.GET_FEED_DETAIL`，跨边界值为 `get_feed_detail`。任务提交和等待复用 `BrowserTaskService` 与 `_BrowserReadExecution`。

DETAIL_EXTENSION_EXECUTOR=`apps/extension/src/browser-task-runner.ts:executeInXhsTab` → `apps/extension/src/browser-page-runner.ts:executeBrowserPageTask`。Extension 通过 `/browser/extension/tasks/claim` 领取任务；详情页执行器读取 `feed_id`、`xsec_token` 和评论参数，必要时加载评论，再返回结构化结果。

DETAIL_NORMALIZER=`apps/extension/src/feed-detail-parser.ts:parseFeedDetailDocument`（Extension 页面状态）；`packages/xhs-adapters/src/xhs_adapters/parsing/feed_detail.py:FeedDetailStateParser.parse`（HTTP 初始状态）。两条路径都归一化为共享 `FeedDetailResult`，没有现成的 `FeedDetailResult → WorkDetail/MediaResource` 转换器。

## 2. Detail contract

GET_FEED_DETAIL_INPUTS=`feed_id`、nonempty `xsec_token`、`comment_limit`、`include_replies`、`reply_limit`。输入模型为 `packages/xhs-core/src/xhs_core/domain/browser_requests.py:FeedDetailPayload`；token 使用隐藏 repr 的字段，不能进入公开输出。

GET_FEED_DETAIL_REQUIRES_BROWSER=NO。HTTP provider 可以读取静态详情初始状态；统一 capability runtime 也支持 Browser provider，具体由 route strategy 和 fallback 决定。

GET_FEED_DETAIL_REQUIRES_XSEC_TOKEN=YES。HTTP URL 与 Extension 新标签页 URL 都将 token 作为详情访问上下文传入；TC3 必须从收藏夹保存的最新 access context 取得它，不得借用 profile source，也不得向公开 API 暴露它。

GET_FEED_DETAIL_OUTPUT_SCHEMA=`packages/xhs-core/src/xhs_core/domain/feeds.py:FeedDetailResult` / `packages/xhs-contracts/src/index.ts:FeedDetailResult`：`feed_id`、隐藏表示的 `xsec_token`、标题、正文、note type、作者、互动指标、图片 URL、发布时间、IP location、评论、分页状态。该结果不是下载领域的 `WorkDetail`。

## 3. Collection data available to TC3

COLLECTION_REPOSITORY=`packages/xhs-core/src/xhs_core/domain/collection_ports.py:CollectionRepository`；生产实现为 `packages/xhs-adapters/src/xhs_adapters/sqlite/collections.py:SqliteCollectionRepository`，由 `apps/api/src/xhs_api/bootstrap.py:create_api_dependencies` 创建并注入 `CollectionImportService`。

SNAPSHOT_ITEM_LOOKUP=`CollectionRepository.list_snapshot_items(snapshot_id)`，SQLite 实现位于 `packages/xhs-adapters/src/xhs_adapters/sqlite/collection_reads.py:90`，按 `collection_snapshot_item.source_order` 返回 `CollectionSnapshotItem`。membership 只含 `snapshot_id`、`feed_id`、`source_order`，不含 token。

LATEST_ACCESS_CONTEXT_LOOKUP_PATH=`CollectionRepository.get_feed_access_context(feed_id)` → `CollectionReadMixin.get_feed_access_context` → `collection_feed.latest_xsec_token`。这是内部敏感读取端口；现有 collection GET routes 不调用它，也不返回 token。

EXISTING_DETAIL_MODEL=`FeedDetailResult` 是现有只读能力结果；`WorkDetail` 是下载/帖子库模型。两者均已存在，但没有收藏条目详情 enrichment 的生命周期模型。

EXISTING_DETAIL_TABLE=NO。现有 collection schema 的表为 `collection_board`、`collection_snapshot`、`collection_feed`、`collection_snapshot_item`；其中 `collection_feed` 只保存最新详情访问上下文，不保存详情结果。

EXISTING_DETAIL_STATUS_MODEL=NO。现有 `BrowserTaskStatus` 只有 `queued`、`claimed`、`running`、`succeeded`、`failed`、`needs_review`；它不能单独表达收藏详情的 `NEEDS_REIMPORT` 或持久化 enrichment 状态。

DETAIL_PERSISTENCE_NOT_PRESENT=YES。未发现 collection detail/enrichment 表、详情结果持久化端口、条目级详情状态或恢复用 enrichment record。现有 `posts` 表保存的是下载领域 `WorkDetail`，不能直接当作收藏详情状态。

## 4. Reuse and proposed semantics for TC3

BROWSER_TASK_REUSE=YES。TC3 应复用现有 `BrowserTaskKind.GET_FEED_DETAIL`、`FeedDetailPayload/FeedDetailResult`、BrowserTask lease、Extension claim/result、结果校验和过期租约恢复；不新增 collection 专用页面抓取器或 HTML scraper。

NEW_TASK_QUEUE_REQUIRED=NO。当前已有持久化 BrowserTask queue、Extension executor 和 `max_concurrency` worker 配置。TC3 只需增加从 snapshot membership 到既有详情任务的编排；是否需要独立 collection 调度表属于后续 schema 设计，不应在本审计中实现。

NEEDS_REIMPORT_PROPOSAL=缺失或失效的最新 feed access context、token 过期/无效且无法在本流程刷新时，详情记录进入 `NEEDS_REIMPORT`，提示 Extension 重新导入该收藏夹；不得静默复制旧 token 或借用 profile token。

RETRY_MODEL=只对可判定为暂时性的网络超时、浏览器暂不可用和有界服务错误进行有限次数重试；明确 token 无效、目标删除/不可用、结果结构不一致和认证/风控挑战不得无限自动重试，分别映射到 `NEEDS_REIMPORT`、终态失败或 `needs_review`，具体映射需在 TC3-B1/B2 由测试冻结。

CONCURRENCY_MODEL=复用现有 BrowserTask worker 的有限并发与 lease；TC3 编排器必须有界提交，不能为一个 snapshot 无限制创建任务，并应保证同一 enrichment key 不并发重复入队。

RESTART_MODEL=复用 SQLite BrowserTask 的持久化状态、lease expiry reconciliation 和 Extension 下一轮 claim。TC3 自身的 enrichment 状态若需要跨重启恢复，必须新增独立持久化记录；不能把进程内 Promise 当作恢复机制。

IDEMPOTENCY_MODEL=建议以 `(snapshot_id, feed_id, enrichment_version)` 作为详情 enrichment key；相同 key 返回既有任务/结果，不重复入队。新的 snapshot 即使 feed 相同也应是新的观察上下文；access context 更新不能改写历史 snapshot membership。

## 5. Proposed gated subphases

TC3_PROPOSED_SUBPHASES=

1. `TC3-B1`：冻结详情 enrichment domain/persistence contract。定义条目关联、详情摘要/结果保存边界、状态、任务 key、版本和 `NEEDS_REIMPORT` 语义；只做 synthetic domain/repository tests。
2. `TC3-B2`：实现 snapshot item → `GET_FEED_DETAIL` 编排。读取最新 access context，复用现有 BrowserTask queue/Extension executor，保证有限并发、同 key 幂等和 token 不出公开边界；不得下载媒体。
3. `TC3-B3`：补齐失败映射、retry、lease expiry、restart recovery、partial completion 和 conflict/duplicate 证据；所有测试使用 synthetic token 与 synthetic feed。
4. `TC3-B4`：完成 API/Extension 到 SQLite 的 synthetic integration evidence，验证详情结果持久化与读取边界；不得进入媒体获取。
5. `TC3-FINAL`：在新的人工授权后进行真实页面详情验收。TC4 仍需单独 Gate，不在 TC3 中开始媒体下载或视频处理。

TC3_AUDIT_TESTS=NOT_RUN_DOCS_ONLY

## 6. Scope guard and checkpoint

PRODUCTION_SOURCE_CHANGED=NO  
TEST_FILES_CHANGED=NO  
DB_SCHEMA_CHANGED=NO  
EXTENSION_FILES_CHANGED=NO  
MANIFEST_PERMISSION_CHANGE=NONE  
NEW_DEPENDENCIES=NO  

MEDIA_DOWNLOADED=NO  
VIDEO_PROCESSING_STARTED=NO  
TC4_WORK_STARTED=NO  

本文件只记录基线审计事实和后续提案，不表示 TC3-B1 已开始，也不表示 TC4 获得授权。
