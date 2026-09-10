# TC4 MVP-C4 收藏夹到图片媒体生产接线证据

## 冻结边界

```text
PHASE=TC4-MVP-C4-COLLECTION-TO-IMAGE-MEDIA-PRODUCTION-WIRING
START_HEAD=8949169175e4f8c5e8ff68660d4ed62b11db0b20
SOURCE_OF_TRUTH=docs/travel-collector/REQUIREMENTS.md, ARCHITECTURE.md, IMPLEMENTATION_ROUTE.md
REAL_VIDEO_RUNTIME=DEFERRED_ENVIRONMENT_LIMITATION
NEW_VIDEO_PHYSICAL_CANARY_EXECUTED=NO
TOTAL_PHYSICAL_CANARY_COUNT=5
TC5_AUTHORIZED=NO
TC6_AUTHORIZED=NO
```

本阶段没有修改 Source of Truth、Chrome permissions、R4E timeout，也没有执行真实网站、视频下载或 external browser-control 排障。

## 生产接线

| 边界 | 实现 | 结果 |
| --- | --- | --- |
| 收藏夹扫描 | `apps/extension/src/browser-page.ts` → `collection-panel.ts` → `collection-import-orchestration.ts` | 扫描成功后保存同一 observation |
| Collection → enrichment | `apps/extension/src/collection-image-runner.ts` → `POST /xhs/collections/snapshots/{snapshot_id}/process-images` → `CollectionImageProductionService` | 复用现有 `CollectionDetailEnrichmentService` |
| Enrichment → canonical media | `collection_image.py` 调用 `collection_feed_detail_to_work_detail` | 不重写 C1 规则 |
| Canonical media → artifact | `CollectionMediaService` → 共享 `DownloadService` → `SqliteCollectionMediaArtifactRepository` | 复用 C3 下载、身份校验、幂等、重试和 SQLite 读回 |
| UI/API 状态 | API 返回安全计数；`collection-panel.ts` 展示成功、失败和视频待处理数量 | 不返回 token、Cookie、媒体 URL 或 locator |

本机 API 新增：

- `POST /xhs/collections/snapshots/{snapshot_id}/process-images`
- `GET /xhs/collections/snapshots/{snapshot_id}/image-media`

处理请求只包含 `board_id` 与 `retry_failed`。扩展 Service Worker 调用图片端点时不依赖 Origin；仍要求 loopback、Bearer 能力令牌和扩展身份，页面身份由 Service Worker 发送页校验。

## capability closure

| 能力 | 状态 | 测试/运行时 |
| --- | --- | --- |
| single image | IMPLEMENTED | TESTED / synthetic E2E |
| multi-image | IMPLEMENTED | TESTED / synthetic E2E，顺序保持 |
| media ordering | IMPLEMENTED | TESTED |
| partial failure | IMPLEMENTED | TESTED，单条失败不阻塞其他条目 |
| artifact persistence | IMPLEMENTED | TESTED，SQLite readback |
| retry/idempotency | IMPLEMENTED | TESTED，稳定 request ID；只重试未成功媒体 |
| media identity validation | IMPLEMENTED | TESTED，冲突 fail-closed 为单条失败 |
| secret-safe persistence | IMPLEMENTED | TESTED；沿用 `TC4_SECRET_PERSISTENCE=PASS` |
| real-video acquisition | NOT CLOSED | RUNTIME_VALIDATED=DEFERRED；本阶段不调用 |
| generic WorkDetail | IMPLEMENTED | TESTED；C1 mapper 为唯一转换入口 |
| unsupported type | IMPLEMENTED | TESTED；标记 `unsupported` |

视频条目由 C3 media planner 返回 `video_deferred`，不调用视频 acquisition 或 browser task；图片条目独立继续处理。

## 验证结果

```text
PYTHON_FULL_SUITE=PASS
PYTHON_TESTS=全套通过
PYTHON_COVERAGE=90.53%
PYTHON_RUFF=PASS
ARCHITECTURE_TEST=PASS
COLLECTION_IMAGE_CORE_SYNTHETIC=5/5 PASS
COLLECTION_IMAGE_API_SYNTHETIC=1/1 PASS
EXTENSION_FULL_SUITE=421/421 PASS
EXTENSION_COLLECTION_RELEVANT=24/24 PASS
EXTENSION_TYPECHECK=PASS
EXTENSION_LINT=PASS
EXTENSION_BUILD=PASS
```

人工真实网站 smoke 尚未执行；因此本证据只证明 source/test wiring 和本地合成链，不把 runtime attestation 写成 PASS 或 FAIL。

## 安全不变量

```text
TC4_SECRET_PERSISTENCE=PASS
TC4_TOKEN_PERSISTED=NO
REAL_USER_DATA_COMMITTED=NO
SECRET_COMMITTED=NO
```

