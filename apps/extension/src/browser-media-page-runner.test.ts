import { describe, expect, it } from "vitest";

import { executeBrowserPageTask } from "./browser-page-runner";
import { installBrowserStateBridge } from "./browser-state-main";
import { pageTask as task, statePage } from "./browser-page-test-helpers";
import { FeedMediaParserError, parseFeedMediaDocument } from "./feed-media-parser";

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
              imageList: [{ urlDefault: "https://sns-img-bd.xhscdn.com/synthetic-cover" }],
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
        media: [
          {
            kind: "video",
            url: "https://example.invalid/synthetic.mp4",
            preview_url: "https://sns-img-bd.xhscdn.com/synthetic-cover",
          },
        ],
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

  it("兼容 codec 名称变化及单对象视频流", async () => {
    const page = statePage({
      note: {
        noteDetailMap: {
          "synthetic-feed": {
            note: {
              noteId: "synthetic-feed",
              type: "video",
              video: {
                media: {
                  stream: {
                    avc: {
                      masterUrl: "https://example.invalid/codec-change.mp4",
                    },
                  },
                },
              },
            },
          },
        },
      },
    });

    const response = await executeBrowserPageTask(
      task("get_feed_media", { feed_id: "synthetic-feed" }),
      page,
      "https://www.xiaohongshu.com/explore/synthetic-feed",
    );

    expect(response).toMatchObject({
      ok: true,
      result: {
        media: [{ kind: "video", url: "https://example.invalid/codec-change.mp4" }],
      },
    });
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

  it("状态 schema 为空时从同一详情页的 video currentSrc 读取视频", async () => {
    const page = document.implementation.createHTMLDocument();
    const video = page.createElement("video");
    Object.defineProperty(video, "currentSrc", {
      configurable: true,
      value: "https://sns-video-bd.xhscdn.com/synthetic/video.mp4?signature=synthetic",
    });
    page.body.append(video);

    const result = await parseFeedMediaDocument(
      page,
      "synthetic-feed",
      "https://www.xiaohongshu.com/explore/synthetic-feed",
    );

    expect(result).toMatchObject({
      note_type: "video",
      media: [
        {
          kind: "video",
          url: "https://sns-video-bd.xhscdn.com/synthetic/video.mp4?signature=synthetic",
        },
      ],
    });
  });

  it("video 没有可下载地址时拒绝 blob 并返回脱敏结构诊断", async () => {
    const page = document.implementation.createHTMLDocument();
    const video = page.createElement("video");
    video.src = "blob:https://www.xiaohongshu.com/synthetic-runtime-media";
    page.body.append(video);

    const error = await parseFeedMediaDocument(
      page,
      "synthetic-feed",
      "https://www.xiaohongshu.com/explore/synthetic-feed",
    ).catch((value: unknown) => value);

    expect(error).toBeInstanceOf(FeedMediaParserError);
    expect((error as FeedMediaParserError).diagnostics).toEqual(
      expect.objectContaining({
        video_element_count: 1,
        video_src_present: "YES",
        locator_candidate_source: "NONE",
        locator_rejection_reason: "BLOB_ONLY_SOURCE",
        signed_query_present: "NO",
      }),
    );
    expect(JSON.stringify((error as FeedMediaParserError).diagnostics)).not.toContain("synthetic-runtime");
  });

  it("video 元素没有地址时可读取 source 元素的稳定视频地址", async () => {
    const page = document.implementation.createHTMLDocument();
    const video = page.createElement("video");
    const source = page.createElement("source");
    source.src = "https://sns-video-hw.xhscdn.com/synthetic/stream.m3u8";
    video.append(source);
    page.body.append(video);

    const result = await parseFeedMediaDocument(
      page,
      "synthetic-feed",
      "https://www.xiaohongshu.com/explore/synthetic-feed",
    );

    expect(result.media[0]).toMatchObject({
      kind: "video",
      url: "https://sns-video-hw.xhscdn.com/synthetic/stream.m3u8",
    });
  });
});
