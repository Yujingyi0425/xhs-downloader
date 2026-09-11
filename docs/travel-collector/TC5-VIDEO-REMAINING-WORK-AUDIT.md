# TC5 视频剩余工作审计

## 当前状态

- `VIDEO_CURRENT_IMPLEMENTATION_STATUS=IMPLEMENTED_BUT_RUNTIME_BLOCKED`
- `VIDEO_LAST_PROVEN_RUNTIME_BOUNDARY=GET_FEED_MEDIA_BROWSER_DETAIL_NAVIGATION`
- `VIDEO_KNOWN_BLOCKERS=当前 Chrome 已加载 worker 未刷新；两次真实 canary 在同一 feed 身份已匹配但 tab 仍 loading 时返回 DETAIL_NAVIGATION_FAILED`
- `R4E_CURRENT_STATUS=SOURCE_REPAIR_PASS_RUNTIME_EFFECT_UNPROVEN`
- `VIDEO_PERMISSION_STATUS=SOURCE_HOST_PERMISSION_PRESENT_RUNTIME_ATTESTATION_UNPROVEN`
- `VIDEO_SECRET_SAFETY_STATUS=PASS_FOR_NEW_PIPELINE; historical failed browser task payloads remain outside new extraction records`

## 可直接复用

- detail readiness、feed identity validation、browser task lease/result、结构化安全遥测和 bounded retry。
- 现有 ephemeral token handoff、`FeedMediaResult` 短期 locator、`SafeVideoArtifactStore` 原子落盘、SHA-256/size 元数据和 SQLite CAS/restart recovery。
- PyAV 本地视频探测、固定间隔关键帧、RapidOCR/PaddleOCR 本地 CPU OCR 适配器；同一 OCR 适配器同时服务图片和视频关键帧。
- canonical extraction record、来源 provenance、快照级批处理、幂等键和 API/UI 状态触发。

## 已间接修复与仍真实存在

后来图片工作已经改善 detail page readiness、当前页面 identity、稳定图片地址、parser telemetry 和 artifact/readback 结构；这些能力已被视频路径复用。但它们没有替代真实视频 canary，也没有刷新用户当前 Chrome 已加载的 worker。

仍真实存在的边界是：视频真实 acquisition 尚未通过；因此音频抽取、ASR、关键帧 OCR、视频 extraction readback 和视频批量 backfill 尚未获得真实运行证据。系统依赖 PyAV，不要求系统 `ffmpeg/ffprobe` 命令；本机缺少外部命令应作为环境边界记录，不伪造工具存在。

## 最短 closure 路线

1. 让当前 Chrome 扩展实例加载包含 `tab.url` loading grace 修复的新构建。
2. 仅重跑一个代表性视频 canary，确认下载 artifact、PyAV 音频、CPU faster-whisper、关键帧 OCR、canonical extraction persistence 和重启读回。
3. 若单条闭环通过，再按 bounded batch/idempotency 回填视频；若仍失败，只修复新的第一失败边界。

`IMAGE_MVP_MILESTONE_FROZEN=YES`，`TC5_AUTHORIZED=NO`，`TC6_AUTHORIZED=NO`，`VIDEO_ACQUISITION_TRIGGERED=YES_BOUNDED_CANARY_ONLY`，`VIDEO_RAW_EXTRACTION_PRODUCT_READY=NO`。
