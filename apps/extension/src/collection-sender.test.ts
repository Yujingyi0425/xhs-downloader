import { describe, expect, it } from "vitest";
import { pageUrlFromSender } from "./collection-sender";

describe("collection message sender URL", () => {
  it("prefers the current top-level tab URL", () => {
    expect(pageUrlFromSender({
      url: "https://www.xiaohongshu.com/explore/stale-frame",
      tab: { url: "https://www.xiaohongshu.com/board/current-board" },
    })).toBe("https://www.xiaohongshu.com/board/current-board");
  });

  it("falls back to sender.url when a tab URL is unavailable", () => {
    expect(pageUrlFromSender({ url: "https://www.xiaohongshu.com/board/current-board" }))
      .toBe("https://www.xiaohongshu.com/board/current-board");
  });
});
