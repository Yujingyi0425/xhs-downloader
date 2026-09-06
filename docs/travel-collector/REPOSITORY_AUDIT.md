# XHS Travel Collector：Repository Audit

## 审计范围与基线

审计了 `apps/extension`、`apps/api`、`apps/webui`、`apps/mcp`、`packages/xhs-core`、`packages/xhs-adapters`、`packages/xhs-contracts`、`packages/xhs-sdk` 和 `tests`，并阅读根目录 `AGENTS.md`、`README.md`、`pyproject.toml`、`package.json`、`.env.example`。

## 问题回答

### 1. 收藏夹页面能力应放在哪里？

页面读取和虚拟列表累计属于 `apps/extension` 的页面适配/运行层；扩展服务调用和协议类型分别放在扩展 service 与 `packages/xhs-contracts`。收藏夹业务状态、持久化和后续编排不应放在页面脚本中，应进入 `xhs-core`。`xhs-adapters` 依赖并实现 core 的 ports，`apps/api` 作为 composition root 创建这些 adapter implementation 并注入 core application service；`xhs-core` 不得反向 import `xhs-adapters`。TC0 未发现现成收藏夹模块。

### 2. Extension 如何执行 BrowserTask？

`apps/extension/src/browser-task-runner.ts` 轮询 `/browser/extension/tasks/claim`，领取后由 `browser-task-claim-execution.ts` 和页面执行器分派。普通读取任务在当前小红书标签页中执行；`browser-page-runner.ts` 对 `get_feed_detail` 读取 `feed_id`、`xsec_token`、评论参数，并调用详情解析器。执行前后通过 running/result 接口回报状态。

### 3. 如何登记 capability token？

`apps/extension/src/browser-task-service.ts` 调用 `/browser/extension/register`，提交扩展标识和安装标识，服务端在 `apps/api/src/xhs_api/browser.py` 中校验扩展来源并签发令牌。服务端保存的是凭据受控表示；后续 claim、running、result 请求通过扩展认证头携带令牌。相关请求模型在 `browser_models.py`。

### 4. BrowserTask 如何持久化？

`xhs-core.domain.browser_tasks` 定义 `BrowserTask`、状态、租约和驱动；`BrowserTaskRepository` 定义仓储端口。`SqliteBrowserTaskRepository` 与 `browser_task_storage.py` 在 SQLite 中保存任务快照、状态、目标驱动、租约摘要和时间，并通过条件更新、原子领取、租约校验和过期查询支持恢复与并发控制。任务 payload/result 以 JSON 快照保存。

### 5. `GET_FEED_DETAIL` 调用链

API `/xhs/feeds/detail` 由 `capability_reads.py` 接收参数 → `ReadCapabilityRuntime.get_feed_detail` 依据路由策略选择 HTTP 或 Browser provider → Browser provider 提交 `BrowserTaskKind.GET_FEED_DETAIL` → 扩展 claim → 当前小红书标签页执行 `browser-page-runner.ts` → `feed-detail-parser.ts` 解析 → 扩展回传 result → 服务端验证结果模型并返回 `RoutedReadResponse[FeedDetailResult]`。HTTP provider 另有 `http_read_provider.py` 与 `parsing/feed_detail.py` 路径。

### 6. `feed_id` 与 `xsec_token` 如何流动？

它们从 `FeedSummary`/`FeedDetailPayload` 进入 API；payload 模型对 token 设置 `repr=False`。浏览器任务 payload 冻结后进入 SQLite，扩展从任务中读取并构造详情 URL；解析结果可带回刷新后的 token。WebUI 的 `use-browser-explorer.ts` 当前从卡片传给 `/xhs/feeds/detail`。现有普通 Feed 列表/详情接口会在内部处理 token，但新增收藏夹 API 必须明确禁止默认回显。

### 7. `FeedDetailResult` 字段

`packages/xhs-core/.../feeds.py` 与 `packages/xhs-contracts/src/index.ts` 定义：`feed_id`、隐藏表示的 `xsec_token`、`title`、`body`、`note_type`、`author`、`metrics`、`image_urls`、`published_at`、`ip_location`、`comments`、`comments_has_more`、`comments_cursor`。没有视频 URL、下载产物路径或统一的 `WorkDetail` 字段。

### 8. `FeedDetailResult` 与 `WorkDetail` 的关系

