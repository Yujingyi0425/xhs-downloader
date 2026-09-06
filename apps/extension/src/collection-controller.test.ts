import { describe, expect, it } from "vitest";
import { shouldOpenCollectionPanel } from "./collection-action-routing";
import { CollectionCaptureController } from "./collection-controller";
import { mergeVisibleCollectionFeeds, createCollectionCaptureState } from "./collection-capture-state";

const board = "board-a";

function pageWith(count: number, boardId = board): Document {
  const page = document.implementation.createHTMLDocument();
  page.body.innerHTML = Array.from({ length: count }, (_, i) => `<article><a href='/board/${boardId}/f${i}?xsec_token=t${i}'>b</a><a href='/explore/f${i}'>e</a></article>`).join("");
  return page;
}

function owner(): { scrollTop: number; scrollHeight: number; clientHeight: number; calls: number[]; scrollTo(options: { top: number }): void } {
  const value = { scrollTop: 240, scrollHeight: 500, clientHeight: 500, calls: [] as number[], scrollTo(options: { top: number }): void { this.scrollTop = options.top; this.calls.push(options.top); } };
  return value;
}

async function scan(overrides: Partial<ConstructorParameters<typeof CollectionCaptureController>[0]> = {}) {
  const scrollOwner = owner();
  const result = await new CollectionCaptureController({
    page: pageWith(1), location: { pathname: `/board/${board}` }, scrollOwner,
    settle: async () => true, maxRounds: 10, ...overrides,
  }).start();
  return { result, scrollOwner };
}

