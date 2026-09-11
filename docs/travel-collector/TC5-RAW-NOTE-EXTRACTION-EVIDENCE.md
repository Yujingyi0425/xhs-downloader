# TC5 原始笔记抽取证据

## 当前闭环结果

- `IMAGE_REAL_EXTRACTION_RUNTIME=PASS`：真实图片笔记详情中的标题、正文、已有图片 artifact 复用、OCR、持久化和仓储重启读回均通过。
- `IMAGE_BACKFILL_RUNTIME=PASS`：最新收藏快照中 33 条图片笔记、271 个图片 artifact 已完成抽取记录回填。
- OCR 结果：271 条图片 OCR 记录中 208 条 `SUCCESS`、63 条 `NO_TEXT`，均为正常可解释状态。
- `IMAGE_BACKFILL_IDEMPOTENCY=PASS`：记录按 `snapshot_id/feed_id/extraction_version` 幂等保存，没有新增媒体副本。
- `CANONICAL_PROVENANCE=PASS`：标题、正文、图片 OCR、视频 ASR、视频关键帧 OCR、页面字幕使用独立来源枚举；当前视频/字幕来源待视频运行时闭环后填充。
- `EXTRACTION_API=PASS`：提供本机快照级触发和读回接口；扩展面板提供最小“抽取原始文字”触发与状态提示。

## 冻结与最终回归

- `IMAGE_MVP_MILESTONE_FROZEN=YES`：图片 pipeline 在本证据之后不再修改。
- 最新快照回读：64 条记录，其中图片 33 条、视频 31 条；图片 artifact 271 个。
- 图片 OCR 回读：271 条，其中 `SUCCESS=208`、`NO_TEXT=63`、`FAILED=0`；重启后记录可读且幂等。
- Python 全量测试、Ruff、Extension typecheck、lint、build、安全回归均通过。
- 实际图片文件仍在本机 `volume/download`；抽取记录在本机 `volume/.xhs-downloader/downloads.db`，不进入 Git。

## 视频剩余边界

- `VIDEO_ACQUISITION_RUNTIME=BLOCKED_AT_DETAIL_NAVIGATION`：已执行两次有界代表性真实视频 canary，安全遥测均为同一 feed 详情 URL 已匹配、标签仍为 loading，未进入视频下载、音频、ASR 或关键帧阶段。
- 源码已修复该边界：loading 期间同时接受 `tab.url` 或 `pendingUrl` 的同 feed 详情身份；扩展边界测试通过。
- 当前 Chrome 已加载的扩展实例未能通过受控浏览器接口刷新内部扩展管理页，因此第二次真实 canary 仍运行旧的已加载 worker；不能将它误报为视频成功。
- `VIDEO_RAW_EXTRACTION_PRODUCT_READY=NO`，待扩展实例加载新构建后仅需重跑一个 canary，再决定是否进入批处理。

## 安全验收

- `TC4_SECRET_PERSISTENCE=PASS`
- `TC4_TOKEN_PERSISTED=NO`
- `COOKIE_PERSISTED=NO`
- `AUTH_PERSISTED=NO`
- `XSEC_PERSISTED=NO`
- `SIGNED_URL_PERSISTED=NO`
- `RAW_BROWSER_REQUEST_PERSISTED=NO`
- `REAL_MEDIA_COMMITTED=NO`
- `RAW_NOTE_EXTRACTION_PRODUCT_READY=NO`：仅因视频真实 acquisition 尚未跨过浏览器 detail navigation 边界；图片 MVP 已正式可用。

## 安全与数据边界

- 记录只保存本地数据库中的原始正文、标题、脱敏作者元数据、来源标记和本地产物元数据。
- 不在 evidence、日志或 Git 中记录真实收藏正文、Cookie、token、signed URL、xsec 参数、原始浏览器请求、OCR/ASR 模型调试输出。
- 真实媒体仍只位于本机 `XHS_WORK_PATH`/`volume` 和视频 artifact 目录；任何真实用户内容不进入 Git。
