# XHS Travel Collector：架构边界

## 现有边界

```text
Extension page adapter
        ↓ BrowserTask / capability HTTP
apps/api composition root
        ↓
xhs-core application + domain ports/models
        ↓
xhs-adapters SQLite / HTTP / filesystem
        ↓
WebUI、CLI、MCP 通过各自 API/SDK 使用
```

应用之间不直接导入。扩展共享稳定 TypeScript 契约；Python 领域模型与适配器边界使用 Pydantic/Protocol。

## 建议新增边界

```text
当前收藏页只读适配器
  → CollectionSnapshot / CollectionItem
  → CollectionRepository
  → DetailEnrichmentCoordinator
  → FeedDetail → WorkDetail/分析中间模型
  → 现有 DownloadTask / FileDownloader
  → VideoPreprocessor
  → AnalysisExporter
```

收藏夹捕获不应直接操作 SQLite；页面脚本不应承载详情调度、下载或导出逻辑。`xsec_token` 只作为受控的详情执行上下文，任何公开响应、日志、导出和诊断都必须脱敏。

## 关键模型关系

现有 `FeedSummary`/`FeedDetailResult` 面向浏览能力，现有 `WorkDetail`/`MediaResource`/`DownloadTask` 面向下载领域。需要新增显式 mapper 或 enrichment 输入模型，验证字段完整性和媒体类型，不应把两个模型强行合并。

## 驱动策略

TC1 优先使用 Extension 驱动读取用户当前打开页面，因为该页面拥有登录态且需求明确要求不主动导航。受管浏览器是否支持当前收藏页，应在后续明确实现前单独评估；不能沿用详情 URL 拼接逻辑。

## 数据安全

数据库可以在最小必要范围临时保存 token 以支持详情任务，但模型 repr、日志、普通列表/详情 API、WebUI、导出和 Git 均不得暴露。签名媒体 URL 只在下载执行边界使用，不进入最终分析包。
