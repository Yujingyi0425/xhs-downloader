# TC1A：Final Evidence（R2 脱敏汇总）

## Gate 结论

```text
PHASE=TC1A-FINAL-EVIDENCE
STATUS=HOLD_USER_EVIDENCE_REQUIRED
REAL_PAGE_MEASURED=YES
```

## 页面与链接事实

```text
PAGE_ORIGIN=https://www.xiaohongshu.com
PAGE_PATTERN=/board/<ID>
SCROLL_OWNER=document.scrollingElement
SCROLL_OWNER_TAG=HTML
BOARD_ROUTE=/board/<ID>/<ID>
BOARD_ROUTE_HAS_FEED_ID=YES
BOARD_ROUTE_HAS_XSEC_TOKEN=YES
BOARD_EXPLORE_ALIAS_RELATION=CONFIRMED
```

同一 DOM 卡片中已观察到 board + explore 链接组合，以及 board + profile 链接组合；因此 anchor occurrence 不能直接作为 feed 数量。R2 probe 以卡片内 feed ID 归一化后的 session-local hash 判重。

## 滚动与数量事实

```text
VIRTUALIZATION_PRESENT=YES
DOM_REMOVES_OLD_CARDS=YES
CUMULATIVE_MAP_REQUIRED=YES
LAZY_LOAD_PRESENT=YES
BOTTOM_DETECTION=CONFIRMED
MEASURED_CUMULATIVE_NORMALIZED_UNIQUE_FEEDS=50
USER_VISIBLE_EXPECTED_COUNT=49（用户截图确认）
COUNTS_EQUAL=NO
```

可见 normalized 数量从 31 下降到 11，而累计数量保持 50；本次测量过程中 `scrollHeight` 为 7352，底部连续 4 轮无新增且保持到底。推荐 TC1B 将滚动位置、scrollHeight、loading signal、累计 normalized 数量、连续无新增次数和最大轮数共同作为停止条件输入。

## 元数据结构信号

```text
TITLE_EXTRACTION=OPTIONAL
AUTHOR_EXTRACTION=OPTIONAL
NOTE_TYPE_EXTRACTION=NOT_FOUND
COVER_EXTRACTION=OPTIONAL
```

这些只是脱敏结构信号，不是正式 selector，也不代表字段值可靠可读。

## Token 重渲染事实

```text
XSEC_TOKEN_PRESENCE=CONFIRMED
TOKEN_PRESENT_AFTER_RERENDER=YES
TOKEN_LENGTH_CHANGED=YES
```

后续设计输入：同一 normalized feed 再次出现时，应使用最新非空 token 覆盖旧上下文；真实 token 值未输出、未提交。

## 安全与缺口

```text
COOKIE_READ=NO
LOCAL_STORAGE_READ=NO
PRIVATE_API_CALL=NO
NETWORK_CALLED_BY_PROBE=NO
NAVIGATION_PERFORMED=NO
REAL_FEED_ID_OUTPUT=NO
REAL_XSEC_TOKEN_OUTPUT=NO
REAL_TITLE_OUTPUT=NO
REAL_AUTHOR_OUTPUT=NO
```

TC1A 不能 PASS：用户页面明确显示 49，但脱敏测量得到 50 个 normalized candidate，存在 1 个尚未定位的额外候选。不得忽略该差异、截断结果或把 50 强行视为真实收藏数。需要进一步的 measurement repair 才能定位该候选，当前不得进入 TC1B。
