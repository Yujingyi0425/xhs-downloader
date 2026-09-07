# TC4-MVP-A — Video Content Pipeline Entry Audit

本审计基于冻结基线 `7543730c8ca9196562e4b9257307116fa3dc1fe9`。本文不包含真实收藏夹标识、视频 URL、正文、作者、token 或用户数据。

## 当前边界

```text
TC3_VIDEO_POST_METADATA_ONLY=YES
VIDEO_CONTENT_UNDERSTANDING_PRESENT=NO
REAL_COLLECTION_TOTAL=59
REAL_DETAIL_SUCCEEDED=42
REAL_DETAIL_FAILED_RETRYABLE=17
SUCCESSFUL_VIDEO_POSTS_OBSERVED=18
```

`FeedDetailResult` / `CollectionFeedDetail` 当前保存标题、正文、note type、作者、metrics、图片、发布时间、IP 位置和评论；没有 video media URL、artifact、音频、transcript、OCR、keyframes 或 video summary。

## Extension 视频解析审计

`apps/extension/src/parser.ts` 的 `parseCurrentDocument` → `parseInitialStateScript` 读取 `window.__INITIAL_STATE__`。视频路径由 `parseVideo` 处理：

- 优先读取 `note.video.consumer.originVideoKey`，拼接固定媒体域名和 key；
- 没有 origin key 时，`selectVideoStream` 合并 H.264/H.265 stream；
- stream 按高度降序选择最高高度项；
- 先取所选项的 `backupUrls`，再 fallback 到 `masterUrl`；
- 视频返回 `kind=video`、`suffix=mp4`，并保留图片预览地址。

```text
EXISTING_VIDEO_MEDIA_PARSER=PASS
ORIGIN_VIDEO_KEY_SUPPORTED=YES
H264_SUPPORTED=YES
H265_SUPPORTED=YES
VIDEO_PREVIEW_SUPPORTED=YES
NEW_VIDEO_URL_PARSER_REQUIRED=NO
```

TC4-MVP-B 应复用或提取该逻辑，不创建第二套字段猜测逻辑。

## Feed-detail 契约差距

`apps/extension/src/feed-detail-parser.ts` 同样从 `window.__INITIAL_STATE__` 的 `note.noteDetailMap` 读取目标 note，并校验 feed identity。它只输出 `image_urls`，没有视频媒体字段；`FeedDetailResult` 也没有可持久化 video media locator。

```text
FEED_DETAIL_AND_DOWNLOAD_PARSER_SHARE_SOURCE_STATE=YES
VIDEO_MEDIA_DROPPED_AT_FEED_DETAIL_CONTRACT=YES
```

推荐在 TC4-MVP-B 中增加共享的 pure media extraction helper，让下载 parser 与专用 browser media acquisition adapter 共用；本阶段不重构。

## Contract 选择

不推荐直接扩展 frozen `FeedDetailResult`。它被 HTTP provider、Browser provider、Extension task、managed browser、BrowserTask result validation、TC3 sanitizer 和 transient secret handoff 共同使用，加入 `video_media` 会扩大兼容与安全回归面。

推荐 Option B：专用 media acquisition capability，例如 `GET_FEED_MEDIA`，只在处理期间返回 transient media locator；它不改变 TC3 detail persistence，也不把 signed URL 传入长期 collection 数据。core 仅定义 capability/port，adapter 负责页面与 provider 交互，apps/api 只负责 composition 和 localhost trigger/read。

```text
RECOMMENDED_MEDIA_ACQUISITION_DESIGN=dedicated GET_FEED_MEDIA capability with transient locator
FEED_DETAIL_CONTRACT_CHANGE_REQUIRED=NO
TC3_B2_B1_SECRET_BOUNDARY_REUSABLE=YES
NEW_SECRET_STORE_REQUIRED=NO
VIDEO_SOURCE_URL_PERSISTENCE=TRANSIENT
```

媒体身份沿用 `snapshot_id → feed_id → latest access context`。不得要求用户复制 URL/token，也不得从 token 生成持久 hash 或 fingerprint。

## 现有下载器复用

当前 `MediaKind.VIDEO`、`MediaResource`、`WorkDetail`、`DownloadArtifact`、`DownloadService`、`ArtifactDownloader`、`PageGateway` 和 filesystem downloader 已支持视频资源、mp4、流式下载、断点标记、原子落盘、SHA-256、文件大小和 download record。`DetailParser` 负责详情解析，下载器不应被第二套视频下载实现替代。

```text
EXISTING_VIDEO_DOWNLOADER_REUSABLE=YES
SECOND_GENERIC_DOWNLOADER_REQUIRED=NO
```

TC4 adapter 只需把 transient locator 交给现有 `ArtifactDownloader`；禁止在 router 或新 service 中手写 requests/aiohttp/urllib 下载循环。

## 本地 artifact 与持久化

```text
LOCAL_ARTIFACT_ROOT=%LOCALAPPDATA%\\xhs-downloader\\video-content\\
REAL_MEDIA_GIT_TRACKING=FORBIDDEN
```

建议按不含敏感信息的 `sha256(snapshot_id + feed_id)` identity 建目录。长期保存 snapshot/feed identity、local artifact path、sha256、size 和 processing status；不保存 signed/ephemeral source URL、含 xsec 的 navigation URL、token 或 token-derived fingerprint。

