import type { FeedMediaResult } from "@xhs-downloader/contracts";

import { readLiveInitialState } from "./browser-state-bridge";
import { parseInitialStateRecord, parseInitialStateScript } from "./parser";

/** 从同一 initial-state 来源提取短期媒体定位器。 */
export async function parseFeedMediaDocument(
  page: Document,
  feedId: string,
  sourceUrl: string,
): Promise<FeedMediaResult> {
  const scripts = [...page.scripts]
    .map((script) => script.textContent?.trim() ?? "")
    .filter((text) => text.startsWith("window.__INITIAL_STATE__"))
    .reverse();
  let latestResult: FeedMediaResult | undefined;
  for (const script of scripts) {
    try {
      const work = parseInitialStateScript(script, sourceUrl);
      if (work.workId !== feedId) throw new Error("媒体结果与请求帖子不一致");
      latestResult = {
        feed_id: feedId,
        note_type: work.media.some((media) => media.kind === "video") ? "video" : "unknown",
        media: work.media,
      };
      if (latestResult.media.length) return latestResult;
    } catch {
      // 与详情 parser 一致，尝试页面中的下一份状态快照。
    }
  }
  try {
    const work = parseInitialStateRecord(await readLiveInitialState(page), sourceUrl);
    if (work.workId !== feedId) throw new Error("实时媒体结果与请求帖子不一致");
    const liveResult: FeedMediaResult = {
      feed_id: feedId,
      note_type: work.media.some((media) => media.kind === "video") ? "video" : "unknown",
      media: work.media,
    };
    if (liveResult.media.length) return liveResult;
  } catch {
    // 没有实时桥或实时状态仍未就绪时，保持 fail closed。
  }
  throw new Error("页面没有请求帖子的视频媒体");
}