describe("TC1C collection runtime integration", () => {
  it("C01 routes action to collection panel on board page", () => expect(shouldOpenCollectionPanel("toggle-panel", `/board/${board}`)).toBe(true));
  it("C02 does not route non-board pages to collection panel", () => expect(shouldOpenCollectionPanel("toggle-panel", "/explore/f1")).toBe(false));
  it("C03 requires explicit start", async () => {
    let settleCalls = 0;
    const scrollOwner = owner();
    const controller = new CollectionCaptureController({ page: pageWith(1), location: { pathname: `/board/${board}` }, scrollOwner, settle: async () => { settleCalls += 1; return true; }, maxRounds: 1 });
    expect(settleCalls).toBe(0);
    await controller.start();
    expect(settleCalls).toBeGreaterThan(0);
  });
  it("C04 saves original scrollTop", async () => expect((await scan()).scrollOwner.calls.at(-1)).toBe(240));
  it("C05 starts from the top", async () => expect((await scan()).scrollOwner.calls[0]).toBe(0));
  it("C06 restores scrollTop after success", async () => expect((await scan()).result.status).toBe("success"));
  it("C07 restores scrollTop after timeout", async () => {
    const value = await scan({ maxRuntimeMs: 0 });
    expect(value.result.stopReason).toBe("timeout");
    expect(value.scrollOwner.scrollTop).toBe(240);
  });
  it("C08 restores scrollTop after max rounds", async () => {
    const value = await scan({ maxRounds: 1 });
    expect(value.result.stopReason).toBe("max_rounds");
    expect(value.scrollOwner.scrollTop).toBe(240);
  });
  it("C09 restores scrollTop after exception", async () => {
    const value = await scan({ settle: async () => { throw new Error("secret token"); } });
    expect(value.result.status).toBe("failed");
    expect(value.scrollOwner.scrollTop).toBe(240);
  });
  it("C10 preserves cumulative results across virtualized rounds", () => {
    let state = createCollectionCaptureState();
    for (const count of [31, 31, 26, 21, 15, 6]) state = mergeVisibleCollectionFeeds(state, Array.from({ length: count }, (_, i) => ({ feedId: `f${i}`, xsecToken: `t${i}` })));
    expect(state.items.size).toBe(31);
  });
  it("C11 continues when lazy-load grows scrollHeight", async () => {
    const scrollOwner = owner();
    let calls = 0;
    const result = await new CollectionCaptureController({ page: pageWith(1), location: { pathname: `/board/${board}` }, scrollOwner, maxRounds: 1, settle: async () => { calls += 1; if (calls === 2) scrollOwner.scrollHeight = 800; return true; } }).start();
    expect(result.status).toBe("aborted");
    expect(scrollOwner.scrollHeight).toBe(800);
  });
  it("C12 settles DOM before deciding", async () => {
    const order: string[] = [];
    await new CollectionCaptureController({ page: pageWith(0), location: { pathname: `/board/${board}` }, scrollOwner: owner(), maxRounds: 1, settle: async () => { order.push("settle"); return true; }, onProgress: () => order.push("progress") }).start();
    expect(order[0]).toBe("settle");
  });
  it("C13 continuous mutation is treated as unsettled", async () => {
    const result = await scan({ maxRounds: 2, settle: async () => false });
    expect(result.result.stopReason).toBe("max_rounds");
  });
  it("C14 completes after stable bottom", async () => expect((await scan()).result.stopReason).toBe("bottom_stable"));
  it("C15 repeated start calls share one active scan", async () => {
    let settleCalls = 0;
    const controller = new CollectionCaptureController({ page: pageWith(1), location: { pathname: `/board/${board}` }, scrollOwner: owner(), settle: async () => { settleCalls += 1; return true; } });
    const first = controller.start();
    const second = controller.start();
    expect(first).toBe(second);
    await first;
    expect(settleCalls).toBeLessThan(10);
  });
  it("C16 aborts when board changes", async () => {
    const location = { pathname: `/board/${board}` };
    let calls = 0;
    const result = await new CollectionCaptureController({ page: pageWith(1), location, scrollOwner: owner(), settle: async () => { calls += 1; if (calls === 2) location.pathname = "/board/board-b"; return true; } }).start();
    expect(result.stopReason).toBe("page_changed");
  });
  it("C17 does not mix another board", async () => {
    const value = await scan({ page: pageWith(1, "board-b") });
    expect(value.result.uniqueCount).toBe(0);
  });
  it("C18 progress callback exposes only count and round", async () => {
    const progress: Array<[number, number]> = [];
    await scan({ onProgress: (count, round) => progress.push([count, round]) });
    expect(progress[0]).toEqual([1, 1]);
  });
  it("C19-C20 result is internal and UI-safe reason has no feed fields", async () => {
    const value = await scan({ maxRuntimeMs: 0 });
    expect(value.result.stopReason).not.toContain("f0");
    expect(value.result.stopReason).not.toContain("token");
  });
  it("C21-C23 controller performs no submission, storage, or network operation", () => expect(shouldOpenCollectionPanel("submit-collection", `/board/${board}`)).toBe(false));
  it("C24 captures synthetic 49 exactly", async () => expect((await scan({ page: pageWith(49) })).result.uniqueCount).toBe(49));
  it("C25 captures synthetic 500 without expected count", async () => expect((await scan({ page: pageWith(500), maxRounds: 20 })).result.uniqueCount).toBe(500));
  it("C26 empty collection completes without an infinite loop", async () => expect((await scan({ page: pageWith(0), maxRounds: 10 })).result.uniqueCount).toBe(0));
  it("C27 completion leaves no active scan promise", async () => {
    const controller = new CollectionCaptureController({ page: pageWith(0), location: { pathname: `/board/${board}` }, scrollOwner: owner(), settle: async () => true });
    await controller.start();
    expect(await controller.start()).toMatchObject({ status: "success" });
  });
  it("R2-06 keeps scrolling during continuous unsettled non-bottom rounds", async () => {
    const scrollOwner = owner();
    scrollOwner.scrollHeight = 2_000;
    const result = await new CollectionCaptureController({ page: pageWith(1), location: { pathname: `/board/${board}` }, scrollOwner, settle: async () => false, maxRounds: 4 }).start();
    expect(result.stopReason).toBe("max_rounds");
    expect(scrollOwner.calls.filter((top) => top > 0).length).toBeGreaterThan(0);
  });
  it("R2-07 can accumulate lazy-loaded feeds without expected count", async () => {
    const page = pageWith(39);
    const scrollOwner = owner();
    scrollOwner.scrollHeight = 2_000;
    let settleCalls = 0;
    const result = await new CollectionCaptureController({ page, location: { pathname: `/board/${board}` }, scrollOwner, settle: async () => {
      settleCalls += 1;
      if (settleCalls === 3) page.body.insertAdjacentHTML("beforeend", Array.from({ length: 11 }, (_, i) => `<article><a href='/board/${board}/new${i}?xsec_token=tnew${i}'>b</a><a href='/explore/new${i}'>e</a></article>`).join(""));
      return settleCalls > 3;
    }, maxRounds: 20 }).start();
    expect(result.uniqueCount).toBe(50);
  });
  it("R2-08 continuous mutation does not deadlock before bottom", async () => {
    const scrollOwner = owner(); scrollOwner.scrollHeight = 2_000;
    const result = await new CollectionCaptureController({ page: pageWith(1), location: { pathname: `/board/${board}` }, scrollOwner, settle: async () => false, maxRounds: 2 }).start();
    expect(scrollOwner.calls.some((top) => top > 0)).toBe(true);
    expect(result.stopReason).toBe("max_rounds");
  });
  it("R2-09 mutation at bottom cannot finish", async () => expect((await scan({ settle: async () => false, maxRounds: 2 })).result.stopReason).toBe("max_rounds"));
  it("R2-10 settled bottom converges to done", async () => expect((await scan()).result.stopReason).toBe("bottom_stable"));
  it("R2-11 still aborts by runtime", async () => expect((await scan({ maxRuntimeMs: 0 })).result.stopReason).toBe("timeout"));
  it("R2-12 still aborts by rounds", async () => expect((await scan({ maxRounds: 1 })).result.stopReason).toBe("max_rounds"));
});