推荐独立 `collection_video_content`（或等价 repository），主键为 `(snapshot_id, feed_id, processing_version)`，不要污染冻结的 `CollectionEnrichmentStatus`。最小状态为 `pending/running/succeeded/failed_retryable/failed_terminal`，并独立记录 `stt_status`、`ocr_status`；允许保存部分结果。

```text
RECOMMENDED_PERSISTENCE_DESIGN=independent collection_video_content lifecycle
PARTIAL_RESULT_ALLOWED=YES
TC3_STATUS_MUTATED_BY_TC4=NO
```

## 环境与依赖审计

本机只检查、不安装：

```text
FFMPEG_AVAILABLE=NO
FFPROBE_AVAILABLE=NO
FASTER_WHISPER_INSTALLED=NO
OPENAI_WHISPER_INSTALLED=NO
TORCH_INSTALLED=NO
CTRANSLATE2_INSTALLED=NO
ONNXRUNTIME_INSTALLED=NO
CUDA_AVAILABLE=NO_OR_NOT_INSTALLED
TESSERACT_AVAILABLE=NO
PYTESSERACT_INSTALLED=NO
PADDLEOCR_INSTALLED=NO
RAPIDOCR_INSTALLED=NO
OPENCV_INSTALLED=NO
PIL_INSTALLED=NO
```

推荐 TC4-MVP-B：

```text
RECOMMENDED_STT_ENGINE=faster-whisper
RECOMMENDED_STT_MODEL=small, CPU int8
STT_CPU_SUPPORTED=YES
STT_MODEL_DOWNLOAD_REQUIRED=YES
RECOMMENDED_OCR_ENGINE=PaddleOCR multilingual
OCR_MODEL_DOWNLOAD_REQUIRED=YES
```

`faster-whisper` 适合本地 CPU 推理并覆盖中文、日文、英文；small/int8 是精度、速度和体积的折中。模型首次下载属于运行时资源下载，不是云端推理。PaddleOCR multilingual 比英文专用 OCR 更适合旅行视频中的中文、日文和英文，但依赖与模型体积较大；TC4-MVP-B 应先做小型真实/合成验证，不应本阶段安装。

系统依赖为 `ffmpeg/ffprobe`（required，用于媒体探测、音频抽取和 keyframe）；Python 依赖为 faster-whisper 及其 CPU runtime、PaddleOCR 及其推理依赖（required for enabled stages）；模型资源为 faster-whisper small 与 multilingual OCR model（required at first use, downloaded locally）。不引入 online STT/OCR/LLM API。

## Keyframe、STT、OCR 方案

```text
KEYFRAME_STRATEGY=fixed interval 4 seconds with duration-based cap
MAX_KEYFRAMES_PER_VIDEO=60
BOUNDED_KEYFRAMES=YES
OCR_TEXT_DEDUP_STRATEGY=normalize whitespace, exact duplicate removal, preserve chronological order
```

固定间隔加上限比 scene-change 更确定，且不做逐帧 OCR；视频异常长时仍受 60 帧上限约束。建议删除处理中间 `audio.wav` 和 keyframes，保留 transcript/OCR；`source.mp4` 默认可选保留，由本地磁盘策略控制。

```text
SOURCE_VIDEO_RETENTION=optional keep
AUDIO_RETENTION=delete after STT
KEYFRAME_RETENTION=delete after OCR by default
TEXT_RESULT_RETENTION=keep transcript and OCR
```

安全输出结构：

```text
VideoTranscript: language, duration_seconds, segments[start, end, text]
VideoOcrFrame: timestamp_seconds, text, optional frame_path
video_content: processing_status, duration_seconds, transcript, ocr, artifact.local_video_available
```

不保存 raw model debug、tokens、probability arrays、internal tensors 或媒体 source URL。最终 export 只提供文本结果与本地 artifact 是否存在，不包含 token、Cookie、BrowserTask internals、source navigation URL 或视频源 URL。

## TC4-MVP-B 范围与真实 canary

```text
TC4_ELIGIBLE_SOURCE=TC3 enrichment SUCCEEDED AND detail.note_type == video
OBSERVED_ELIGIBLE_VIDEO_COUNT=18
MAX_ACTIVE_VIDEO_PROCESSING=1
```

17 条 TC3 retryable 记录没有 detail，本阶段不为找视频类型重新抓取。B 阶段先完成 synthetic tests，再只处理 1 个真实 video canary，验证 acquisition、音频抽取、STT、keyframes、OCR、持久化、secret absence 和 export；通过后最多扩大到 3 个视频，不直接处理 18 个。

最终 export v2 保持 59 条 `source_order` 不变：成功 video 增加安全 `video_content`，image post 不增加无意义 transcript，未处理/失败 video 明确 status，不伪造 detail。无 online LLM summary，旅行语义由 ChatGPT 后续分析。

预估文件拆分遵守 handwritten Python <=300 lines/file：core models/ports/service；adapters 的 ffmpeg、STT、OCR、artifact filesystem；apps/api composition 与 localhost trigger/read。不得把 subprocess、whisper 或 OCR 直接写入 FastAPI router。

```text
TC4_MVP_B_SCOPE_DEFINED=YES
TC4_MVP_B_AUTHORIZED=NO
REAL_VIDEO_DOWNLOADED=NO
REAL_AUDIO_EXTRACTED=NO
REAL_TRANSCRIPT_CREATED=NO
REAL_OCR_CREATED=NO
```
