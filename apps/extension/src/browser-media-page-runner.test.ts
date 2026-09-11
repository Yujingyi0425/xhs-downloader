import { describe, expect, it } from "vitest";

import { executeBrowserPageTask } from "./browser-page-runner";
import { installBrowserStateBridge } from "./browser-state-main";
import { pageTask as task, statePage } from "./browser-page-test-helpers";

describe("GET_FEED_MEDIA 页面执行边界", () => {
  it("在详情页读取视频 locator，并对空媒体 fail closed", async () => {
    const page = statePage({
      note: {
        noteDetailMap: {
          "synthetic-feed": {
            note: {
              noteId: "synthetic-feed",
              type: "video",
              user: { userId: "synthetic-author" },
              video: {
                media: {
                  stream: {
                    h264: [{ masterUrl: "https://example.invalid/synthetic.mp4" }],
                  },
                },
              },
            },
          },
        },
      },
    });
    const payload = { feed_id: "synthetic-feed", xsec_token: "synthetic-token" };

    const response = await executeBrowserPageTask(
      task("get_feed_media", payload),
      page,
      "https://www.xiaohongshu.com/explore/synthetic-feed",
    );

    expect(response).toMatchObject({
      ok: true,
      result: {
        feed_id: "synthetic-feed",
        note_type: "video",
        media: [{ kind: "video", url: "https://example.invalid/synthetic.mp4" }],
      },
    });
    await expect(
      executeBrowserPageTask(
        task("get_feed_media", payload),
        document.implementation.createHTMLDocument(),
        "https://www.xiaohongshu.com/explore/synthetic-feed",
      ),
    ).rejects.toThrow("页面没有请求帖子的视频媒体");
  });

  it("静态快照为空时回读主世界实时状态", async () => {
    const page = document;
    page.body.innerHTML = "";
    const scope = window as Window & { __INITIAL_STATE__?: unknown };
    scope.__INITIAL_STATE__ = {
      note: {
        noteDetailMap: {
          "synthetic-feed": {
            note: {
              noteId: "synthetic-feed",
              type: "video",
              video: {
                media: {
                  stream: {
                    h264: [{ masterUrl: "https://example.invalid/live.mp4" }],
                  },
                },
              },
            },
          },
        },
      },
    };
    const uninstall = installBrowserStateBridge(scope);
    try {
      const response = await executeBrowserPageTask(
        task("get_feed_media", { feed_id: "synthetic-feed" }),
        page,
        "https://www.xiaohongshu.com/explore/synthetic-feed",
      );
      expect(response).toMatchObject({
        ok: true,
        result: {
          note_type: "video",
          media: [{ kind: "video", url: "https://example.invalid/live.mp4" }],
        },
      });
    } finally {
      uninstall();
    }
  });

  it("实时状态没有媒体时保持 fail closed", async () => {
    const page = document;
    page.body.innerHTML = "";
    const scope = window as Window & { __INITIAL_STATE__?: unknown };
    scope.__INITIAL_STATE__ = {
      note: {
        noteDetailMap: {
          "synthetic-feed": { note: { noteId: "synthetic-feed", type: "video" } },
        },
      },
    };
    const uninstall = installBrowserStateBridge(scope);
    try {
      await expect(
        executeBrowserPageTask(
          task("get_feed_media", { feed_id: "synthetic-feed" }),
          page,
          "https://www.xiaohongshu.com/explore/synthetic-feed",
        ),
      ).rejects.toThrow("页面没有请求帖子的视频媒体");
    } finally {
      uninstall();
    }
  });
});
