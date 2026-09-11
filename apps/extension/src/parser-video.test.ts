import { describe, expect, it } from "vitest";

import { parseInitialStateScript } from "./parser";

const WORK_ID = "synthetic000000000000000001";
const SOURCE_URL = `https://www.xiaohongshu.com/explore/${WORK_ID}`;

function stateScript(note: Record<string, unknown>): string {
  return `window.__INITIAL_STATE__=${JSON.stringify({
    note: { noteDetailMap: { [WORK_ID]: { note } } },
  })};`;
}

describe("视频详情页面解析", () => {
  it("视频详情带多个预览图时仍优先解析视频媒体", () => {
    const work = parseInitialStateScript(
      stateScript({
        noteId: WORK_ID,
        type: "video",
        user: { userId: "synthetic-author" },
        imageList: [
          { url: "https://sns-img-bd.xhscdn.com/synthetic-cover" },
          { url: "https://sns-img-bd.xhscdn.com/synthetic-preview" },
        ],
        video: { consumer: { originVideoKey: "folder\\u002Fvideo.mp4" } },
      }),
      SOURCE_URL,
    );

    expect(work.media[0]).toMatchObject({
      kind: "video",
      url: "https://sns-video-bd.xhscdn.com/folder/video.mp4",
    });
  });

  it("即使类型字段异常也优先解析非空视频对象", () => {
    const work = parseInitialStateScript(
      stateScript({
        noteId: WORK_ID,
        type: "normal",
        user: { userId: "synthetic-author" },
        imageList: [{ url: "https://sns-img-bd.xhscdn.com/synthetic-cover" }],
        video: { consumer: { originVideoKey: "folder\\u002Fvideo.mp4" } },
      }),
      SOURCE_URL,
    );

    expect(work.media[0]).toMatchObject({
      kind: "video",
      url: "https://sns-video-bd.xhscdn.com/folder/video.mp4",
    });
  });
});
