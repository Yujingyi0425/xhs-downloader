import { describe, expect, it } from "vitest";

import {
  BrowserTaskExecutionError,
  classifyMessageDispatchError,
  classifyPageTaskError,
  isSupportedDetailPageForFeed,
} from "./browser-task-errors";

describe("浏览器任务失败边界", () => {
  it("区分 parser 空结果、parser 异常和 identity mismatch", () => {
    expect(classifyPageTaskError("get_feed_media", new Error("页面没有请求帖子的视频媒体"))).toBe(
      "MEDIA_PARSER_EMPTY",
    );
    expect(classifyPageTaskError("get_feed_media", new Error("页面状态读取失败"))).toBe(
      "MEDIA_PARSER_ERROR",
    );
    expect(classifyPageTaskError("get_feed_media", new Error("媒体结果与请求帖子不一致"))).toBe(
      "MEDIA_IDENTITY_MISMATCH",
    );
  });

  it("将 content script 消息失败保持为明确错误", () => {
    expect(
      classifyMessageDispatchError(
        new Error("Could not establish connection. Receiving end does not exist."),
      ),
    ).toBe("CONTENT_SCRIPT_NOT_READY");
    expect(classifyMessageDispatchError(new Error("message port closed before response"))).toBe(
      "CONTENT_SCRIPT_NOT_READY",
    );
    expect(classifyMessageDispatchError(new Error("unexpected dispatch failure"))).toBe(
      "MESSAGE_DISPATCH_FAILED",
    );
  });

  it("对空消息响应和详情页 identity fail closed", () => {
    const failure = new BrowserTaskExecutionError("MESSAGE_RESPONSE_EMPTY", "空响应");
    expect(failure.code).toBe("MESSAGE_RESPONSE_EMPTY");
    expect(
      isSupportedDetailPageForFeed(
        "https://www.xiaohongshu.com/explore/synthetic-feed?xsec_source=pc_feed",
        "synthetic-feed",
      ),
    ).toBe(true);
    expect(
      isSupportedDetailPageForFeed(
        "https://www.xiaohongshu.com/explore/other-feed",
        "synthetic-feed",
      ),
    ).toBe(false);
    expect(
      isSupportedDetailPageForFeed(
        "https://www.xiaohongshu.com/board/synthetic-board/synthetic-feed",
        "synthetic-feed",
      ),
    ).toBe(false);
  });
});
