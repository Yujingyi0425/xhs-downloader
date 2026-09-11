import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { runBrowserTaskPoll } from "./browser-task-runner";
import { makeBrowserTaskClaim as claim } from "./browser-task-test-helpers";

let createdUrl: string | undefined;

beforeEach(() => {
  createdUrl = undefined;
  const values: Record<string, unknown> = {
    settings: { serviceUrl: "http://service", mode: "auto" },
    extensionCredential: {
      extensionId: "synthetic-extension",
      token: "synthetic-token",
      installationId: "synthetic-installation",
    },
  };
  vi.stubGlobal("chrome", {
    runtime: { id: "synthetic-extension" },
    storage: {
      local: {
        get: vi.fn(async (keys: string | string[]) =>
          Object.fromEntries(
            (Array.isArray(keys) ? keys : [keys]).map((key) => [key, values[key]]),
          ),
        ),
        set: vi.fn(async (next: Record<string, unknown>) => Object.assign(values, next)),
        remove: vi.fn(async (keys: string | string[]) => {
          for (const key of Array.isArray(keys) ? keys : [keys]) delete values[key];
        }),
      },
    },
    tabs: {
      create: vi.fn(async (options: { url?: string }) => {
        createdUrl = options.url;
        return { id: 8, active: false };
      }),
      get: vi.fn(async () => ({ id: 8, status: "complete", url: createdUrl })),
      remove: vi.fn(async () => undefined),
      sendMessage: vi.fn(async () => ({
        ok: true,
        message: "帖子视频媒体读取完成",
        result: {
          feed_id: "synthetic-feed",
          note_type: "video",
          media: [{ kind: "video", url: "https://example.invalid/synthetic.mp4" }],
        },
      })),
    },
  });
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
function serviceResponses(taskClaim: ReturnType<typeof claim>) {
  return vi
    .fn()
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ protocol_version: 4, features: { browser_tasks: true } })),
    )
    .mockResolvedValueOnce(new Response(JSON.stringify(taskClaim)))
    .mockResolvedValueOnce(new Response(JSON.stringify({ status: "running" })))
    .mockResolvedValueOnce(new Response(JSON.stringify({ status: "succeeded" })));
}
describe("GET_FEED_MEDIA 后台执行边界", () => {
  it("从 feed_id 打开详情页，确认 identity 后再发送消息", async () => {
    const fetchMock = serviceResponses(
      claim("get_feed_media", {
        feed_id: "synthetic-feed",
        xsec_token: "synthetic-token",
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await runBrowserTaskPoll();

    expect(createdUrl).toBe(
      "https://www.xiaohongshu.com/explore/synthetic-feed?xsec_token=synthetic-token&xsec_source=pc_feed",
    );
    expect(chrome.tabs.get).toHaveBeenCalledWith(8);
    expect(chrome.tabs.sendMessage).toHaveBeenCalledWith(
      8,
      expect.objectContaining({ type: "browser-page-task" }),
    );
    expect(JSON.parse(fetchMock.mock.calls[3][1].body)).toMatchObject({
      status: "succeeded",
      result: { note_type: "video" },
    });
    expect(JSON.parse(fetchMock.mock.calls[3][1].body).result).not.toHaveProperty(
      "elapsed_ms",
    );
  });
  it("非详情页持续 loading 时保留有界导航诊断", async () => {
    vi.mocked(chrome.tabs.get).mockResolvedValue({
      id: 8,
      status: "loading",
      url: "about:blank",
    } as never);
    const fetchMock = serviceResponses(
      claim("get_feed_media", {
        feed_id: "synthetic-feed",
        xsec_token: "synthetic-token",
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await runBrowserTaskPoll();

    const response = JSON.parse(fetchMock.mock.calls[3][1].body);
    expect(response).toMatchObject({
      status: "failed",
      result: {
        failure_stage: "background",
        failure_code: "DETAIL_NAVIGATION_FAILED",
        target_tab_exists: true,
        last_tab_status: "loading",
        last_route_class: "/blank",
        url_host_is_xhs: false,
        expected_route_matched: false,
        tab_removed: false,
      },
    });
    expect(response.result.elapsed_ms).toBeGreaterThanOrEqual(0);
    expect(response.result).not.toHaveProperty("navigation_creation");
    expect(response.result).not.toHaveProperty("created_tab_id");
  }, 10_000);
  it("预期详情 pendingUrl 在旧超时后提交时获得有限 grace", async () => {
    const expectedUrl =
      "https://www.xiaohongshu.com/explore/synthetic-feed?xsec_token=synthetic-token";
    let reads = 0;
    vi.mocked(chrome.tabs.get).mockImplementation(async () => {
      reads += 1;
      if (reads <= 24) {
        return {
          id: 8,
          status: "loading",
          url: "about:blank",
          pendingUrl: expectedUrl,
        } as never;
      }
      return { id: 8, status: "complete", url: expectedUrl } as never;
    });
    const fetchMock = serviceResponses(
      claim("get_feed_media", {
        feed_id: "synthetic-feed",
        xsec_token: "synthetic-token",
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await runBrowserTaskPoll();

    expect(reads).toBe(25);
    expect(JSON.parse(fetchMock.mock.calls[3][1].body)).toMatchObject({
      status: "succeeded",
      result: { note_type: "video" },
    });
  }, 12_000);
  it("pendingUrl 缺失时不获得 grace", async () => {
    vi.mocked(chrome.tabs.get).mockResolvedValue({
      id: 8,
      status: "loading",
      url: "about:blank",
    } as never);
    const fetchMock = serviceResponses(
      claim("get_feed_media", {
        feed_id: "synthetic-feed",
        xsec_token: "synthetic-token",
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await runBrowserTaskPoll();

    expect(JSON.parse(fetchMock.mock.calls[3][1].body as string)).toMatchObject({
      status: "failed",
      result: { failure_code: "DETAIL_NAVIGATION_FAILED" },
    });
  }, 10_000);
  it("目标详情 URL 已匹配时允许 loading 页面进入页面执行器", async () => {
    const expectedUrl =
      "https://www.xiaohongshu.com/explore/synthetic-feed?xsec_token=synthetic-token";
    vi.mocked(chrome.tabs.get).mockResolvedValue({
      id: 8,
      status: "loading",
      url: expectedUrl,
    } as never);
    const fetchMock = serviceResponses(
      claim("get_feed_media", {
        feed_id: "synthetic-feed",
        xsec_token: "synthetic-token",
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await runBrowserTaskPoll();

    expect(JSON.parse(fetchMock.mock.calls[3][1].body)).toMatchObject({
      status: "succeeded",
      result: { note_type: "video" },
    });
  }, 10_000);
  it("预期 pendingUrl 永不提交时在新上限失败", async () => {
    vi.mocked(chrome.tabs.get).mockResolvedValue({
      id: 8,
      status: "loading",
      url: "about:blank",
      pendingUrl:
        "https://www.xiaohongshu.com/explore/synthetic-feed?xsec_token=synthetic-token",
    } as never);
    const fetchMock = serviceResponses(
      claim("get_feed_media", {
        feed_id: "synthetic-feed",
        xsec_token: "synthetic-token",
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await runBrowserTaskPoll();

    const finalResponse = JSON.parse(
      fetchMock.mock.calls[fetchMock.mock.calls.length - 1][1].body as string,
    );
    expect(finalResponse).toMatchObject({
      status: "failed",
      result: { failure_code: "DETAIL_NAVIGATION_FAILED" },
    });
  }, 12_000);
  it("目标标签消失时保留 missing 诊断", async () => {
    vi.mocked(chrome.tabs.get).mockRejectedValue(new Error("tab removed"));
    const fetchMock = serviceResponses(
      claim("get_feed_media", {
        feed_id: "synthetic-feed",
        xsec_token: "synthetic-token",
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await runBrowserTaskPoll();

    expect(JSON.parse(fetchMock.mock.calls[3][1].body)).toMatchObject({
      status: "failed",
      result: {
        failure_stage: "background",
        failure_code: "TARGET_TAB_NOT_FOUND",
        target_tab_exists: false,
        last_tab_status: "missing",
        last_route_class: "/unknown",
        url_host_is_xhs: false,
        expected_route_matched: false,
        tab_removed: true,
      },
    });
  });
  it("content script 未就绪时返回明确 failure code", async () => {
    vi.mocked(chrome.tabs.sendMessage).mockRejectedValue(
      new Error("Could not establish connection. Receiving end does not exist."),
    );
    const fetchMock = serviceResponses(
      claim("get_feed_media", {
        feed_id: "synthetic-feed",
        xsec_token: "synthetic-token",
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await runBrowserTaskPoll();

    expect(JSON.parse(fetchMock.mock.calls[3][1].body)).toMatchObject({
      status: "failed",
      result: { failure_code: "CONTENT_SCRIPT_NOT_READY", failure_stage: "background" },
    });
  }, 10_000);
  it("board context identity 不匹配时不发送 media 消息", async () => {
    vi.mocked(chrome.tabs.get).mockResolvedValue({
      id: 8,
      status: "complete",
      url: "https://www.xiaohongshu.com/board/synthetic-board/synthetic-feed",
    } as never);
    const fetchMock = serviceResponses(
      claim("get_feed_media", {
        feed_id: "synthetic-feed",
        xsec_token: "synthetic-token",
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await runBrowserTaskPoll();

    expect(chrome.tabs.sendMessage).not.toHaveBeenCalled();
    expect(JSON.parse(fetchMock.mock.calls[3][1].body)).toMatchObject({
      status: "failed",
      result: {
        failure_code: "TARGET_TAB_IDENTITY_MISMATCH",
        failure_stage: "background",
        target_tab_exists: true,
        last_tab_status: "complete",
        last_route_class: "/board/<board_id>",
        url_host_is_xhs: true,
        expected_route_matched: false,
        tab_removed: false,
      },
    });
  });
});
