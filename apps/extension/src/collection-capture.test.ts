import { describe, expect, it } from "vitest";
import { detectCollectionPage, parseCollectionRoute } from "./collection-page-detection";
import { parseVisibleCollectionFeeds, type CollectionFeedCandidate } from "./collection-feed-parser";
import { createCollectionCaptureState, mergeVisibleCollectionFeeds } from "./collection-capture-state";
import { decideCollectionScroll } from "./collection-scroll-policy";

const boardId = "japan-board";

function pageWith(...cards: string[]): Document {
  const page = document.implementation.createHTMLDocument();
  page.body.innerHTML = cards.join("");
  return page;
}

function card(feedId: string, token = `token-${feedId}`, options: { explore?: string; source?: string; board?: string; title?: string; author?: string; cover?: boolean } = {}): string {
  const board = options.board ?? boardId;
  const explore = options.explore ?? feedId;
  const source = options.source ?? "pc_feed";
  return `<article class="feed-card" data-title="${options.title ?? feedId}" data-author="author"><a href="/board/${board}/${feedId}?xsec_token=${token}&xsec_source=${source}">board</a><a href="/explore/${explore}">explore</a>${options.cover === false ? "" : "<img src='cover.jpg'>"}</article>`;
}

function candidate(feedId: string, token = `token-${feedId}`): CollectionFeedCandidate {
  return { feedId, xsecToken: token, xsecSource: "pc_feed" };
}

const scroll = (overrides: Partial<Parameters<typeof decideCollectionScroll>[0]> = {}) => ({
  scrollTop: 0, scrollHeight: 1000, clientHeight: 500, newUniqueCount: 1, loading: false,
  round: 1, elapsedMs: 100, maxRounds: 20, maxRuntimeMs: 10_000, bottomStableRounds: 0,
  requiredBottomStableRounds: 3, ...overrides,
});

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
  it("A13 accepts missing title", () => expect(parseVisibleCollectionFeeds(pageWith(card("f1", "t", { title: "" })), boardId)).toHaveLength(1));
  it("A14 accepts missing author", () => expect(parseVisibleCollectionFeeds(pageWith(card("f1").replace("data-author=\"author\"", "")), boardId)).toHaveLength(1));
  it("A15 accepts missing cover", () => expect(parseVisibleCollectionFeeds(pageWith(card("f1", "t", { cover: false })), boardId)).toHaveLength(1));
  it("A16 does not require note type", () => expect(parseVisibleCollectionFeeds(pageWith(card("f1")), boardId)[0].feedId).toBe("f1"));
  it("A17 excludes a different board", () => expect(parseVisibleCollectionFeeds(pageWith(card("f1", "t", { board: "other" })), boardId)).toEqual([]));
  it("A18 excludes an alias mismatch", () => expect(parseVisibleCollectionFeeds(pageWith(card("f1", "t", { explore: "other" })), boardId)).toEqual([]));
  it("A19 excludes a missing token", () => expect(parseVisibleCollectionFeeds(pageWith(card("f1", "", {})), boardId)).toEqual([]));
  it("A20 excludes a missing xsec source", () => expect(parseVisibleCollectionFeeds(pageWith(card("f1", "t", { source: "" })), boardId)).toEqual([]));
  it("A21 completes after stable bottom", () => expect(decideCollectionScroll(scroll({ scrollTop: 500, newUniqueCount: 0, bottomStableRounds: 3 }))).toBe("done"));
  it("A22 waits at bottom while loading or new items arrive", () => expect(decideCollectionScroll(scroll({ scrollTop: 500, loading: true }))).toBe("wait"));
  it("A23 aborts at max rounds", () => expect(decideCollectionScroll(scroll({ round: 20 }))).toBe("abort_max_rounds"));
  it("A24 aborts at max runtime", () => expect(decideCollectionScroll(scroll({ elapsedMs: 10_000 }))).toBe("abort_timeout"));
  it("A25 tolerates DOM order changes", () => {
    const state = mergeVisibleCollectionFeeds(createCollectionCaptureState(), [candidate("f1"), candidate("f2")]);
    const next = mergeVisibleCollectionFeeds(state, [candidate("f2"), candidate("f1")]);
    expect([...next.items.keys()]).toEqual(["f1", "f2"]);
  });
  it("A26 deduplicates multiple board anchors and aliases", () => {
    const html = `<article class='feed-card'><a href='/board/${boardId}/f1?xsec_token=t1&xsec_source=pc_feed'>one</a><a href='/board/${boardId}/f1?xsec_token=t2&xsec_source=pc_feed'>two</a><a href='/explore/f1'>explore</a></article>`;
    expect(parseVisibleCollectionFeeds(pageWith(html), boardId)).toHaveLength(1);
  });
  it("keeps route parsing free of token errors", () => expect(parseCollectionRoute("%bad").kind).toBe("other"));
});
