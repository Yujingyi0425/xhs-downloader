import type { FeedMediaResult } from "@xhs-downloader/contracts";

import { parseInitialStateScript } from "./parser";

/** 从同一 initial-state 来源提取短期媒体定位器。 */
export function parseFeedMediaDocument(
  page: Document,
  feedId: string,
  sourceUrl: string,
): FeedMediaResult {
  const scripts = [...page.scripts]
    .map((script) => script.textContent?.trim() ?? "")
    .filter((text) => text.startsWith("window.__INITIAL_STATE__"))
    .reverse();
  for (const script of scripts) {
    try {
      const work = parseInitialStateScript(script, sourceUrl);
      if (work.workId !== feedId) throw new Error("媒体结果与请求帖子不一致");
      return {
        feed_id: feedId,
        note_type: work.media.some((media) => media.kind === "video") ? "video" : "unknown",
        media: work.media,
      };
    } catch {
      // 与详情 parser 一致，尝试页面中的下一份状态快照。
    }
  }
  throw new Error("页面没有请求帖子的视频媒体");
}
