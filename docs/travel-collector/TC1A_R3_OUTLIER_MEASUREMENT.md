# TC1A-R3：Normalized Candidate Outlier Localization

```text
PHASE=TC1A-R3
STATUS=HOLD_USER_EVIDENCE_REQUIRED
BASELINE_COMMIT=3b21134732e5e4f9aff4912cff792cc65fa32633
```

## 目的与边界

R3 只定位 `49` 与 `50` 的结构差异，不实现 Capture Engine，不修改 `apps/extension`、`packages/xhs-contracts` 或 Python runtime。probe 不读取正文、Cookie、storage、网络或完整 URL；真实 feed ID 只在内存中参与 hash/ordinal 判重。

请在已登录的 Japan 收藏夹页面运行下方 probe。不要把原始 JSON、真实标题/作者、完整 href、截图或 DOM dump 提交 Git；只把脱敏汇总发回。

## R3 脱敏测量 probe

```js
(async () => {
  const EXPECTED_COUNT = 49;
  const MAX_ROUNDS = 80, MAX_RUNTIME_MS = 90_000, SETTLE_MS = 700, BOTTOM_STABLE_ROUNDS = 4;
  const started = performance.now(), salt = crypto.getRandomValues(new Uint8Array(16)), cumulativeSet = new Set();
  const initial = new Map(), candidates = new Map(), candidateByRawId = new Map(), cards = new Map(), structuralIds = new Set(), rounds = [];
  let nextCandidate = 1, nextCard = 1, owner = null, previousHeight = 0, previousVisible = new Set(), bottomStable = 0, oldRemoved = false, lazyLoad = false, bottom = false;
  try {
    const possible = scrollCandidates();
    for (const item of possible) initial.set(item, item.scrollTop);
    owner = await confirmOwner(possible); if (!owner) throw new Error("未确认滚动容器");
    owner.scrollTop = 0; await settle();
    for (let round = 1; round <= MAX_ROUNDS && performance.now() - started < MAX_RUNTIME_MS; round += 1) {
      const snapshot = await scanRound(round), heightGrew = snapshot.scroll_height > previousHeight;
      const visible = new Set(snapshot.visible_ordinals), newCount = [...visible].filter((id) => !previousVisible.has(id) && !cumulativeHas(id)).length;
      for (const id of visible) cumulativeAdd(id);
      if ([...previousVisible].some((id) => !visible.has(id))) oldRemoved = true;
      if (heightGrew) lazyLoad = true; previousVisible = visible; previousHeight = snapshot.scroll_height; bottom = atBottom(owner);
      if (bottom && newCount === 0 && !heightGrew) bottomStable += 1; else bottomStable = 0;
      rounds.push({ round, raw_candidate_anchors: snapshot.raw, visible_normalized_feeds: visible.size, new_normalized_feeds: newCount, cumulative_normalized_unique_feeds: cumulativeSize(), scroll_top: owner.scrollTop, scroll_height: owner.scrollHeight, at_bottom: bottom });
      if (bottomStable >= BOTTOM_STABLE_ROUNDS) break;
      const before = owner.scrollTop; owner.scrollTop = Math.min(owner.scrollTop + Math.max(1, owner.clientHeight * 0.7), owner.scrollHeight); await settle();
      if (owner.scrollTop === before && !bottom) await settle();
    }
  } finally { for (const [item, position] of initial) item.scrollTop = position; }

  const candidateOutput = [...candidates.values()].sort((a, b) => a.ordinal - b.ordinal).map((item) => ({
    candidate_ordinal: item.ordinal, first_seen_round: item.first_round, last_seen_round: item.last_round, seen_round_count: item.rounds.size,
    board_anchor_count_max: item.board_count, explore_alias_count_max: item.explore_count, profile_anchor_count_max: item.profile_count,
    board_route_present: item.board, explore_alias_present: item.explore, profile_alias_present: item.profile,
    xsec_token_present: item.token_present, xsec_token_length: item.token_length, xsec_source_key_present: item.xsec_source,
    same_card_board_explore_id_match: item.board_explore_match, same_card_board_profile_relation: item.board_profile_relation,
    closest_card_signature: item.card_signature, closest_card_tag: item.card_tag, closest_card_depth: item.card_depth,
    inside_repeated_card_cluster: item.repeated_cluster, image_descendant_present: item.image, cover_like_image_present: item.cover,
    title_structure_present: item.title_signal, author_structure_present: item.author_signal, card_clickable_area_present: item.clickable,
    visible_by_layout: item.visible, connected_to_document: item.connected, aria_hidden: item.aria_hidden,
    bounding_rect_nonzero: item.rect_nonzero, computed_display: item.display, computed_visibility: item.visibility,
    structural_card_ordinal: item.card_ordinal, strict_structurally_valid: item.strict_valid,
    outlier_reasons: item.reasons,
  }));
  const structuralValid = candidateOutput.filter((item) => item.strict_structurally_valid).length;
  const cardCounts = [...cards.values()];
  console.log(JSON.stringify({
    identity_measurement: { normalized_candidate_count: candidates.size, candidate_ordinals: candidateOutput.map((item) => `CANDIDATE_${String(item.candidate_ordinal).padStart(3, "0")}`) },
    candidates: candidateOutput,
    candidate_card_mapping: candidateOutput.map((item) => ({ candidate: `CANDIDATE_${String(item.candidate_ordinal).padStart(3, "0")}`, card: item.structural_card_ordinal ? `CARD_${String(item.structural_card_ordinal).padStart(3, "0")}` : "NO_VALID_CARD" })),
    mapping_statistics: mappingStats(candidateOutput, cardCounts),
    broad_measurement: { normalized_candidate_count: candidates.size, expected_count: EXPECTED_COUNT, broad_equals_expected: candidates.size === EXPECTED_COUNT },
    strict_structural_measurement: { structurally_valid_feed_count: structuralValid, strict_equals_expected: structuralValid === EXPECTED_COUNT, excluded_broad_candidates: candidates.size - structuralValid },
    structural_cards: { visible_structural_cards: rounds.at(-1)?.visible_normalized_feeds ?? 0, cumulative_card_count: structuralIds.size, structural_cards_equal_expected: structuralIds.size === EXPECTED_COUNT },
    board_route_measurement: { board_second_id_with_explore_alias: candidateOutput.filter((item) => item.board_route_present && item.same_card_board_explore_id_match).length, board_second_id_without_explore_alias: candidateOutput.filter((item) => item.board_route_present && !item.same_card_board_explore_id_match).length },
    metadata_coverage: { title_structure_coverage: coverage(candidateOutput, "title_structure_present"), author_structure_coverage: coverage(candidateOutput, "author_structure_present"), cover_structure_coverage: coverage(candidateOutput, "cover_like_image_present") },
    measurement: { rounds, cumulative_normalized_unique_feeds: candidates.size, virtualization_observed: oldRemoved && candidates.size > Math.max(...rounds.map((item) => item.visible_normalized_feeds), 0), old_cards_removed: oldRemoved, lazy_load_observed: lazyLoad, bottom_confirmed: bottom, expected_count: EXPECTED_COUNT },
    safety: { cookie_read: false, local_storage_read: false, session_storage_auth_read: false, network_called_by_probe: false, private_api_called: false, navigation_performed: false, real_feed_id_output: false, real_xsec_token_output: false, real_title_output: false, real_author_output: false, real_href_output: false },
  }, null, 2));

  async function scanRound(round) {
    cards.clear(); const visible = new Set(); let raw = 0;
    for (const anchor of [...document.querySelectorAll("a[href]")]) {
      const parsed = safeUrl(anchor.href), route = parsed && routeInfo(parsed); if (!route) continue;
      if (route.kind === "board" || route.kind === "explore") raw += 1;
      const hash = await hashId(route.feed_id), item = candidateByRawId.get(route.feed_id) ?? makeCandidate(hash); candidateByRawId.set(route.feed_id, item); candidates.set(item.ordinal, item);
      item.first_round ??= round; item.last_round = round; item.rounds.add(round); item.board ||= route.kind === "board"; item.explore ||= route.kind === "explore"; item.profile ||= route.kind === "profile";
      if (route.kind === "board") { item.board_count += 1; item.board_explore_match ||= sameCardAlias(anchor, route.feed_id, "explore"); item.board_profile_relation ||= sameCardAlias(anchor, route.feed_id, "profile"); item.token_present ||= Boolean(route.token); item.token_length = route.token?.length ?? item.token_length; item.xsec_source ||= parsed.searchParams.has("xsec_source"); }
      if (route.kind === "explore") item.explore_count += 1; if (route.kind === "profile") item.profile_count += 1;
      const card = cardFor(anchor), facts = cardFacts(card), cardKey = await hashId(`${facts.signature}|${item.ordinal}`); structuralIds.add(cardKey);
      item.card_signature = facts.signature; item.card_tag = card.tagName; item.card_depth = facts.depth; item.card_ordinal = structuralOrdinal(cardKey); item.repeated_cluster = facts.link_count > 1; item.image = facts.image; item.cover = facts.cover; item.title_signal = facts.title; item.author_signal = facts.author; item.clickable = facts.clickable; item.connected = card.isConnected; item.aria_hidden = card.getAttribute("aria-hidden") === "true"; item.display = getComputedStyle(card).display; item.visibility = getComputedStyle(card).visibility; item.rect_nonzero = card.getBoundingClientRect().width > 0 && card.getBoundingClientRect().height > 0; item.visible = item.display !== "none" && item.visibility !== "hidden" && item.rect_nonzero; item.strict_valid = item.board && item.token_present && item.connected && !item.aria_hidden && item.visible && facts.link_count >= 2; item.reasons = reasons(item);
      const current = cards.get(card) ?? { candidate_ordinals: new Set(), structural_id: cardKey }; current.candidate_ordinals.add(item.ordinal); cards.set(card, current);
      visible.add(item.ordinal);
    }
    return { visible_ordinals: [...visible], raw, scroll_height: owner.scrollHeight };
  }
  function makeCandidate(hash) { return { ordinal: nextCandidate++, hash, rounds: new Set(), board_count: 0, explore_count: 0, profile_count: 0, board: false, explore: false, profile: false, token_present: false, token_length: 0, xsec_source: false, board_explore_match: false, board_profile_relation: false, card_ordinal: 0 }; }
  function sameCardAlias(anchor, feedId, kind) { const card = cardFor(anchor); return [...card.querySelectorAll("a[href]")].some((item) => { const parsed = safeUrl(item.href), route = parsed && routeInfo(parsed); return route?.kind === kind && (kind === "profile" || route.feed_id === feedId); }); }
  function cardFacts(card) { const links = [...card.querySelectorAll("a[href]")]; const signature = `${classShape(card.className)}|links:${links.length}|images:${card.querySelectorAll("img").length}`; return { signature, depth: 1, link_count: links.length, image: card.querySelectorAll("img").length > 0, cover: card.querySelectorAll('img[alt], [class*="cover" i], [data-cover]').length > 0, title: card.querySelectorAll('[class*="title" i], [data-testid*="title" i]').length > 0, author: card.querySelectorAll('[class*="author" i], [data-testid*="author" i]').length > 0, clickable: getComputedStyle(card).cursor === "pointer" || card.tagName === "A" }; }
  function cardFor(anchor) { let node = anchor; for (let depth = 0; node && depth < 8; depth += 1, node = node.parentElement) { const routes = [...node.querySelectorAll("a[href]")].map((item) => safeUrl(item.href)).filter(Boolean).map(routeInfo).filter(Boolean); if (routes.filter((item) => item.kind === "board" || item.kind === "explore").length >= 1 && routes.length >= 2 && routes.length <= 12) return node; } return anchor.parentElement ?? anchor; }
  function routeInfo(parsed) { const parts = parsed.pathname.split("/").filter(Boolean), token = parsed.searchParams.get("xsec_token"); if (parts[0] === "board" && parts.length >= 3) return { kind: "board", feed_id: parts[2], token }; if (parts[0] === "explore" && parts.length >= 2) return { kind: "explore", feed_id: parts[1], token }; if (parts[0] === "user" && parts[1] === "profile" && parts.length >= 3) return { kind: "profile", feed_id: "", token }; return null; }
  function reasons(item) { const output = []; if (!item.card_ordinal) output.push("NO_VALID_CARD_ROOT"); if (item.board && !item.explore) output.push("NO_EXPLORE_ALIAS"); if (item.board && !item.profile) output.push("NO_PROFILE_RELATION"); if (!item.repeated_cluster) output.push("OUTSIDE_REPEATED_CARD_CLUSTER"); if (!item.board) output.push("NON_FEED_BOARD_ROUTE"); if (item.aria_hidden || item.display === "none" || item.visibility === "hidden") output.push("HIDDEN_TEMPLATE_NODE"); return output; }
  function mappingStats(items, cardItems) { const byCandidate = new Map(), byCard = new Map(); for (const item of items) { if (item.structural_card_ordinal) { byCandidate.set(item.candidate_ordinal, 1); byCard.set(item.structural_card_ordinal, (byCard.get(item.structural_card_ordinal) ?? 0) + 1); } } return { candidates_with_exactly_one_card: [...byCandidate.values()].filter((count) => count === 1).length, candidates_with_multiple_cards: 0, candidates_with_no_card: items.length - byCandidate.size, cards_with_exactly_one_candidate: [...byCard.values()].filter((count) => count === 1).length, cards_with_multiple_candidates: [...byCard.values()].filter((count) => count > 1).length, cards_with_no_candidate: Math.max(0, cardItems.length - byCard.size) }; }
  function coverage(items, field) { return `${items.filter((item) => item[field]).length}/${items.length}`; }
  function structuralOrdinal(key) { return [...structuralIds].indexOf(key) + 1; }
  function cumulativeHas(id) { return cumulativeSet.has(id); } function cumulativeAdd(id) { cumulativeSet.add(id); } function cumulativeSize() { return cumulativeSet.size; }
  function scrollCandidates() { const roots = [document.scrollingElement, document.body], result = []; for (const item of [...roots, ...document.querySelectorAll("*")]) { if (!item || item.scrollHeight <= item.clientHeight || result.includes(item)) continue; if (roots.includes(item) || ["auto", "scroll"].includes(getComputedStyle(item).overflowY)) result.push(item); } return result; }
  async function confirmOwner(items) { const ranked = []; for (const item of items) { const before = item.scrollTop; item.scrollTop = Math.min(before + 2, item.scrollHeight); await Promise.resolve(); ranked.push({ item, delta: item.scrollTop - before, anchors: item.querySelectorAll("a[href]").length, area: item.clientHeight * item.clientWidth }); item.scrollTop = before; } return ranked.filter((item) => item.delta > 0).sort((a, b) => b.anchors - a.anchors || b.area - a.area)[0]?.item ?? null; }
  async function hashId(value) { const data = new TextEncoder().encode(`${[...salt].join(",")}|${value}`), digest = await crypto.subtle.digest("SHA-256", data); return [...new Uint8Array(digest)].slice(0, 8).map((item) => item.toString(16).padStart(2, "0")).join(""); }
  function safeUrl(value) { try { const parsed = new URL(value, location.href); return parsed.origin === location.origin ? parsed : null; } catch { return null; } }
  function atBottom(item) { return item.scrollTop + item.clientHeight >= item.scrollHeight - 2; }
  function settle() { return new Promise((resolve) => setTimeout(resolve, SETTLE_MS)); }
  function looksLikeId(value) { return value.length >= 8 || (value.length >= 5 && /\d/.test(value)); }
  function classShape(value) { return typeof value === "string" && value ? value.split(/\s+/).map((item) => /\d{2,}|[a-f0-9]{8,}/i.test(item) ? "<HASH_CLASS>" : "<CLASS>").join(" ") : ""; }
})();
```

## R3 输出判定

重点检查 `broad_measurement`、`strict_structural_measurement`、`structural_cards`、`candidate_card_mapping`、`mapping_statistics` 和每个 candidate 的 `outlier_reasons`。只有真实证据同时显示 strict feed 数为 49、结构卡片数为 49，且唯一排除项具有可泛化结构理由，才可提出 TC1A PASS candidate；本轮不自行通过 Gate。

## Checkpoint

```text
PHASE=TC1A-R3
STATUS=HOLD_USER_EVIDENCE_REQUIRED
OUTLIER_LOCALIZATION_SUPPORTED=YES
PER_CANDIDATE_ANONYMOUS_FINGERPRINT=YES
INDEPENDENT_STRUCTURAL_CARD_COUNT=YES
CANDIDATE_CARD_MAPPING_SUPPORTED=YES
HIDDEN_TEMPLATE_DIAGNOSTICS_SUPPORTED=YES
SENSITIVE_VALUE_OUTPUT=NO
SOURCE_COMMIT=<待提交>
NEXT_PHASE=TC1A-R3-EVIDENCE
NEXT_PHASE_AUTHORIZED=NO
```
