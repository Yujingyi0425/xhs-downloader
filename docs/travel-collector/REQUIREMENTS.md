# XHS Travel Collector：TC0 需求基线

## 文档状态

- 阶段：TC0 Repository Audit
- 状态：审计基线
- 上游：`Andy-SoulShell/xhs-downloader`
- 当前 Fork：`Yujingyi0425/xhs-downloader`
- 原则：未获人工 Gate 授权不得进入 TC1

## 目标

在现有登录态、浏览器任务、详情读取、媒体下载和 SQLite 能力上，增加“当前收藏夹批量采集 → 详情丰富 → 媒体处理 → AI 分析包导出”工作流。最终数据必须能够在不重新访问小红书网页的情况下供另一个 AI 阅读。

## 本阶段范围

TC0 只完成真实源码审计、架构边界、实现路线和测试策略，不新增收藏夹功能，不修改运行时代码，不实现 TC1。

## 冻结的后续需求

1. TC1 从当前已打开的小红书收藏夹页面累计读取全部唯一卡片，适配虚拟列表回收。
2. TC2 将收藏夹快照幂等持久化到本地 SQLite/API，并对 `xsec_token` 做受控边界管理。
3. TC3 复用 `get_feed_detail` 获取正文、作者、媒体和状态，支持重试、恢复及 `NEEDS_REIMPORT`。
4. TC4 复用现有 `WorkDetail`、`MediaResource` 和 `DownloadTask` 下载图文/视频媒体。
5. TC5 对视频执行 FFprobe、FFmpeg 音频抽取、本地 STT 和有上限的关键帧抽取。
6. TC6 输出 `manifest.json`、`notes.jsonl`、`summary_input.md`，移除认证和签名敏感信息。
7. TC7 在扩展和 WebUI 提供分层的收藏夹列表、详情、笔记和导出入口。
8. TC8 使用合成回归及用户本机真实收藏夹完成最终验收；真实数据不得提交 Git。

## 非目标

不做 Notion 自动写入、在线 LLM、旅行决策、平台发布、验证码/风控绕过、Cookie 窃取或认证信息上传。

## 已知仓库约束

- 依赖方向为 `apps → xhs-adapters → xhs-core`，应用之间不得直接导入。
- 手写代码单文件不超过 300 行。
- Python 公开接口使用中文 Google 风格 docstring。
- 公开测试材料只能使用合成、公版或明确授权材料。
- 日志、导出和 Git 不得包含 Cookie、`xsec_token`、敏感 URL、请求头、请求正文或真实用户内容。
