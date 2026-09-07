# XHS Travel Collector：实施路线

## Gate 规则

每阶段必须完成审计、设计、测试、实现、验证、提交和 checkpoint；`NEXT_PHASE_AUTHORIZED=NO`。没有人工 Gate 通过，不得跨阶段。

## 路线

### TC0 Repository Audit（当前）

输出真实源码审计、架构边界、需求基线、实现路线和测试策略。不得改运行时代码。

### TC1 Collection Capture（TC1A/TC1B/TC1C/TC1D 已完成）

阶段状态：`TC1A=PASS`、`TC1B=PASS`、`TC1C=PASS`、`TC1D=PASS`、`TC1D-R1=PASS`、`TC1D-RERUN-3=PASS`。当前真实页面 Capture contract 为：board route 中存在 `feed_id` 与非空 `xsec_token`，同卡片必须有 matching `/explore/<FEED_ID>` alias；`xsec_source` 不再是必需条件，且不得借用 profile source。TC1 已完成最终真实验收。TC2 仍未授权，且开始前必须先完成 Python/uv preflight。

```text
TC1=PASS
TC2_AUTHORIZED=NO
```

### TC2 Collection Persistence

TC2A Persistence Architecture Audit 已完成，TC2B1 Core + SQLite Persistence Implementation 已完成，当前状态：`TC2A=PASS`、`TC2B1=PASS`、`TC2B2=PENDING_HUMAN_AUTHORIZATION`。TC2B1 只实现 `xhs-core` domain/application/port 与 `xhs-adapters` SQLite 持久化，并使用 synthetic tests 验证；未新增 HTTP API、Extension 或 TypeScript contract。后续在人工 Gate 授权后，才可进入 API 实现。目标仍是验证幂等、历史快照、事务回滚、重启恢复和 token 脱敏。

### TC3 Detail Enrichment

复用现有 `GET_FEED_DETAIL` payload/result、BrowserTask 租约和扩展执行链；新增收藏条目到详情任务的编排、有限并发、恢复、失败状态和 `NEEDS_REIMPORT`。默认评论数为 0，禁止另写 HTML scraper。

### TC4 Media Acquisition

阶段合同：从 `FeedDetailResult` / enrichment 通过显式 mapper 转换为可下载的 `WorkDetail` / `MediaResource`，复用 `DownloadTaskCoordinator`、`FileDownloader`、fingerprint、SHA-256、Range resume 和 atomic completion；单媒体失败不得把整体标记为 ready。

当前进度：TC4-MVP-B 的视频 artifact、共享 streaming primitive、retry/resume、processing lifecycle、restart recovery、attempt CAS 和 secret-boundary synthetic work 已完成部分实现，但 generic collection media acquisition 与 canonical `WorkDetail` path 仍需 reconciliation；真实媒体 canary 尚未授权。

### TC5 Video Preprocessing

TC5 拥有 FFmpeg/FFprobe、STT、音频抽取和关键帧处理。当前已完成的 Whisper 本地 synthetic runtime 属于 TC5 prework；OCR 不属于 TC5 baseline，Windows PaddleOCR inference limitation 记录为可选未来能力。

### TC6 Analysis Export

阶段合同：从持久化状态生成稳定排序的 `manifest.json`、`notes.jsonl`、`summary_input.md` 和每笔记目录；导出前做敏感字段/URL 清洗，纯规则标签命名为 `suggested_tags`。

当前进度：TC4 synthetic export-v2、最终 export source order 与 export secret redaction 尚未实现，均保留给 TC6。

### TC7 WebUI

按收藏夹列表 → 详情 → 笔记列表 → 笔记详情分层；复用现有 API 请求和状态组件，扩展仅显示导入进度，不暴露 token。完成桌面、窄屏、长文本、空/错/partial/大列表验收。

### TC8 End-to-End Acceptance

先跑全量自动化回归，再使用本机真实收藏夹验证计数、详情、媒体、转录和导出。真实数据只在本机使用；生成最终验收文档，状态只能为 PASS 或 HOLD。
