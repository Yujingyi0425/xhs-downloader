# XHS Travel Collector：实施路线

## Gate 规则

每阶段必须完成审计、设计、测试、实现、验证、提交和 checkpoint；`NEXT_PHASE_AUTHORIZED=NO`。没有人工 Gate 通过，不得跨阶段。

## 路线

### TC0 Repository Audit（当前）

输出真实源码审计、架构边界、需求基线、实现路线和测试策略。不得改运行时代码。

### TC1 Collection Capture（TC1A/TC1B/TC1C 已完成；TC1D 进行中）

阶段状态：`TC1A=PASS`、`TC1B=PASS`、`TC1C=PASS`、`TC1D=IN_PROGRESS`、`TC1D-R1=PASS`、`TC1D-RERUN=PENDING_HUMAN_AUTHORIZATION`。当前真实页面 Capture contract 为：board route 中存在 `feed_id` 与非空 `xsec_token`，同卡片必须有 matching `/explore/<FEED_ID>` alias；`xsec_source` 不再是必需条件，且不得借用 profile source。TC1D-R1 仅修复了该文档/运行时契约不匹配；新的真实 Japan 页面验收尚未重跑。TC2 未授权。

### TC2 Collection Persistence

在 `xhs-core` 定义收藏快照/条目端口和状态，在 `xhs-adapters` 增加 SQLite 实现，在 `apps/api` 组合路由，在扩展调用边界提交快照。验证幂等、历史快照、事务回滚、重启恢复和 token 脱敏。

### TC3 Detail Enrichment

复用现有 `GET_FEED_DETAIL` payload/result、BrowserTask 租约和扩展执行链；新增收藏条目到详情任务的编排、有限并发、恢复、失败状态和 `NEEDS_REIMPORT`。默认评论数为 0，禁止另写 HTML scraper。

### TC4 Media Acquisition

先实现并测试 `FeedDetailResult` 到可下载媒体/`WorkDetail` 的显式转换，再复用 `DownloadTaskCoordinator`、`FileDownloader`、指纹、SHA-256、续传和原子完成。单媒体失败不得标为整体 ready。

### TC5 Video Preprocessing

增加外部 FFmpeg/FFprobe 检测、音频抽取、可替换 STT provider、转录 JSON/TXT 和限量关键帧。缺失依赖返回 `NOT_CONFIGURED`，不让 Collector 崩溃；不做 OCR。

### TC6 Analysis Export

从持久化状态生成稳定排序的 `manifest.json`、`notes.jsonl`、`summary_input.md` 和每笔记目录；导出前做敏感字段/URL 清洗，纯规则标签命名为 `suggested_tags`。

### TC7 WebUI

按收藏夹列表 → 详情 → 笔记列表 → 笔记详情分层；复用现有 API 请求和状态组件，扩展仅显示导入进度，不暴露 token。完成桌面、窄屏、长文本、空/错/partial/大列表验收。

### TC8 End-to-End Acceptance

先跑全量自动化回归，再使用本机真实收藏夹验证计数、详情、媒体、转录和导出。真实数据只在本机使用；生成最终验收文档，状态只能为 PASS 或 HOLD。
