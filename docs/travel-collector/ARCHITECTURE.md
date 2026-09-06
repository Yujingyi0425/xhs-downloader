# XHS Travel Collector：架构边界

## 现有边界

### 编译/导入依赖方向

```text
apps（api / cli / mcp）
        ↓ import
xhs-adapters
        ↓ import
xhs-core
```

`xhs-core` 定义 domain、application 和 ports/Protocols；`xhs-adapters` 依赖
`xhs-core` 并实现这些 ports。`xhs-core` 不得 import `xhs-adapters`。各 app 之间也不得直接导入；扩展通过 `packages/xhs-contracts` 共享 TypeScript 契约。

### 运行时调用与依赖注入方向

```text
apps/api composition root
        ├─ 创建 xhs-adapters 实现
        └─ 注入 xhs-core application service
                    ↓ 调用 port
             xhs-adapters 实现
```

扩展页面通过 BrowserTask/capability HTTP 调用 `apps/api`；API 的组合根负责组装适配器和核心应用服务。运行时调用方向可以表现为 API → core service → adapter，但这不改变上面的 compile/import 依赖方向。

## 建议新增边界

```text
apps/extension 当前收藏页只读适配器
        ↓ 协议/HTTP
apps/api composition root
        ↓ 注入
xhs-core Collection/Detail application service
        ↓ ports
xhs-adapters CollectionRepository / SQLite / filesystem
```

核心应用服务内部的业务流程为：

```text
CollectionSnapshot / CollectionItem
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
