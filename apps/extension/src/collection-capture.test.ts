import { describe, expect, it } from "vitest";
import { detectCollectionPage, parseCollectionRoute } from "./collection-page-detection";
import { parseVisibleCollectionFeeds, type CollectionFeedCandidate } from "./collection-feed-parser";
import { createCollectionCaptureState, mergeVisibleCollectionFeeds } from "./collection-capture-state";
import { advanceCollectionScrollProgress, decideCollectionScroll, type CollectionScrollProgressState } from "./collection-scroll-policy";

const boardId = "japan-board";

function pageWith(...cards: string[]): Document {
  const page = document.implementation.createHTMLDocument();
  page.body.innerHTML = cards.join("");
  return page;
}

function card(feedId: string, token = `token-${feedId}`, options: { explore?: string; source?: string; board?: string; cover?: boolean } = {}): string {
  const board = options.board ?? boardId;
  const explore = options.explore ?? feedId;
  return `<article class="feed-card"><a href="/board/${board}/${feedId}?xsec_token=${token}${options.source ? `&xsec_source=${options.source}` : ""}">board</a><a href="/explore/${explore}">explore</a>${options.cover === false ? "" : "<img src='cover.jpg'>"}</article>`;
}

function candidate(feedId: string, token = `token-${feedId}`): CollectionFeedCandidate {
  return { feedId, xsecToken: token };
}

const scroll = (overrides: Partial<Parameters<typeof decideCollectionScroll>[0]> = {}) => ({
  scrollTop: 0, scrollHeight: 1000, clientHeight: 500, newUniqueCount: 1, loading: false,
  round: 1, elapsedMs: 100, maxRounds: 20, maxRuntimeMs: 10_000,
  requiredBottomStableRounds: 3, progress: stableProgress(0), ...overrides,
});

function stableProgress(bottomStableRounds: number): CollectionScrollProgressState {
  return { previousScrollTop: 500, previousScrollHeight: 1000, previousUniqueCount: 0, bottomStableRounds };
}

