# TC1A：Real Page Measurement

```text
PHASE=TC1A
STATUS=HOLD_USER_EVIDENCE_REQUIRED
BASELINE_COMMIT=c433ff6718d400db64717413de11d4fb66a41743
REAL_PAGE_MEASURED=NO
```

## 当前阻塞

当前可用浏览器标签不是已打开的 Japan 收藏夹页面，且本任务不能读取 Cookie、localStorage、账号凭据或私有 API。仓库中也没有收藏夹真实 DOM fixture。因此本轮没有形成任何页面事实，不对 URL、selector、滚动容器、token 或虚拟列表行为做猜测。

## 用户侧测量步骤

1. 在 Chrome/Chromium/Edge 中登录小红书。
2. 手动打开「我的收藏 → Japan」具体收藏夹页面并保持页面停留。
3. 打开开发者工具 Console。
4. 仅粘贴并运行下方脱敏 probe。
5. 将 Console 输出的 JSON 复制回来；不要复制页面 HTML、正文、完整 href、Cookie、请求头或截图。

## 脱敏只读 probe

probe 只读取当前 DOM、页面 URL 的 origin/path/query key、滚动几何值和链接的结构信息；token 只输出是否存在及长度，feed id、标题、作者和 URL 值均不输出。它不调用网络、不导航、不读取 Cookie/localStorage，不保存数据。

```js
(() => {
  const redact = (value) => value ? "<REDACTED>" : "";
  const url = new URL(location.href);
  const scroll = document.scrollingElement;
  const anchors = [...document.querySelectorAll("a[href]")];
  const hrefs = anchors.map((anchor) => {
    const parsed = new URL(anchor.href, location.href);
    const keys = [...parsed.searchParams.keys()].sort();
    return {
      path_shape: pathShape(parsed.pathname),
      path_segment_count: nonEmptySegments(parsed.pathname).length,
      query_keys: keys,
      xsec_token_present: parsed.searchParams.has("xsec_token"),
      xsec_token_length: parsed.searchParams.get("xsec_token")?.length ?? 0,
      feed_id_present: /(?:explore|item|feed)/i.test(parsed.pathname),
      ancestor_classes: [...ancestorChain(anchor)].map((node) => node.className).filter((name) => typeof name === "string").slice(0, 5),
    };
  });
  const classCounts = new Map();
  for (const anchor of anchors) for (const node of ancestorChain(anchor).slice(0, 6)) {
    if (typeof node.className !== "string" || !node.className) continue;
    classCounts.set(node.className, (classCounts.get(node.className) ?? 0) + 1);
  }
  const result = {
    page: {
      origin: url.origin,
      path_shape: pathShape(url.pathname),
      path_segment_count: nonEmptySegments(url.pathname).length,
      query_keys: [...url.searchParams.keys()].sort(),
      title_present: Boolean(document.title),
      title_length: document.title.length,
    },
    scroll: scroll ? {
      owner: scroll === document.body ? "body" : "document.scrollingElement",
      client_height: scroll.clientHeight,
      scroll_height: scroll.scrollHeight,
      scroll_top: scroll.scrollTop,
    } : null,
    anchors: {
      count: anchors.length,
      samples: hrefs.slice(0, 12),
    },
    repeated_ancestor_classes: [...classCounts.entries()]
      .filter(([, count]) => count > 1)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 20),
    text_and_authentication: {
      page_text_returned: false,
      cookie_read: false,
      local_storage_read: false,
      network_called: false,
      navigated: false,
      redaction_marker: redact(true),
    },
  };
  console.log(JSON.stringify(result, null, 2));

  function* ancestorChain(node) {
    let current = node;
    while (current && current !== document.documentElement) {
      yield current;
      current = current.parentElement;
    }
  }

  function nonEmptySegments(pathname) {
    return pathname.split("/").filter(Boolean);
  }

  function pathShape(pathname) {
    return pathname.split("/").map((segment) => segment ? "<SEGMENT>" : "").join("/");
  }
})();
```

## 当前测量结论

以下均为等待用户证据的 `UNKNOWN`，不是实现假设：

```text
PAGE_URL_ORIGIN=UNKNOWN
PAGE_URL_PATH_PATTERN=UNKNOWN
PAGE_QUERY_KEYS=UNKNOWN
PAGE_TITLE_PATTERN=UNKNOWN
SCROLL_OWNER=UNKNOWN
CARD_STABLE_SIGNALS=UNKNOWN
CARD_UNSTABLE_SIGNALS=UNKNOWN
FEED_PATH_PATTERN=UNKNOWN
FEED_ID_SOURCE=UNKNOWN
XSEC_TOKEN_SOURCE=UNKNOWN
XSEC_SOURCE_PRESENT=UNKNOWN
TITLE_SOURCE=UNKNOWN
AUTHOR_SOURCE=UNKNOWN
NOTE_TYPE_SOURCE=UNKNOWN
COVER_SOURCE=UNKNOWN
VIRTUALIZATION_PRESENT=UNKNOWN
DOM_REMOVES_OLD_CARDS=UNKNOWN
CUMULATIVE_MAP_REQUIRED=UNKNOWN
LAZY_LOAD_PRESENT=UNKNOWN
LOAD_TRIGGER=UNKNOWN
END_OF_COLLECTION_SIGNAL=UNKNOWN
RECOMMENDED_STOP_CONDITION=UNKNOWN
SAME_FEED_REAPPEAR=UNKNOWN
TOKEN_PRESENT_AFTER_RERENDER=UNKNOWN
TOKEN_LENGTH_CHANGED=UNKNOWN
USER_VISIBLE_EXPECTED_COUNT=UNKNOWN
MEASURED_CUMULATIVE_UNIQUE_COUNT=UNKNOWN
```

## 安全状态

```text
COOKIE_READ=NO
PRIVATE_API_CALL=NO
AUTH_BYPASS=NO
REAL_TOKEN_COMMITTED=NO
REAL_USER_CONTENT_COMMITTED=NO
```

收到脱敏 probe 输出后，才会补齐事实并判断 TC1A Gate；在此之前不得进入 TC1B。
