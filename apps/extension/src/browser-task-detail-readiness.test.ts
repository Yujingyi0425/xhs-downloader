import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { runBrowserTaskPoll } from "./browser-task-runner";
import { makeBrowserTaskClaim as claim } from "./browser-task-test-helpers";

let values: Record<string, unknown>;
let createdUrl: string | undefined;

beforeEach(() => {
  values = {
    settings: { serviceUrl: "http://service", mode: "auto" },
    extensionCredential: {
      extensionId: "synthetic-extension",
      token: "synthetic-token",
      installationId: "synthetic-installation",
    },
  };
  createdUrl = undefined;
  vi.stubGlobal("chrome", {
    runtime: { id: "synthetic-extension" },
    storage: {
      local: {
        get: vi.fn(async (keys: string | string[]) =>
          Object.fromEntries(
            (Array.isArray(keys) ? keys : [keys]).map((key) => [key, values[key]]),
          ),
        ),
        set: vi.fn(async (next: Record<string, unknown>) => {
          Object.assign(values, next);
        }),
        remove: vi.fn(async () => undefined),
      },
    },
    tabs: {
      query: vi.fn(async () => []),
      create: vi.fn(async (options: { url?: string }) => {
        createdUrl = options.url;
        return { id: 8, active: false };
      }),
      get: vi.fn(async () => ({
        id: 8,
        status: "complete",
        url: createdUrl,
      })),
      remove: vi.fn(async () => undefined),
      sendMessage: vi.fn(async () => ({ ok: true, message: "合成详情已解析" })),
    },
  });
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("详情 enrichment 页面 readiness", () => {
  it("页面完成且身份匹配后才发送解析消息", async () => {
    let tabReads = 0;
    vi.mocked(chrome.tabs.get).mockImplementation(async () => {
      tabReads += 1;
      return {
        id: 8,
        status: tabReads === 1 ? "loading" : "complete",
        url: createdUrl,
      };
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            protocol_version: 4,
            features: { browser_tasks: true },
          }),
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify(
            claim("get_feed_detail", {
              feed_id: "synthetic-feed",
              xsec_token: "synthetic-token",
            }),
          ),
        ),
      )
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "running" })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "succeeded" })));
    vi.stubGlobal("fetch", fetchMock);

    await runBrowserTaskPoll();

    expect(tabReads).toBe(2);
    expect(chrome.tabs.sendMessage).toHaveBeenCalledWith(
      8,
      expect.objectContaining({ type: "browser-page-task" }),
    );
    expect(JSON.parse(fetchMock.mock.calls[3][1].body).status).toBe("succeeded");
  });

  it("错误页面上下文 fail closed 且不发送解析消息", async () => {
    vi.mocked(chrome.tabs.get).mockImplementation(
      () =>
        Promise.resolve({
          id: 8,
          status: "complete",
          url: "https://www.xiaohongshu.com/board/synthetic-board/synthetic-feed",
        }) as never,
    );
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            protocol_version: 4,
            features: { browser_tasks: true },
          }),
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify(
            claim("get_feed_detail", {
              feed_id: "synthetic-feed",
              xsec_token: "synthetic-token",
            }),
          ),
        ),
      )
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "running" })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "failed" })));
    vi.stubGlobal("fetch", fetchMock);

    await runBrowserTaskPoll();

    expect(chrome.tabs.sendMessage).not.toHaveBeenCalled();
    expect(JSON.parse(fetchMock.mock.calls[3][1].body)).toMatchObject({
      status: "failed",
      message: "详情页与目标帖子不一致",
    });
  });
});
