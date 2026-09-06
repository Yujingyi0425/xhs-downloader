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

## TC1A-R2 脱敏只读 session probe（使用此版本）

probe 会在当前页面启动一个有上限的只读测量 session：探测滚动容器，小步滚动，等待页面自身更新，使用 session-local SHA-256 记录脱敏 feed identity，最后恢复运行前的滚动位置。token 只输出是否存在及长度，feed id、标题、作者和完整 URL 值均不输出。它不调用网络、不导航、不读取 Cookie/localStorage，不保存数据。

如需将页面 UI 明确显示的数量用于比较，可先把 probe 顶部的 `EXPECTED_COUNT` 改为该数字；它只用于最终比较，不参与停止逻辑。不要把 49 当作默认事实。

```js
(async () => {
  const EXPECTED_COUNT = null;
  const MAX_ROUNDS = 80;
  const MAX_RUNTIME_MS = 90_000;
  const SETTLE_MS = 700;
  const BOTTOM_STABLE_ROUNDS = 4;
  const started = performance.now();
  const initial = new Map();
  const identityHashes = new Map();
  const patternGroups = new Map();
  const cards = new Map();
  const cardObservations = [];
  const tokenHistory = new Map();
  const cumulative = new Set();
  const rounds = [];
  const sessionSalt = crypto.getRandomValues(new Uint8Array(16));
  let owner = null;
  let previousHeight = 0;
  let previousVisible = new Set();
  let bottomStable = 0;
  let oldCardsRemoved = false;
  let lazyLoadObserved = false;
  let bottomConfirmed = false;

  try {
    const candidates = scrollCandidates();
    for (const item of candidates) initial.set(item, item.scrollTop);
    owner = await confirmScrollOwner(candidates);
    if (!owner) throw new Error("未确认滚动容器");
    owner.scrollTop = 0;
    await settle();
    for (let round = 1; round <= MAX_ROUNDS && performance.now() - started < MAX_RUNTIME_MS; round += 1) {
      const snapshot = await scanVisibleCards();
      const heightGrew = snapshot.scroll_height > previousHeight;
      const visible = new Set(snapshot.visible_hashes);
      const newCount = [...visible].filter((id) => !cumulative.has(id)).length;
      for (const id of visible) cumulative.add(id);
      if ([...previousVisible].some((id) => !visible.has(id))) oldCardsRemoved = true;
      if (heightGrew) lazyLoadObserved = true;
      previousVisible = visible;
      previousHeight = snapshot.scroll_height;
      bottomConfirmed = atBottom(owner);
      if (bottomConfirmed && newCount === 0 && !heightGrew) bottomStable += 1;
      else bottomStable = 0;
      rounds.push({ round, raw_candidate_anchors: snapshot.raw_candidate_anchors, visible_normalized_feeds: visible.size, new_normalized_feeds: newCount, cumulative_normalized_unique_feeds: cumulative.size, scroll_top: owner.scrollTop, scroll_height: owner.scrollHeight, loading_signal: snapshot.loading_signal, at_bottom: bottomConfirmed });
      if (bottomStable >= BOTTOM_STABLE_ROUNDS) break;
      const beforeTop = owner.scrollTop;
      owner.scrollTop = Math.min(owner.scrollTop + Math.max(1, owner.clientHeight * 0.7), owner.scrollHeight);
      await settle();
      if (owner.scrollTop === beforeTop && !bottomConfirmed) await settle();
    }
  } finally {
    for (const [item, position] of initial) item.scrollTop = position;
  }

  const cardSignatures = cardObservations;
  console.log(JSON.stringify({
    page: { origin: location.origin, path_pattern: pathShape(location.pathname), query_keys: [...new URL(location.href).searchParams.keys()].sort(), title_present: Boolean(document.title), title_length: document.title.length },
    scroll_owner: owner ? { type: owner === document.scrollingElement ? "document.scrollingElement" : "element", tag: owner.tagName, class_shape: classShape(owner.className) } : null,
    anchor_pattern_groups: [...patternGroups.values()].sort((a, b) => b.count - a.count),
    card_link_signatures: cardSignatures,
    identity_measurement: { board_route_has_feed_id: cardObservations.some((card) => card.board_feed_id_present), board_route_has_xsec_token: cardObservations.some((card) => card.board_token_present), board_explore_alias_match: cardObservations.some((card) => card.board_explore_alias_match), normalized_identity_count: identityHashes.size },
    measurement: { rounds, cumulative_normalized_unique_feeds: cumulative.size, visible_counts: rounds.map((r) => r.visible_normalized_feeds), growth_history: rounds.map((r) => r.new_normalized_feeds), scroll_height_history: rounds.map((r) => r.scroll_height), virtualization_observed: oldCardsRemoved && cumulative.size > Math.max(...rounds.map((r) => r.visible_normalized_feeds), 0), old_cards_removed: oldCardsRemoved, lazy_load_observed: lazyLoadObserved, bottom_confirmed: bottomConfirmed, expected_count: EXPECTED_COUNT, counts_equal: EXPECTED_COUNT == null ? null : cumulative.size === EXPECTED_COUNT },
    metadata_structure: { title_extraction: fieldSignal("title"), author_extraction: fieldSignal("author"), note_type_extraction: fieldSignal("note_type"), cover_extraction: fieldSignal("cover") },
    token_behavior: { xsec_token_presence_rate: tokenHistory.size ? [...tokenHistory.values()].filter((v) => v.latest.present).length / tokenHistory.size : 0, same_feed_reappeared: [...tokenHistory.values()].some((v) => v.seen > 1), token_present_after_rerender: [...tokenHistory.values()].some((v) => v.seen > 1 && v.latest.present), token_length_changed: [...tokenHistory.values()].some((v) => v.seen > 1 && v.first.length !== v.latest.length) },
    safety: { cookie_read: false, local_storage_read: false, network_called: false, private_api_called: false, navigation_performed: false, page_text_returned: false, real_values_returned: false },
  }, null, 2));

  async function scanVisibleCards() {
    const visibleHashes = new Set();
    cards.clear();
    let rawCandidateAnchors = 0;
    for (const anchor of [...document.querySelectorAll("a[href]")]) {
      const parsed = safeUrl(anchor.href);
      if (!parsed) continue;
      recordPattern(parsed);
      const route = routeInfo(parsed);
      if (!route) continue;
      if (route.kind === "board" || route.kind === "explore") rawCandidateAnchors += 1;
      const hash = await hashIdentity(route.feed_id);
      visibleHashes.add(hash);
      identityHashes.set(hash, true);
      const token = route.token;
      const state = tokenHistory.get(hash) ?? { seen: 0, first: { present: Boolean(token), length: token?.length ?? 0 }, latest: { present: Boolean(token), length: token?.length ?? 0 } };
      state.seen += 1; state.latest = { present: Boolean(token), length: token?.length ?? 0 }; tokenHistory.set(hash, state);
      const card = cardFor(anchor);
      const current = cards.get(card) ?? makeCard();
      current.occurrence += 1;
      if (route.kind === "board") { current.board_links += 1; current.board_hashes.add(hash); current.board_feed_id_present = true; current.board_token_present ||= Boolean(token); }
      if (route.kind === "explore") { current.explore_links += 1; current.explore_hashes.add(hash); }
      if (route.kind === "profile") current.profile_links += 1;
      cards.set(card, current);
    }
    cardObservations.push(...[...cards.values()].map((card) => ({ board_links: card.board_links, explore_links: card.explore_links, profile_links: card.profile_links, occurrence: card.occurrence, board_feed_id_present: card.board_feed_id_present, board_token_present: card.board_token_present, board_explore_alias_match: card.board_hashes.some((hash) => card.explore_hashes.has(hash)) })));
    return { visible_hashes: [...visibleHashes], raw_candidate_anchors: rawCandidateAnchors, scroll_height: owner.scrollHeight, loading_signal: Boolean(document.querySelector('[aria-busy="true"], [data-loading="true"], [class*="loading" i]')) };
  }
  function makeCard() { return { board_links: 0, explore_links: 0, profile_links: 0, occurrence: 0, board_hashes: new Set(), explore_hashes: new Set(), board_feed_id_present: false, board_token_present: false }; }
  function cardFor(anchor) { let node = anchor; for (let depth = 0; node && depth < 8; depth += 1, node = node.parentElement) { const links = [...node.querySelectorAll("a[href]")].map((item) => safeUrl(item.href)).filter(Boolean).map(routeInfo).filter(Boolean); if (links.some((item) => item.kind === "board" || item.kind === "explore") && links.length >= 2 && links.length <= 12) return node; } return anchor.parentElement ?? anchor; }
  function routeInfo(parsed) { const parts = parsed.pathname.split("/").filter(Boolean); const token = parsed.searchParams.get("xsec_token"); if (parts[0] === "board" && parts.length >= 3) return { kind: "board", feed_id: parts[2], token }; if (parts[0] === "explore" && parts.length >= 2) return { kind: "explore", feed_id: parts[1], token }; if (parts[0] === "user" && parts[1] === "profile" && parts.length >= 3) return { kind: "profile", feed_id: "", token }; return null; }
  function recordPattern(parsed) { const key = `${pathShape(parsed.pathname)}|${[...parsed.searchParams.keys()].sort().join(",")}`; const current = patternGroups.get(key) ?? { path_pattern: pathShape(parsed.pathname), query_keys: [...parsed.searchParams.keys()].sort(), count: 0, xsec_token_present_count: 0, xsec_token_length_min: null, xsec_token_length_max: null }; current.count += 1; const token = parsed.searchParams.get("xsec_token"); if (token) { current.xsec_token_present_count += 1; current.xsec_token_length_min = current.xsec_token_length_min == null ? token.length : Math.min(current.xsec_token_length_min, token.length); current.xsec_token_length_max = Math.max(current.xsec_token_length_max ?? 0, token.length); } patternGroups.set(key, current); }
  function fieldSignal(kind) { const selectors = { title: '[data-testid*="title" i], [class*="title" i]', author: '[data-testid*="author" i], [class*="author" i]', note_type: 'video, [data-type], [data-note-type], [class*="video" i]', cover: 'img, [data-cover], [class*="cover" i]' }[kind]; const count = [...cards.keys()].reduce((sum, card) => sum + card.querySelectorAll(selectors).length, 0); return { status: count ? "OPTIONAL" : "NOT_FOUND", candidate_signal_count: count }; }
  function scrollCandidates() { const result = []; const roots = [document.scrollingElement, document.body]; for (const item of [...roots, ...document.querySelectorAll("*")]) { if (!item || item.scrollHeight <= item.clientHeight || result.includes(item)) continue; const root = roots.includes(item); if (root || ["auto", "scroll"].includes(getComputedStyle(item).overflowY)) result.push(item); } return result; }
  async function confirmScrollOwner(items) { const ranked = []; for (const item of items) { const before = item.scrollTop; item.scrollTop = Math.min(before + 2, item.scrollHeight); await Promise.resolve(); const delta = item.scrollTop - before; item.scrollTop = before; ranked.push({ item, delta, anchors: item.querySelectorAll("a[href]").length, area: item.clientHeight * item.clientWidth }); } return ranked.filter((x) => x.delta > 0).sort((a, b) => b.anchors - a.anchors || b.area - a.area)[0]?.item ?? null; }
  async function hashIdentity(value) { const bytes = new TextEncoder().encode(`${[...sessionSalt].join(",")}|${value}`); const digest = await crypto.subtle.digest("SHA-256", bytes); return [...new Uint8Array(digest)].slice(0, 8).map((byte) => byte.toString(16).padStart(2, "0")).join(""); }
  function safeUrl(value) { try { const parsed = new URL(value, location.href); return parsed.origin === location.origin ? parsed : null; } catch { return null; } }
  function atBottom(item) { return item.scrollTop + item.clientHeight >= item.scrollHeight - 2; }
  function settle() { return new Promise((resolve) => setTimeout(resolve, SETTLE_MS)); }
  function looksLikeId(value) { return value.length >= 8 || (value.length >= 5 && /\d/.test(value)); }
  function pathShape(pathname) { return pathname.split("/").map((part) => !part ? "" : looksLikeId(part) ? "<ID>" : part).join("/"); }
  function classShape(value) { return typeof value === "string" && value ? value.split(/\s+/).map((part) => /\d{2,}|[a-f0-9]{8,}/i.test(part) ? "<HASH_CLASS>" : "<CLASS>").join(" ") : ""; }
})();
```

