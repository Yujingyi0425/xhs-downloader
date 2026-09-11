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
- Python 全量测试、Ruff、Extension 全量测试（461 passed）、typecheck、lint、build、安全回归通过；Extension coverage 分支门槛当前为 `83.75% < 85%`，因此带 coverage 的脚本退出失败，未伪装为通过。
- 实际图片文件仍在本机 `volume/download`；抽取记录在本机 `volume/.xhs-downloader/downloads.db`，不进入 Git。

## 视频剩余边界

- `VIDEO_ACQUISITION_RUNTIME=BLOCKED_AT_MEDIA_PARSER`：最新 reload 后的 bounded canary 已跨过 detail navigation，页面诊断确认初始状态、主容器和详情容器存在，但静态状态与实时状态均未产生可下载视频 locator，最终为 `MEDIA_PARSER_EMPTY`。
- 静态状态为空时回读主世界实时状态的修复已通过本地测试，但真实页面仍返回空媒体；Extension 全量测试 461 passed，lint、typecheck、build 均通过。
- `VIDEO_RAW_EXTRACTION_PRODUCT_READY=NO`，需要加载该最新构建后再执行一个 canary，不能将当前失败误报为视频成功。

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
