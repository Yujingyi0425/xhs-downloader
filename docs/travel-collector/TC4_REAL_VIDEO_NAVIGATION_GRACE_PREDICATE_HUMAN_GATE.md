# TC4 Real Video Navigation Grace-Predicate Human Gate

## Gate 状态

```text
PHASE=TC4-REAL-VIDEO-NAVIGATION-GRACE-PREDICATE-PERMISSION-REPAIR
STATUS=HOLD_SECURITY_BOUNDARY_AND_MANUAL_RELOAD
BASELINE_HEAD=ede6b2e8151d69c6cbc0930d1adb7ba718608c54
R4E_RUNTIME_ACTIVATION_CLOSURE=PASS
R4A_R4D_TELEMETRY_CHAIN=CLOSED
```

R4E 的唯一 final-validation canary 已于 2026-09-10 执行一次；本 Gate 不运行
新的真实 canary，也不改变现有源码。

```text
FINAL_VALIDATION_TASK_ID=6201c3641ebf456d967da560bdaff6aa
TOTAL_PHYSICAL_CANARY_COUNT=5
R4E_FINAL_VALIDATION_CANARY_COUNT=1
RETRY=NO
```

## 真实结果

```text
T6_DETAIL_PAGE_READY=FAIL
FAILURE_CODE=DETAIL_NAVIGATION_FAILED
ELAPSED_MS=4990
TARGET_TAB_EXISTS=YES
LAST_TAB_STATUS=loading
LAST_ROUTE_CLASS=/unknown
URL_HOST_IS_XHS=NO
EXPECTED_ROUTE_MATCHED=NO
TAB_REMOVED=NO
```

按 R4E 的冻结判定规则，旧权限下的 final canary 属于 Case C：

```text
R4E_GRACE_PREDICATE_RUNTIME_RESULT=FALSE
R4E_NAVIGATION_REPAIR_EFFECTIVE=UNPROVEN
ROOT_CAUSE_PROVEN=PARTIAL
```

不能再将这次失败归因于旧扩展未 Reload，也不能继续把等待时间扩大到 15 秒或更久。

## 根因审查

canonical `apps/extension/dist/manifest.json` 当前只声明：

```text
permissions=activeTab, alarms, browsingData, debugger, downloads, storage
host_permissions=http://127.0.0.1/*, http://localhost/*
```

它没有声明 `tabs` 权限，也没有声明 `https://www.xiaohongshu.com/*` host permission。

R4E 在 service worker 的 `executeInNewTab` → `waitForMediaDetailPage` 路径中，先用
`chrome.tabs.create` 创建后台小红书详情页，再用 `chrome.tabs.get` 读取
`tab.status`、已提交的 `tab.url` 和 `tab.pendingUrl`。Chrome 官方 `tabs` API 文档说明，
`url` 与 `pendingUrl` 只有在扩展拥有 `tabs` 权限或目标页面 host permission 时才会提供：

<https://developer.chrome.com/docs/extensions/reference/api/tabs>

`activeTab` 是用户手势触发的临时授权；它不能替代后台新建小红书标签页所需的持续
host access。因而当前权限声明与 R4E 所依赖的 URL/pendingUrl 观察面不一致。

这与本次结果相互吻合：目标标签页仍为 `loading`，但安全遥测只能得到
`/unknown`、`url_host_is_xhs=false` 和 `expected_route_matched=false`，5 秒边界没有进入
conditional grace。现有安全结果没有保存 `pendingUrl` 原值，所以仍不能区分“字段缺失”与
“字段存在但不匹配”；因此根因状态保留为 `PARTIAL`，不作过度断言。

## 本次权限修复

已按批准内容实施唯一生产权限修改：source manifest 仅增加
`https://www.xiaohongshu.com/*`；canonical build 已重新生成 dist manifest。

```text
SOURCE_MANIFEST_XHS_HOST_PERMISSION=PASS
DIST_MANIFEST_XHS_HOST_PERMISSION=PASS
GLOBAL_TABS_PERMISSION_PRESENT=NO
ALL_URLS_PERMISSION_PRESENT=NO
BROAD_HOST_PERMISSION_ADDED=NO
SOURCE_DIST_PERMISSION_SEMANTICS_MATCH=PASS
```

R4E 源文件未修改；其 readiness、超时和 pendingUrl 语义保持不变。

```text
R4E_READINESS_SEMANTICS_UNCHANGED=PASS
R4E_TIMEOUT_SEMANTICS_UNCHANGED=PASS
```

## 最小修复选项

```text
OPTION_A=仅增加 https://www.xiaohongshu.com/* 到 host_permissions
OPTION_B=增加 tabs 权限
OPTION_C=改为不依赖后台 Tab URL 属性的导航握手设计
```

推荐先评审 `OPTION_A`：它只覆盖当前任务目标站点，能够同时让后台读取该站点的
`tab.url` 与 `tab.pendingUrl`，权限面小于全局 `tabs`。该选项仍属于扩展权限扩大，必须由
人工 Gate 明确批准后才能实施。

## 本地验证与运行时状态

```text
TARGETED_MANIFEST_TEST=NOT_ADDED_NO_EXISTING_MANIFEST_CONTRACT
TARGETED_RED=NOT_APPLICABLE
TARGETED_GREEN=NOT_APPLICABLE
EXTENSION_TYPECHECK=PASS
EXTENSION_LINT=PASS
EXTENSION_TEST=PASS_420_TESTS
EXTENSION_BUILD=PASS
RUNTIME_PERMISSION_ATTESTATION=WAITING_MANUAL_CANONICAL_EXTENSION_RELOAD
XHS_TAB_URL_VISIBLE=PASS_PRE_RELOAD_COMMITTED_TAB
PENDING_URL_RUNTIME_OBSERVED=NO_NATURAL_IN_FLIGHT_NAVIGATION
REPAIR_RUNTIME_EFFECTIVENESS=NOT_YET_PROVEN
```

本阶段允许的 runtime attestation 只能在用户手动 Reload canonical unpacked Extension
后进行；不得创建 production media acquisition task。

## 人工决策字段

```text
PERMISSION_EXPANSION_REQUIRED=YES
RECOMMENDED_REPAIR=OPTION_A_XHS_HOST_PERMISSION
USER_APPROVAL_REQUIRED=SATISFIED
NEW_REAL_CANARY_AUTHORIZED=NO
R4E_CANARY_BUDGET_REMAINING=0
SECURITY_RECHECK=HOLD
TC4_OVERALL_PASS=NO
TC5_AUTHORIZED=NO
TC6_AUTHORIZED=NO
```

## 安全边界

```text
COOKIE_READ=NO
RAW_TOKEN_LOGGED=NO
SIGNED_MEDIA_URL_LOGGED=NO
TC4_TOKEN_PERSISTED=YES_EXISTING_FAILED_TASK_PAYLOADS
RAW_URL_QUERY_PERSISTED=NO
COOKIE_PERSISTED=NO
AUTHORIZATION_PERSISTED=NO
REAL_MEDIA_COMMITTED=NO
REAL_USER_DATA_COMMITTED=NO
SECRET_COMMITTED=NO
SOURCE_OF_TRUTH_CHANGED=NO
```

安全复核发现失败的 `browser_task.payload` 仍包含 `xsec_token`。这是既有持久化边界
问题，本次权限修复不获授权顺带修改；因此 permission-repair phase 不能标记为完整
PASS，也不能形成可运行 real-video validation 的绿色 Gate。后续需另行授权一个
bounded secret-persistence repair phase。