该版本会输出 `anchor_pattern_groups`、`card_link_signatures`、`identity_measurement`、逐轮 normalized counts、metadata structure 和 token behavior；输出中不包含真实 feed ID、token、标题、作者、正文或完整 href。

## （已废弃）TC1A-R1 单次/旧 session probe

以下旧 probe 仅保留作历史审计，不得再次运行；它的 identity 逻辑不足以区分卡片内的 board/explore/profile 多链接。

```js
(async () => {
  const EXPECTED_COUNT = null;
  const MAX_ROUNDS = 80;
  const MAX_RUNTIME_MS = 90_000;
  const SETTLE_MS = 700;
  const BOTTOM_STABLE_ROUNDS = 4;
  const started = performance.now();
  const initial = new Map();
  const cumulative = new Map();
  const tokenHistory = new Map();
  const patternGroups = new Map();
  const rounds = [];
  let owner;
  let bottomStable = 0;
  let virtualizationObserved = false;
  let oldCardsRemoved = false;
  let lazyLoadObserved = false;
  let bottomConfirmed = false;
  let previousVisible = new Set();
  let previousHeight = 0;

  try {
    const candidates = scrollCandidates();
    for (const item of candidates) initial.set(item, item.scrollTop);
    owner = await confirmScrollOwner(candidates);
    if (!owner) throw new Error("未确认滚动容器");
    owner.scrollTop = 0;
    await settle();
    for (let round = 1; round <= MAX_ROUNDS && performance.now() - started < MAX_RUNTIME_MS; round += 1) {
      const snapshot = await scan();
      const heightGrew = snapshot.scroll_height > previousHeight;
      const visible = new Set(snapshot.feed_hashes);
      const newCount = [...visible].filter((id) => !cumulative.has(id)).length;
      for (const id of visible) cumulative.set(id, true);
      if ([...previousVisible].some((id) => !visible.has(id))) oldCardsRemoved = true;
      if (visible.size !== previousVisible.size && cumulative.size > visible.size) virtualizationObserved = true;
      if (heightGrew) lazyLoadObserved = true;
      previousVisible = visible;
      previousHeight = snapshot.scroll_height;
      bottomConfirmed = atBottom(owner);
      if (bottomConfirmed && newCount === 0 && !heightGrew) bottomStable += 1;
      else bottomStable = 0;
      rounds.push({
        round, visible_candidate_feeds: visible.size, cumulative_unique_count: cumulative.size,
        new_unique_feeds: newCount, scroll_top: owner.scrollTop, scroll_height: owner.scrollHeight,
        loading_signal: snapshot.loading_signal, at_bottom: bottomConfirmed,
      });
      if (bottomStable >= BOTTOM_STABLE_ROUNDS) break;
      const beforeTop = owner.scrollTop;
      owner.scrollTop = Math.min(owner.scrollTop + Math.max(1, owner.clientHeight * 0.7), owner.scrollHeight);
      await settle();
      if (owner.scrollTop === beforeTop && !bottomConfirmed) await settle();
    }
  } finally {
    for (const [item, position] of initial) item.scrollTop = position;
  }

  console.log(JSON.stringify({
    page: { origin: location.origin, path_pattern: pathShape(location.pathname), query_keys: [...new URL(location.href).searchParams.keys()].sort(), title_present: Boolean(document.title), title_length: document.title.length },
    scroll_owner: owner ? { type: owner === document.scrollingElement ? "document.scrollingElement" : "element", tag: owner.tagName, class_shape: classShape(owner.className) } : null,
    anchor_pattern_groups: [...patternGroups.values()].sort((a, b) => b.count - a.count),
    measurement: { rounds, cumulative_unique_count: cumulative.size, visible_counts: rounds.map((r) => r.visible_candidate_feeds), growth_history: rounds.map((r) => r.new_unique_feeds), scroll_height_history: rounds.map((r) => r.scroll_height), virtualization_observed: virtualizationObserved, old_cards_removed: oldCardsRemoved, lazy_load_observed: lazyLoadObserved, bottom_confirmed: bottomConfirmed, expected_count: EXPECTED_COUNT, counts_equal: EXPECTED_COUNT == null ? null : cumulative.size === EXPECTED_COUNT },
    token_behavior: { xsec_token_presence_rate: tokenHistory.size ? [...tokenHistory.values()].filter((v) => v.latest.present).length / tokenHistory.size : 0, same_feed_reappeared: [...tokenHistory.values()].some((v) => v.seen > 1), token_present_after_rerender: [...tokenHistory.values()].some((v) => v.seen > 1 && v.latest.present), token_length_changed: [...tokenHistory.values()].some((v) => v.seen > 1 && v.first.length !== v.latest.length) },
    safety: { cookie_read: false, local_storage_read: false, network_called: false, private_api_called: false, navigation_performed: false, page_text_returned: false, real_values_returned: false },
  }, null, 2));

  async function scan() {
    const hashes = [];
    let loading = Boolean(document.querySelector('[aria-busy="true"], [data-loading="true"], [class*="loading" i]'));
    for (const anchor of [...document.querySelectorAll("a[href]")]) {
      const parsed = safeUrl(anchor.href); if (!parsed) continue;
      recordPattern(parsed);
      const token = parsed.searchParams.get("xsec_token");
      const id = candidateId(parsed); if (!id || (!token && parsed.searchParams.size === 0)) continue;
      const hash = await idHash(id); hashes.push(hash);
      const state = tokenHistory.get(hash) ?? { seen: 0, first: { present: Boolean(token), length: token?.length ?? 0 }, latest: { present: Boolean(token), length: token?.length ?? 0 } };
      state.seen += 1; state.latest = { present: Boolean(token), length: token?.length ?? 0 }; tokenHistory.set(hash, state);
    }
    return { feed_hashes: [...new Set(hashes)], scroll_height: owner.scrollHeight, loading_signal: loading };
  }
  function scrollCandidates() { const result = []; const roots = [document.scrollingElement, document.body]; const all = [...roots, ...document.querySelectorAll("*")]; for (const item of all) { if (!item || item.scrollHeight <= item.clientHeight || result.includes(item)) continue; const root = roots.includes(item); if (root || ["auto", "scroll"].includes(getComputedStyle(item).overflowY)) result.push(item); } return result; }
  async function confirmScrollOwner(items) { const ranked = []; for (const item of items) { const before = item.scrollTop; item.scrollTop = Math.min(before + 2, item.scrollHeight); await Promise.resolve(); const delta = item.scrollTop - before; item.scrollTop = before; ranked.push({ item, delta, area: item.clientHeight * item.clientWidth, anchors: item.querySelectorAll("a[href]").length }); } return ranked.filter((x) => x.delta > 0).sort((a, b) => b.anchors - a.anchors || b.area - a.area)[0]?.item ?? null; }
  function safeUrl(value) { try { const parsed = new URL(value, location.href); return parsed.origin === location.origin ? parsed : null; } catch { return null; } }
  function recordPattern(parsed) { const key = `${pathShape(parsed.pathname)}|${[...parsed.searchParams.keys()].sort().join(",")}`; const current = patternGroups.get(key) ?? { path_pattern: pathShape(parsed.pathname), query_keys: [...parsed.searchParams.keys()].sort(), count: 0, xsec_token_present_count: 0, xsec_token_length_min: null, xsec_token_length_max: null }; current.count += 1; const token = parsed.searchParams.get("xsec_token"); if (token) { current.xsec_token_present_count += 1; current.xsec_token_length_min = current.xsec_token_length_min == null ? token.length : Math.min(current.xsec_token_length_min, token.length); current.xsec_token_length_max = Math.max(current.xsec_token_length_max ?? 0, token.length); } patternGroups.set(key, current); }
  function candidateId(parsed) { const parts = parsed.pathname.split("/").filter(Boolean); const last = parts.at(-1); return last && (parsed.searchParams.has("xsec_token") || looksLikeId(last)) ? `${pathShape(parsed.pathname)}|${last}` : null; }
  function looksLikeId(value) { return value.length >= 8 || (value.length >= 5 && /\d/.test(value)); }
  async function idHash(value) { const bytes = new TextEncoder().encode(value); const digest = await crypto.subtle.digest("SHA-256", bytes); return [...new Uint8Array(digest)].slice(0, 8).map((byte) => byte.toString(16).padStart(2, "0")).join(""); }
  function atBottom(item) { return item.scrollTop + item.clientHeight >= item.scrollHeight - 2; }
  function settle() { return new Promise((resolve) => setTimeout(resolve, SETTLE_MS)); }
  function pathShape(pathname) { return pathname.split("/").map((part) => !part ? "" : looksLikeId(part) ? "<ID>" : part).join("/"); }
  function classShape(value) { return typeof value === "string" && value ? value.split(/\s+/).map((part) => /\d{2,}|[a-f0-9]{8,}/i.test(part) ? "<HASH_CLASS>" : "<CLASS>").join(" ") : ""; }
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

## TC1A-R1 Checkpoint

```text
PHASE=TC1A-R1
STATUS=HOLD_USER_EVIDENCE_REQUIRED
BASELINE_COMMIT=9f48b8cbaaebb1c88cb8644f353a027938e663d8
SOURCE_COMMIT=<待提交>
PROBE_SINGLE_SNAPSHOT_ONLY=NO
INNER_SCROLL_CONTAINER_DISCOVERY=SUPPORTED
VIRTUALIZATION_MEASUREMENT=SUPPORTED
LAZY_LOAD_MEASUREMENT=SUPPORTED
CUMULATIVE_UNIQUE_MEASUREMENT=SUPPORTED
TOKEN_REFRESH_MEASUREMENT=SUPPORTED
SENSITIVE_VALUE_OUTPUT=NO
FILES_CHANGED=TC1A_REAL_PAGE_MEASUREMENT.md
TEST_RESULT=仅文档/静态范围检查；未运行真实页面测量
NEXT_PHASE=TC1A-EVIDENCE
NEXT_PHASE_AUTHORIZED=NO
```

## TC1A-R2 Checkpoint

```text
PHASE=TC1A-R2
STATUS=HOLD_USER_EVIDENCE_REQUIRED
BASELINE_COMMIT=9f48b8cbaaebb1c88cb8644f353a027938e663d8
SOURCE_COMMIT=<待提交>
RAW_ANCHOR_OVERCOUNT_CONFIRMED=SUPPORTED
BOARD_EXPLORE_ALIAS_MEASUREMENT_SUPPORTED=SUPPORTED
NORMALIZED_FEED_IDENTITY_SUPPORTED=SUPPORTED
CARD_LEVEL_LINK_SIGNATURE_SUPPORTED=SUPPORTED
EXPECTED_COUNT_INPUT_SUPPORTED=SUPPORTED
TITLE_STRUCTURE_MEASUREMENT_SUPPORTED=SUPPORTED
AUTHOR_STRUCTURE_MEASUREMENT_SUPPORTED=SUPPORTED
NOTE_TYPE_STRUCTURE_MEASUREMENT_SUPPORTED=SUPPORTED
COVER_STRUCTURE_MEASUREMENT_SUPPORTED=SUPPORTED
SENSITIVE_VALUE_OUTPUT=NO
FILES_CHANGED=TC1A_REAL_PAGE_MEASUREMENT.md
TEST_RESULT=仅文档/静态范围检查；未运行真实页面测量
NEXT_PHASE=TC1A-FINAL-EVIDENCE
NEXT_PHASE_AUTHORIZED=NO
```
