# TC4 MVP C5：图片 enrichment 页面兼容性证据

```text
PHASE=TC4-MVP-C5-IMAGE-ONLY-ENRICHMENT-PAGE-COMPATIBILITY
START_HEAD=b8cd87bc57a838c7250dca4ac260a8d03efba8a5
C5_SOURCE_HEAD=24ded805dcfc38f0c0b232c37973a782721ec932
```

## 根因闭合

```text
ROOT_CAUSE_PROVEN=YES
FIRST_CONTEXT_MISMATCH_BOUNDARY=apps/extension/src/browser-task-runner.ts::executeInNewTab
REPAIR_CLASS=bounded image-only detail-page readiness and feed-identity gate
```

`provider_page_incompatible` 是浏览器读取任务失败后的通用 provider failure 映射：任务已经发生过至少一次尝试时，终态失败会映射为 `PAGE_INCOMPATIBLE`。它不是把收藏夹 board 页面认定为受支持的详情页，也不是允许 provider 在收藏夹页面上直接解析。

旧的 `get_feed_detail` 顺序是：

```text
创建新的详情页标签
→ 立即向页面发送 parser task
→ 页面/初始状态尚未 ready 时 parser 失败
→ 重试后的失败映射为 provider_page_incompatible
```

修复后的顺序是：

```text
创建新的详情页标签
→ bounded wait
→ 确认最终页面已 complete
→ 确认页面属于 /explore/<feed_id> 或 /discovery/item/<feed_id>
→ 确认 feed identity 匹配
→ 发送 parser task
```

```text
COMPATIBILITY_GUARD_BYPASSED=NO
```

provider 仍只接受与请求 feed identity 匹配的 XHS 详情页上下文；没有把 collection board route 加入支持范围。详情解析依赖详情页注入的初始状态和 feed identity，collection item 中已有的 feed identity 与临时访问上下文仅用于建立该详情页任务，不写入持久化证据。

## 调用链

```text
apps/api/src/xhs_api/collection_images.py::process_images
→ packages/xhs-core/src/xhs_core/application/collection_enrichment.py::CollectionDetailEnrichmentService.enrich_snapshot
→ apps/api/src/xhs_api/capability_runtime.py::ReadCapabilityRuntime.get_feed_detail
→ packages/xhs-core/src/xhs_core/application/browser_read_provider.py::BrowserReadProvider.get_feed_detail
→ apps/extension/src/browser-task-runner.ts::executeInNewTab
→ apps/extension/src/browser-task-errors.ts::isSupportedDetailPageForFeed
→ detail-page parser dispatch
```

## 验证结果

```text
EXTENSION_TYPECHECK=PASS
EXTENSION_LINT=PASS
EXTENSION_TEST=424/424
BACKEND_IMAGE_REGRESSION=18/18
EXTENSION_BUILD=PASS

IMAGE_COLLECTION_ITEM_COMPATIBLE_PATH=PASS
WRONG_PAGE_CONTEXT_REJECTED=PASS
WRONG_FEED_IDENTITY_REJECTED=PASS
IMAGE_ENRICHMENT_TO_CANONICAL_WORKDETAIL=PASS
PRODUCTION_USES_EXISTING_IMAGE_PIPELINE=PASS

VIDEO_ITEM_REMAINS_DEFERRED=PASS
VIDEO_PROVIDER_NOT_INVOKED=PASS
VIDEO_ACQUISITION_TRIGGERED=NO

TC4_SECRET_PERSISTENCE=PASS
TC4_TOKEN_PERSISTED=NO
REAL_WEBSITE_SMOKE_AFTER_C5=NOT_EXECUTED
TOTAL_PHYSICAL_CANARY_COUNT=5
NEW_VIDEO_PHYSICAL_CANARY_EXECUTED=NO
```

测试使用合成页面、合成 feed identity 和合成任务数据；未写入真实收藏内容、Cookie、Authorization、token、signed URL 或下载产物。

## 范围隔离

```text
C5_GET_FEED_DETAIL_CHANGE_SCOPE=IMAGE_DETAIL_ENRICHMENT_ONLY
GET_FEED_MEDIA_BEHAVIOR_CHANGED=NO
R4E_BEHAVIOR_CHANGED=NO
VIDEO_NAVIGATION_BEHAVIOR_CHANGED=NO
```

本轮只在 `get_feed_detail` 分支调用新的 readiness/identity gate。现有 `get_feed_media` 分支继续使用原有 media wait path；没有修改 pendingUrl grace、视频导航、R4E 或媒体下载逻辑。

真实 image runtime smoke 尚未执行，因此本证据不把 `COLLECTION_IMAGE_MVP_RUNTIME_READY` 写成 PASS。

