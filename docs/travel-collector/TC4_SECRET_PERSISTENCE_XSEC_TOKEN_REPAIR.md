# TC4 Secret Persistence XSEC Token Repair

## 阶段合同

```text
PHASE=TC4-SECRET-PERSISTENCE-XSEC-TOKEN-REPAIR
MODE=AUDIT-FIRST-THEN-MINIMAL-REPAIR
PHYSICAL_CANARY_ALLOWED=NO
TOTAL_PHYSICAL_CANARY_COUNT=5
REAL_VIDEO_RETRY=NO
MEDIA_DOWNLOAD=NO
GET_FEED_MEDIA_VALIDATION=NO
```

本阶段独立于 permission runtime attestation。R4E 导航、pendingUrl grace、超时、详情
readiness、解析器、下载器和 TC4 其他阶段均未改动；不要求用户重载扩展。

## 审计结论

原始持久化边界为：

```text
xsec_token -> BrowserReadProvider/BrowserTaskService.submit
-> SqliteBrowserTaskRepository.save
-> browser_task.payload JSON
-> browser_task repository/API readback
```

同一问题也存在于通用任务 API；此前显式临时详情入口已经有内存交接，但通用入口没有
经过该路径。成功结果还可能在 `FeedSummary` 等嵌套字段中携带 `xsec_token`，并进入
任务终态 JSON。

真实本地数据库审计仅记录字段名和计数：`browser_task` 共 128 条记录，其中 5 条
`get_feed_media/failed` 快照含 `payload.xsec_token`；没有发现同表的 Cookie、Authorization、
pending URL 或 raw URL query 字段。`collection_feed.latest_xsec_token` 是此前已批准的
收藏访问上下文存储位置，本阶段未读取值、未修改、未 scrub。

## 最小修复

生产代码将所有含 `xsec_token` 的浏览器任务输入统一分离：任务身份、feed/user 标识、
操作参数和安全元数据进入 SQLite；token 只进入有容量和 TTL 限制的进程内一次性通道，
领取时回注给扩展或受管执行器。通道失效时任务 fail closed。

持久化边界的统一清洗器现在会：

- 从任务 payload 和成功结果的嵌套对象移除 secret-bearing 字段；
- 从持久化 URL 查询中移除 `xsec_token`、Cookie、Authorization、pending URL 和 raw URL query
  字段；
- 对失败/待核对结果继续保留既有白名单诊断和固定安全消息；
- 对媒体成功结果只保留 feed、note type 和 media count，完整 locator 仍只走临时结果通道。

旧记录 scrub 只更新 `browser_task.payload`，保留任务身份、状态、失败消息和安全诊断；
扫描 128 条记录，原位 scrub 5 条，未创建备份、证据副本或提交数据库文件。

## 验证

```text
TARGETED_RED=PASS_BASELINE_REPRODUCED_GENERIC_XSEC_PERSISTENCE
TARGETED_GREEN=PASS
TARGETED_SECRET_BOUNDARY_TESTS=PASS
TARGETED_API_READBACK_TEST=PASS
PYTHON_TEST=PASS_710_TESTS
PYTHON_LINT=PASS
PYTHON_TYPECHECK=NOT_CONFIGURED
EXTENSION_TYPECHECK=PASS
EXTENSION_LINT=PASS
EXTENSION_TEST=PASS_420_TESTS
EXTENSION_BUILD=PASS
DATABASE_SCRUB=PASS_5_ROWS
```

合成回归只使用 `TEST_ONLY_FAKE_XSEC_TOKEN`；未输出真实 token、token 片段、摘要、原始
序列化对象、请求正文或真实用户内容。领取接口中的 token 是扩展执行所需的短期运行时
传输；普通任务 submit/get/list、终态快照和错误/日志序列化均不含该 token。

## 最终 checkpoint

```text
STATUS=SOURCE_EVIDENCE_CANDIDATE_COMPLETE
PERMISSION_REPAIR_SOURCE_LOCAL=PASS
RUNTIME_PERMISSION_ATTESTATION=WAITING_MANUAL_CANONICAL_EXTENSION_RELOAD
REPAIR_RUNTIME_EFFECTIVENESS=NOT_YET_PROVEN
TC4_SECRET_PERSISTENCE=PASS
TC4_OVERALL_PASS=NO
TOTAL_PHYSICAL_CANARY_COUNT=5
NEW_PHYSICAL_CANARY_EXECUTED=NO
TC5_AUTHORIZED=NO
TC6_AUTHORIZED=NO
```

该 checkpoint 不授权任何新的真实视频任务，也不改变 permission runtime attestation 的
等待状态；到此停止。
