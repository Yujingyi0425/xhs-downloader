# TC4 视频剩余工作审计

```text
PHASE=TC4-VIDEO-REMAINING-WORK-AUDIT
IMAGE_MVP_MILESTONE_FROZEN=YES
NEW_REAL_VIDEO_CANARY=NO
VIDEO_ACQUISITION_TRIGGERED=NO
TC5_AUTHORIZED=NO
TC6_AUTHORIZED=NO
```

## 当前结论

```text
VIDEO_CURRENT_IMPLEMENTATION_STATUS=PARTIAL_INFRASTRUCTURE_ONLY_PRODUCT_NOT_CLOSED
VIDEO_LAST_PROVEN_RUNTIME_BOUNDARY=SYNTHETIC_GET_FEED_MEDIA_READINESS_PARSER_AND_ARTIFACT_HANDOFF
R4E_CURRENT_STATUS=SOURCE_REPAIR_PRESENT_RUNTIME_EFFECTIVENESS_UNPROVEN_HOLD
VIDEO_PERMISSION_STATUS=SOURCE_XHS_HOST_PERMISSION_PRESENT_RUNTIME_ATTESTATION_UNPROVEN
VIDEO_SECRET_SAFETY_STATUS=IMAGE_BOUNDARY_PASS_VIDEO_FAILED_TASK_PAYLOAD_SAFETY_REQUIRES_SEPARATE_REPAIR
```

当前没有成功的真实视频 acquisition 证据。最后一次真实 R4E validation 的结果是详情
页导航未在边界内就绪；后续源码已经包含 XHS host permission 与 bounded pending URL
grace，但权限 runtime attestation 没有在可观察的 canonical XHS 标签页上完成，且历史
证据明确记录 real-video retry budget 为 0。因此不能把 R4E 标为 PASS，也不在本审计中
重试 canary。

## 已有实现与已证明边界

当前代码已经具备以下合成/源码边界：

- Extension `GET_FEED_MEDIA` 任务会创建详情页、等待 bounded readiness、校验详情页
  route/feed identity，再向页面 parser 派发请求。
- `originVideoKey`、H.264/H.265 stream、backup/master URL 的视频解析逻辑存在；失败
  会返回有界的 failure code/telemetry。
- API 组合根已经有 transient media acquirer、视频处理 service、独立视频 artifact
  repository 和本机视频 process/read 路由。
- 合成 R6.1 已证明视频 artifact 的下载、hash/size、重启读回、失败重试和 source
  retention 语义。

这些证明的是 synthetic boundary 与 source wiring，不是当前真实 XHS 视频的成功获取。

## 可直接复用的能力

```text
REUSE_DETAIL_READINESS_AND_IDENTITY=YES
REUSE_BROWSER_TASK_LEASE_AND_RESULT_FLOW=YES
REUSE_GET_FEED_MEDIA_FAILURE_TELEMETRY=YES
REUSE_EPHEMERAL_SECRET_HANDOFF=YES
REUSE_CANONICAL_MEDIA_RESOURCE_AND_WORK_IDENTITY=YES
REUSE_SHARED_STREAMING_DOWNLOADER=YES
REUSE_ATOMIC_FINALIZE_RETRY_HASH_SIZE=YES
REUSE_INDEPENDENT_VIDEO_CONTENT_LIFECYCLE=YES
REUSE_LOOPBACK_VIDEO_API_BOUNDARY=YES
```

图片阶段后来验证和修好的 detail readiness、当前详情状态解析、稳定图片地址、页面
identity 与 bounded failure telemetry 可作为视频排障基础设施复用；但它们不等于视频
locator 在真实页面上已经成功。

## 历史 blocker 的重新分类

### 已被间接改善、但未被证明完全消失

- 详情页 readiness/identity gate 已修复并被图片 enrichment 真实运行验证；`GET_FEED_MEDIA`
  仍有自己的导航与 parser 边界，不能直接继承 image runtime PASS。
- 当前状态解析和 parser telemetry 已增强，下一次诊断可区分导航、content-script、
  parser 和 identity failure；这是诊断能力改善，不是 acquisition closure。
- XHS host permission 已进入 source/dist manifest，消除了文档中指出的缺失声明；但
  runtime permission effect 仍未通过 canonical XHS tab attestation 验证。
- 稳定图片 URL 与页面 adapter 变化改善了 image artifact 路径；它们不提供 video
  locator，也不应被当作视频修复。

### 仍真实存在

1. 没有成功真实视频 acquisition 的证据；最后真实 R4E 结果仍是 navigation failure。
2. R4E runtime effectiveness 未证明，且历史 canary budget 已耗尽，不能在本阶段补跑。
3. 收藏夹图片 UI 明确将 video 保持 deferred；现有视频 API 是本机管理入口，不是已
   完成的收藏夹用户视频产品 UI。
4. 视频处理 optional 依赖（AV、STT、OCR 及模型资源）不是默认 API 依赖，当前环境也
   没有新的真实处理验收证据。
5. 历史 permission gate 记录失败的 browser task payload 仍可能保存 `xsec_token`；
   这与图片 MVP 的 `TC4_TOKEN_PERSISTED=NO` 是不同边界，必须另开 bounded secret
   persistence repair，不能在本次审计中默认为已解决。

## 最短 video closure 路线

```text
1. 保持 image MVP 冻结，不改 image pipeline。
2. 单独授权并修复 video failed-task secret persistence，先通过安全回归。
3. 在 canonical XHS tab 可观察时完成只读 permission/runtime attestation；不创建任务。
4. 重新执行 synthetic GET_FEED_MEDIA + parser + artifact handoff gates。
5. 由人工重新授权新的、单次 bounded real-video canary budget 后，再决定是否运行 canary。
6. 真实 acquisition 通过后，才接入现有 VideoProcessingService 和最小用户触发/结果读取 UI。
```

本审计不执行第 5 步，也不启动 TC5/TC6。图片 MVP 继续保持：

```text
IMAGE_MVP_MILESTONE_FROZEN=YES
VIDEO_ACQUISITION_TRIGGERED=NO
TC5_AUTHORIZED=NO
TC6_AUTHORIZED=NO
```

## 安全边界

```text
REAL_VIDEO_CANARY_IN_THIS_AUDIT=NO
REAL_XHS_MEDIA_DOWNLOADED_IN_THIS_AUDIT=NO
RAW_VIDEO_URL_RECORDED=NO
COOKIE_READ=NO
AUTHORIZATION_PERSISTED_BY_THIS_AUDIT=NO
REAL_USER_DATA_COMMITTED=NO
SECRET_COMMITTED=NO
```

