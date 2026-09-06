# TC1D：Real Japan Collection Acceptance

本阶段只验证已经构建好的 Extension runtime 是否能在用户自己的已登录页面完成收藏夹扫描。扫描结果只保存在当前页面内存中，不会发送到 API，也不会写入本地服务。

## 1. 加载已构建扩展

1. 运行 Extension 的 production build。
2. 打开 Chrome 或 Edge 的扩展管理页面。
3. 开启“开发者模式”。
4. 点击“加载已解压的扩展程序”。
5. 选择仓库中的 `apps/extension/dist` 目录，不要选择源码目录。
6. 确认 `xhs-downloader` 加载成功；如果之前已加载旧版本，先点击“重新加载”。
7. 刷新小红书页面。

## 2. 确认真实页面

使用自己的账号正常登录小红书网页版，手动进入“我的收藏 → Japan”。确认当前地址形状为：

```text
https://www.xiaohongshu.com/board/<ID>
```

页面显示的收藏总数应为 50。这个数量只用于人工验收，不会传给扫描器，也不会控制扫描终止。

## 3. Run 1：完整扫描与滚动恢复

先手动滚到收藏列表中间附近。在 DevTools Console 只执行：

```js
document.scrollingElement?.scrollTop
```

记录返回值为 `RUN1_SCROLL_TOP_BEFORE`。

点击浏览器工具栏中的 `xhs-downloader`。应出现“小红书旅行收藏夹”面板，但页面不应自动开始扫描。记录 `RUN1_AUTO_SCAN_BEFORE_CLICK=NO`。

点击“扫描当前收藏夹”。扫描期间不要手动滚动、点击笔记、切换收藏夹或改变地址。成功时面板应显示：

```text
扫描完成，共发现 50 条唯一笔记
```

记录：

```text
RUN1_STATUS=SUCCESS
RUN1_UNIQUE_COUNT=50
```

扫描结束后再次执行 `document.scrollingElement?.scrollTop`，记录为 `RUN1_SCROLL_TOP_AFTER`。如果回到原先区域，记录 `RUN1_SCROLL_RESTORE=PASS`。

## 4. Run 2：重复性

关闭面板，在同一个收藏夹页面重新打开扩展面板。确认初始状态为“尚未扫描”，再次点击“扫描当前收藏夹”。记录：

```text
RUN2_STATUS=SUCCESS
RUN2_UNIQUE_COUNT=50
REPEATABILITY=PASS
```

只有 Run 1 和 Run 2 都恰好为 50，才能记录 `REPEATABILITY=PASS`。

## 5. Run 3：面板生命周期

打开面板并点击“扫描当前收藏夹”。在扫描完成前关闭面板，立即重新打开面板并再次启动扫描。等待新扫描结束，不要操作页面。记录：

```text
LIFECYCLE_CLOSE_CANCEL=PASS
LIFECYCLE_REOPEN_SCAN=PASS
LIFECYCLE_OLD_SESSION_ISOLATION=PASS
RUN3_UNIQUE_COUNT=50
```

确认旧扫描的结果没有改写新面板，新扫描没有出现明显并行争抢。

## 6. 普通帖子回归

进入任意普通 `/explore/<ID>` 页面，点击扩展按钮。不得出现收藏夹扫描面板，原有帖子下载面板应继续正常出现：

```text
NON_BOARD_COLLECTION_PANEL=NOT_OPENED
EXISTING_DOWNLOAD_PANEL=PASS
```

## 7. 请勿提交敏感证据

只回传以下脱敏结果：

```text
EXPECTED_COUNT=50
RUN1_AUTO_SCAN_BEFORE_CLICK=NO
RUN1_STATUS=
RUN1_UNIQUE_COUNT=
RUN1_SCROLL_TOP_BEFORE=
RUN1_SCROLL_TOP_AFTER=
RUN1_SCROLL_RESTORE=
RUN2_STATUS=
RUN2_UNIQUE_COUNT=
REPEATABILITY=
LIFECYCLE_CLOSE_CANCEL=
LIFECYCLE_REOPEN_SCAN=
LIFECYCLE_OLD_SESSION_ISOLATION=
RUN3_UNIQUE_COUNT=
NON_BOARD_COLLECTION_PANEL=
EXISTING_DOWNLOAD_PANEL=
```

不要提供 Cookie、localStorage/sessionStorage、完整 href、Network headers、真实 token、真实 feed identity、DOM dump、真实标题或截图。

如果失败，只需提供最终 UI 错误文字、最终数量、大致停止轮次和是否到底；不要先改代码、放宽超时、修改停止条件或截断数量。

## Historical Failure Evidence（TC1D-R1 修复前）