当前没有直接转换器或类型继承关系。`FeedDetailResult` 是浏览能力结果，使用英文字段和 Feed/评论模型；`WorkDetail` 是下载/帖子库领域模型，使用中文别名字段，包含作者、标签、发布时间、互动计数和 `media: list[MediaResource]`。TC3/TC4 必须设计显式、经验证的转换边界，不能假设两者已打通。

### 9. 媒体 URL 由谁产生？

HTTP 详情解析路径中的 `packages/xhs-adapters/src/xhs_adapters/parsing/media.py` 从详情 note 数据生成 `MediaResource`，区分视频、图片和动态图片；页面详情路径 `feed-detail.py` 产生的是 `image_urls`，不会直接产生 `MediaResource`。视频 URL 的页面结果目前不在 `FeedDetailResult` 契约中。

### 10. 扩展详情页下载如何获得 `MediaResource`？

现有扩展详情页下载主要通过 `apps/extension/src/feed-parser.ts`/页面解析结果和 `service.ts` 请求 `/xhs/detail`，下载流程接收服务端返回的 `WorkDetail`。未发现收藏夹批量路径，也未发现把 `FeedDetailResult` 直接转换成 `MediaResource` 的现成适配器。

### 11. `DownloadTask` 如何创建？

`apps/api/src/xhs_api/tasks.py` 的 `POST /tasks` 委托 `DownloadTaskCoordinator.submit`；协调器按 `client_request_id` 幂等，创建 queued 任务并调度。任务执行调用现有 `DownloadService`，再由 `FileDownloader` 对 `WorkDetail.media` 下载并生成带 SHA-256、大小和相对路径的 `DownloadArtifact`。

### 12. 下载任务如何恢复？

API lifespan 启动时调用协调器 `start()`；`SqliteTaskRepository.list_recoverable()` 读取 queued/running 任务，将 running 改回 queued 后重新调度。文件下载器另有 URL 指纹 marker、`.part` 文件、Range 续传、重试和完成后的原子替换。

### 13. SQLite Repository/schema

已存在：`browser_task`、`download_task`、`collected_post`、`download_record`、`client_download_record`、扩展凭据、发布草稿/任务等仓储。收藏夹 `CollectionImport`/`CollectionItem`、快照历史和导出索引目前不存在。

### 14. WebUI 帖子列表如何加载？

现有 WebUI 通过 `use-browser-explorer.ts` 调用读取能力，列表使用 `FeedListResult`，详情使用 `FeedDetailResult`；已持久化帖子工作台通过 `/posts` 返回 `WorkDetail`，并由 `workspace.ts`/帖子组件合并下载任务状态。没有收藏夹列表、收藏夹详情或导出页面。

### 15. 是否已有 export 能力？

未发现旅行分析包的 `manifest.json`、`notes.jsonl`、`summary_input.md` 生成器，也未发现通用 export service。现有能力主要是帖子 JSON 持久化、下载产物和 WebUI 展示。

### 16. 是否已有收藏夹 BrowserTask？

没有。`BrowserTaskKind` 当前有登录、Feed 列表/搜索/详情、用户资料、互动和评论类型，没有 collection/favorite-board 类型。`browser-page-runner.ts` 和受管页面适配器也没有收藏夹读取分派。

### 17. 收藏夹页面 DOM/状态结构是什么？

本地源码没有真实收藏夹页面适配器，也没有可作为事实依据的收藏夹 DOM fixture。因此 URL、卡片选择器、board 标识、标题来源、加载容器、虚拟列表机制和停止条件仍需在 TC1 前用用户已登录的真实页面只读测量确认，不能按 SOP 中的示例 URL 或选择器硬编码。

### 18. 页面适配器能否读取当前页面且不主动导航？

能作为设计方向。现有扩展页面执行器在已打开的小红书标签页读取 DOM；但现有通用 BrowserTask 对详情任务会按 payload 构造目标 URL，且受管页面适配器有导航/执行边界。收藏夹 Capture 应新增“当前页只读”适配器/任务语义，禁止自动导航，并单独测试当前 URL、页面类型和登录态校验。

## 审计结论

现有 BrowserTask、租约、扩展认证、详情读取和下载基础可复用；缺口集中在收藏夹页面捕获、收藏夹领域模型/持久化、FeedDetail 到 WorkDetail/媒体的显式转换、视频处理和分析导出。TC0 通过前提是这些边界按本审计进入后续设计，并在 TC1 前完成真实页面结构测量。