describe("TC1B collection capture engine", () => {
  it("A01 parses 10 feeds", () => expect(parseVisibleCollectionFeeds(pageWith(...Array.from({ length: 10 }, (_, i) => card(`f${i}`))), boardId)).toHaveLength(10));
  it("A02 parses 49 feeds", () => expect(parseVisibleCollectionFeeds(pageWith(...Array.from({ length: 49 }, (_, i) => card(`f${i}`))), boardId)).toHaveLength(49));
  it("A03 parses 500 feeds", () => expect(parseVisibleCollectionFeeds(pageWith(...Array.from({ length: 500 }, (_, i) => card(`f${i}`))), boardId)).toHaveLength(500));
  it("A04 detects collection page", () => expect(detectCollectionPage(`/board/${boardId}`)).toEqual({ isCollectionPage: true, boardId }));
  it("A05 accepts board and matching explore alias", () => expect(parseVisibleCollectionFeeds(pageWith(card("f1")), boardId)[0].feedId).toBe("f1"));
  it("A06 excludes profile-only links", () => expect(parseVisibleCollectionFeeds(pageWith(`<article><a href='/user/profile/u1'>profile</a></article>`), boardId)).toEqual([]));
  it("A07 excludes the exact profile-heavy outlier", () => expect(parseVisibleCollectionFeeds(pageWith(`<article>${"<a href='/user/profile/u'>profile</a>".repeat(30)}</article>`), boardId)).toEqual([]));
  it("A08 is duplicate-free after rerender", () => expect(mergeVisibleCollectionFeeds(mergeVisibleCollectionFeeds(createCollectionCaptureState(), [candidate("f1")]), [candidate("f1")]).items.size).toBe(1));
  it("A09 keeps cumulative count monotonic", () => {
    const first = mergeVisibleCollectionFeeds(createCollectionCaptureState(), [candidate("f1"), candidate("f2")]);
    const second = mergeVisibleCollectionFeeds(first, [candidate("f2"), candidate("f3")]);
    expect(second.items.size).toBeGreaterThanOrEqual(first.items.size);
  });
  it("A10 continues before bottom", () => expect(decideCollectionScroll(scroll())).toBe("continue"));
  it("A11 uses latest nonempty token", () => expect(mergeVisibleCollectionFeeds(createCollectionCaptureState(), [candidate("f1", "new")]).items.get("f1")?.xsecToken).toBe("new"));
  it("A12 never overwrites token with empty value", () => expect(mergeVisibleCollectionFeeds(mergeVisibleCollectionFeeds(createCollectionCaptureState(), [candidate("f1", "old")]), [{ ...candidate("f1"), xsecToken: "" }]).items.get("f1")?.xsecToken).toBe("old"));
  it("A13 accepts missing title without metadata selectors", () => expect(parseVisibleCollectionFeeds(pageWith(card("f1", "t")), boardId)[0]).toEqual(candidate("f1", "t")));
  it("A14 accepts missing author", () => expect(parseVisibleCollectionFeeds(pageWith(card("f1")), boardId)).toHaveLength(1));
  it("A15 accepts missing cover", () => expect(parseVisibleCollectionFeeds(pageWith(card("f1", "t", { cover: false })), boardId)).toHaveLength(1));
  it("A16 does not require note type", () => expect(parseVisibleCollectionFeeds(pageWith(card("f1")), boardId)[0].feedId).toBe("f1"));
  it("A17 excludes a different board", () => expect(parseVisibleCollectionFeeds(pageWith(card("f1", "t", { board: "other" })), boardId)).toEqual([]));
  it("A18 excludes an alias mismatch", () => expect(parseVisibleCollectionFeeds(pageWith(card("f1", "t", { explore: "other" })), boardId)).toEqual([]));
  it("A19 excludes a missing token", () => expect(parseVisibleCollectionFeeds(pageWith(card("f1", "", {})), boardId)).toEqual([]));
  it("A20 accepts a missing xsec source", () => expect(parseVisibleCollectionFeeds(pageWith(card("f1", "t", { source: "" })), boardId)).toHaveLength(1));
  it("A21 completes after stable bottom", () => expect(decideCollectionScroll(scroll({ scrollTop: 500, newUniqueCount: 0, progress: stableProgress(3) }))).toBe("done"));
  it("A22 waits at bottom while loading", () => expect(decideCollectionScroll(scroll({ scrollTop: 500, loading: true }))).toBe("wait"));
  it("A22b waits at bottom when new items arrive", () => expect(decideCollectionScroll(scroll({ scrollTop: 500, newUniqueCount: 1 }))).toBe("wait"));
  it("A23 aborts at max rounds", () => expect(decideCollectionScroll(scroll({ round: 20 }))).toBe("abort_max_rounds"));
  it("A24 aborts at max runtime", () => expect(decideCollectionScroll(scroll({ elapsedMs: 10_000 }))).toBe("abort_timeout"));
  it("A25 tolerates DOM order changes", () => {
    const state = mergeVisibleCollectionFeeds(createCollectionCaptureState(), [candidate("f1"), candidate("f2")]);
    const next = mergeVisibleCollectionFeeds(state, [candidate("f2"), candidate("f1")]);
    expect([...next.items.keys()]).toEqual(["f1", "f2"]);
  });
  it("A26 deduplicates multiple board anchors and aliases", () => {
    const html = `<article class='feed-card'><a href='/board/${boardId}/f1?xsec_token=t1'>one</a><a href='/board/${boardId}/f1?xsec_token=t2'>two</a><a href='/explore/f1'>explore</a></article>`;
    expect(parseVisibleCollectionFeeds(pageWith(html), boardId)).toHaveLength(1);
  });
  it("keeps route parsing free of token errors", () => expect(parseCollectionRoute("%bad").kind).toBe("other"));
  it("R01 rejects an external origin", () => expect(parseCollectionRoute("https://example.com/board/a/b?xsec_token=t&xsec_source=s").kind).toBe("other"));
  it("R02 rejects an extra board path segment", () => expect(parseCollectionRoute("/board/a/b/extra?xsec_token=t&xsec_source=s").kind).toBe("other"));
  it("R03 rejects an extra explore path segment", () => expect(parseCollectionRoute("/explore/id/extra").kind).toBe("other"));
  it("R04 accepts a valid card with many irrelevant links", () => {
    const extra = "<a href='/search_result/irrelevant'>x</a>".repeat(40);
    expect(parseVisibleCollectionFeeds(pageWith(card("f1") .replace("</article>", `${extra}</article>`)), boardId)).toHaveLength(1);
  });
  it("R05 refreshes token A to nonempty B", () => {
    const state = mergeVisibleCollectionFeeds(createCollectionCaptureState(), [candidate("f1", "A")]);
    expect(mergeVisibleCollectionFeeds(state, [candidate("f1", "B")]).items.get("f1")?.xsecToken).toBe("B");
  });
  it("R06 preserves token A after empty refresh", () => {
    const state = mergeVisibleCollectionFeeds(createCollectionCaptureState(), [candidate("f1", "A")]);
    expect(mergeVisibleCollectionFeeds(state, [{ ...candidate("f1"), xsecToken: "" }]).items.get("f1")?.xsecToken).toBe("A");
  });
  it("R07 retains virtualized feeds across multiple rounds", () => {
    let state = createCollectionCaptureState();
    for (const visibleCount of [31, 31, 26, 21, 15, 6]) {
      state = mergeVisibleCollectionFeeds(state, Array.from({ length: visibleCount }, (_, i) => candidate(`f${i}`)));
    }
    expect(state.items).toHaveProperty("size", 31);
  });
  it("R08 resets stability when scrollHeight grows", () => {
    const first = advanceCollectionScrollProgress(stableProgress(0), { scrollTop: 500, scrollHeight: 1000, clientHeight: 500, uniqueCount: 10, loading: false });
    const stable = advanceCollectionScrollProgress(first, { scrollTop: 500, scrollHeight: 1000, clientHeight: 500, uniqueCount: 10, loading: false });
    expect(advanceCollectionScrollProgress(stable, { scrollTop: 500, scrollHeight: 1100, clientHeight: 500, uniqueCount: 10, loading: false }).bottomStableRounds).toBe(0);
  });
  it("R09 resets stability when scrollTop moves", () => expect(advanceCollectionScrollProgress(stableProgress(2), { scrollTop: 400, scrollHeight: 1000, clientHeight: 500, uniqueCount: 0, loading: false }).bottomStableRounds).toBe(0));
  it("R10 resets stability when unique count grows", () => expect(advanceCollectionScrollProgress(stableProgress(2), { scrollTop: 500, scrollHeight: 1000, clientHeight: 500, uniqueCount: 1, loading: false }).bottomStableRounds).toBe(0));
  it("R11 resets stability while loading", () => expect(advanceCollectionScrollProgress(stableProgress(2), { scrollTop: 500, scrollHeight: 1000, clientHeight: 500, uniqueCount: 0, loading: true }).bottomStableRounds).toBe(0));
  it("R12 increments only fully stable bottom rounds", () => expect(advanceCollectionScrollProgress(stableProgress(2), { scrollTop: 500, scrollHeight: 1000, clientHeight: 500, uniqueCount: 0, loading: false }).bottomStableRounds).toBe(3));
  it("R13 reaches DONE after required stable rounds", () => expect(decideCollectionScroll(scroll({ scrollTop: 500, newUniqueCount: 0, progress: stableProgress(3) }))).toBe("done"));
  it("R14 does not accept EXPECTED_COUNT as a stop input", () => expect(decideCollectionScroll(scroll({ scrollTop: 500, newUniqueCount: 0, progress: stableProgress(0) }))).toBe("wait"));
  it("R1-01 accepts board token with no source and matching alias", () => expect(parseVisibleCollectionFeeds(pageWith(card("f1", "token")), boardId)).toHaveLength(1));
  it("R1-02 accepts source-free board route", () => expect(parseVisibleCollectionFeeds(pageWith(card("f1", "token", { source: "" })), boardId)[0]).toMatchObject({ feedId: "f1", xsecToken: "token" }));
  it("R1-03 deduplicates duplicate source-free board anchors", () => expect(parseVisibleCollectionFeeds(pageWith(`<article><a href='/board/${boardId}/f1?xsec_token=t1'>a</a><a href='/board/${boardId}/f1?xsec_token=t2'>b</a><a href='/explore/f1'>e</a></article>`), boardId)).toHaveLength(1));
  it("R1-04 captures 30 source-free feeds", () => expect(parseVisibleCollectionFeeds(pageWith(...Array.from({ length: 30 }, (_, i) => card(`f${i}`))), boardId)).toHaveLength(30));
  it("R1-05 captures 49 source-free feeds", () => expect(parseVisibleCollectionFeeds(pageWith(...Array.from({ length: 49 }, (_, i) => card(`f${i}`))), boardId)).toHaveLength(49));
  it("R1-06 captures 500 source-free feeds", () => expect(parseVisibleCollectionFeeds(pageWith(...Array.from({ length: 500 }, (_, i) => card(`f${i}`))), boardId)).toHaveLength(500));
  it("R1-07 rejects a missing token", () => expect(parseVisibleCollectionFeeds(pageWith(card("f1", "")), boardId)).toEqual([]));
  it("R1-08 rejects a missing matching alias", () => expect(parseVisibleCollectionFeeds(pageWith(card("f1", "t", { explore: "other" })), boardId)).toEqual([]));
  it("R1-09 rejects a mismatched alias", () => expect(parseVisibleCollectionFeeds(pageWith(card("f1", "t", { explore: "f2" })), boardId)).toEqual([]));
  it("R1-10 rejects a different board", () => expect(parseVisibleCollectionFeeds(pageWith(card("f1", "t", { board: "other" })), boardId)).toEqual([]));
  it("R1-11 rejects profile-only security context", () => expect(parseVisibleCollectionFeeds(pageWith(`<article><a href='/user/profile/u?xsec_token=t&xsec_source=pc_note'>p</a></article>`), boardId)).toEqual([]));
  it("R1-12 does not borrow profile source", () => expect(parseVisibleCollectionFeeds(pageWith(`<article><a href='/board/${boardId}/f1?xsec_token=t'>b</a><a href='/explore/f1'>e</a><a href='/user/profile/u?xsec_token=p&xsec_source=pc_note'>p</a></article>`), boardId)[0]).toEqual({ feedId: "f1", xsecToken: "t" }));
  it("R1-13 retains latest nonempty token B", () => {
    const first = mergeVisibleCollectionFeeds(createCollectionCaptureState(), [candidate("f1", "A")]);
    expect(mergeVisibleCollectionFeeds(first, [candidate("f1", "B")]).items.get("f1")?.xsecToken).toBe("B");
  });
  it("R1-14 preserves A after empty token update", () => {
    const first = mergeVisibleCollectionFeeds(createCollectionCaptureState(), [candidate("f1", "A")]);
    expect(mergeVisibleCollectionFeeds(first, [{ ...candidate("f1"), xsecToken: "" }]).items.get("f1")?.xsecToken).toBe("A");
  });
  it("R2-01 continues when non-bottom and loading", () => expect(decideCollectionScroll(scroll({ loading: true }))).toBe("continue"));
  it("R2-02 continues when non-bottom and settled", () => expect(decideCollectionScroll(scroll({ loading: false }))).toBe("continue"));
  it("R2-03 waits when bottom and loading", () => expect(decideCollectionScroll(scroll({ scrollTop: 500, loading: true }))).toBe("wait"));
  it("R2-04 waits at bottom when new items arrived", () => expect(decideCollectionScroll(scroll({ scrollTop: 500, newUniqueCount: 1 }))).toBe("wait"));
  it("R2-05 finishes only at stable bottom", () => expect(decideCollectionScroll(scroll({ scrollTop: 500, newUniqueCount: 0, progress: stableProgress(3) }))).toBe("done"));
  it("R3-01 ignores generic loading when bottom facts are stable", () => expect(decideCollectionScroll(scroll({ scrollTop: 500, loading: true, relevantLoading: false, newUniqueCount: 0, progress: stableProgress(3) }))).toBe("done"));
  it("R3-02 waits when loading coincides with scrollHeight growth", () => expect(decideCollectionScroll(scroll({ scrollTop: 500, loading: true, relevantLoading: true, newUniqueCount: 0, progress: stableProgress(2) }))).toBe("wait"));
  it("R3-03 waits when loading coincides with unique growth", () => expect(decideCollectionScroll(scroll({ scrollTop: 500, loading: true, relevantLoading: true, newUniqueCount: 1, progress: stableProgress(2) }))).toBe("wait"));
  it("R3-04 resets stability after geometry growth", () => expect(advanceCollectionScrollProgress(stableProgress(2), { scrollTop: 500, scrollHeight: 1100, clientHeight: 500, uniqueCount: 0, loading: true, relevantLoading: true }).bottomStableRounds).toBe(0));
  it("R3-05 resets stability after unique growth", () => expect(advanceCollectionScrollProgress(stableProgress(2), { scrollTop: 500, scrollHeight: 1000, clientHeight: 500, uniqueCount: 1, loading: true, relevantLoading: true }).bottomStableRounds).toBe(0));
});