首次真实扫描未发现 Feed，随后只读测量确认：

```text
RUN1_UNIQUE_COUNT=0
ROOT_CAUSE=BOARD_XSEC_SOURCE_MISSING
BOARD_ANCHORS=60
UNIQUE_BOARD_FEEDS=30
UNIQUE_EXPLORE_FEEDS=30
BOARD_EXPLORE_INTERSECTION=30
MATCHED_WITHIN_DEPTH_9=30
TC1D_R1_REPAIR_REQUIRED=YES
```

当前页面证明 board route 携带非空 `xsec_token`，但不携带 `xsec_source`。不得从 profile route 借用 source；当前有效 Capture 契约为 `feed_id + xsec_token + matching explore alias`。

```text
PHASE=TC1D
STATUS=HOLD_REAL_PAGE_CONTRACT_MISMATCH
REAL_EXTENSION_LOADED=YES
REAL_BOARD_PAGE=YES
EXPECTED_COUNT=49
TC1D_R1_REPAIR_REQUIRED=YES
```

## Historical Failure Evidence（TC1D-R2 修复前）

真实重跑曾观察到当前页面显示数量为 50，但扫描累计数量停在 39，且扫描长期停留在页面顶部：

```text
CURRENT_EXPECTED_COUNT=50
RUN1_UNIQUE_COUNT=39
SCROLL_TOP=0
SCROLL_HEIGHT=8504
CLIENT_HEIGHT=984
AT_BOTTOM=NO
ROOT_CAUSE=NON_BOTTOM_LOADING_WAIT_DEADLOCK
```

该记录属于修复前历史证据；`CURRENT_EXPECTED_COUNT` 只用于人工验收比较，不进入生产终止逻辑。

## Historical Failure Evidence（TC1D-RERUN-2）

```text
CURRENT_EXPECTED_COUNT=50
RUN1_UNIQUE_COUNT=50
RUN2_UNIQUE_COUNT=50
RUN3_UNIQUE_COUNT=50
CAPTURE_COMPLETENESS=PASS
COUNT_REPEATABILITY=PASS
FINAL_ROUND=200
STOP_REASON=max_rounds
TERMINATION=FAIL
ROOT_CAUSE_CANDIDATE=BOTTOM_STABILITY_BLOCKED_BY_GENERIC_DOM_MUTATION
```

该证据表明捕获完整性已通过，但全页面 DOM mutation 阻塞了 bottom stability convergence；它不代表 TC1D 当前已 PASS。

## TC1D-RERUN-3 Acceptance Evidence（脱敏）

用户已确认三次真实 Japan 收藏夹扫描均完整捕获 50 条并正常以 bottom stability 结束：

```text
CURRENT_EXPECTED_COUNT=50
RUN1_STATUS=SUCCESS
RUN1_UNIQUE_COUNT=50
RUN1_STOP_REASON=bottom_stable
RUN2_STATUS=SUCCESS
RUN2_UNIQUE_COUNT=50
RUN2_STOP_REASON=bottom_stable
REPEATABILITY=PASS
RUN3_STATUS=SUCCESS
RUN3_UNIQUE_COUNT=50
RUN3_STOP_REASON=bottom_stable
LIFECYCLE_CLOSE_CANCEL=PASS
LIFECYCLE_REOPEN_SCAN=PASS
LIFECYCLE_OLD_SESSION_ISOLATION=PASS
CAPTURE_COMPLETENESS=PASS
NORMAL_TERMINATION=PASS
REAL_JAPAN_ACCEPTANCE=PASS
RUN1_AUTO_SCAN_BEFORE_CLICK=UNKNOWN
```

普通帖子回归证据尚未提供，因此 TC1 最终 Gate 仍保持 HOLD；不得据此进入 TC2A。

```text
NON_BOARD_COLLECTION_PANEL=UNKNOWN
EXISTING_DOWNLOAD_PANEL=UNKNOWN
STATUS=HOLD_FINAL_REGRESSION_EVIDENCE
```

## Current Checkpoint

```text
PHASE=TC1D-RERUN-3
STATUS=HOLD_FINAL_REGRESSION_EVIDENCE
CURRENT_FEED_CONTRACT=feed_id + xsec_token + matching explore alias
PROFILE_SOURCE_BORROWING=NO
RUN1_AUTO_SCAN_BEFORE_CLICK=UNKNOWN
TC1A=PASS
TC1B=PASS
TC1C=PASS
TC1D=HOLD
TC1_FINAL_STATUS=HOLD
NEXT_PHASE=TC1D-FINAL-REGRESSION
NEXT_PHASE_AUTHORIZED=NO
TC2_AUTHORIZED=NO
```
