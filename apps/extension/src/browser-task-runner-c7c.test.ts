import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { runBrowserTaskPoll } from "./browser-task-runner";
import { makeBrowserTaskClaim as claim } from "./browser-task-test-helpers";

let values: Record<string, unknown>;
let tabs: Array<{ id?: number; active?: boolean }>;
let pageResponse: unknown;
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
  tabs = [{ id: 7, active: true }];
  createdUrl = undefined;
  pageResponse = {
    ok: true,
    message: "浏览器尚未登录小红书",
    result: { logged_in: false, user_id: null, nickname: null },
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
      query: vi.fn(async () => tabs),
      create: vi.fn(async (options: { url?: string }) => {
        createdUrl = options.url;
        return { id: 8, active: false };
      }),
      update: vi.fn(async () => ({ id: 8, active: false })),
      get: vi.fn(async () => ({
        id: 8,
        status: "complete",
        url: createdUrl ?? "https://www.xiaohongshu.com/board/not-a-detail",
      })),
      remove: vi.fn(async () => undefined),
      sendMessage: vi.fn(async () => pageResponse),
    },
  });
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("C7C 浏览器任务边界回传", () => {
  const detailPayload = {
    feed_id: "synthetic-feed",
    xsec_token: "synthetic-token",
    comment_limit: 10,
    include_replies: false,
    reply_limit: 10,
  };

  function stubTaskResult(): ReturnType<typeof vi.fn> {
    return vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ protocol_version: 4, features: { browser_tasks: true } })),
      )
      .mockResolvedValueOnce(new Response(JSON.stringify(claim("get_feed_detail", detailPayload))))
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "running" })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "failed" })));
  }

  it("详情 readiness 失败时回传最后边界和 build identity", async () => {
    tabs = [];
    vi.mocked(chrome.tabs.get).mockImplementation(
      async () =>
        ({
          id: 8,
          status: "complete",
          url: "https://www.xiaohongshu.com/board/not-a-detail",
        }) as chrome.tabs.Tab,
    );
    const fetchMock = stubTaskResult();
    vi.stubGlobal("fetch", fetchMock);

    await runBrowserTaskPoll();

    const body = JSON.parse(fetchMock.mock.calls[3][1].body) as Record<string, unknown>;
    expect(body.result).toMatchObject({
      failure_code: "TARGET_TAB_IDENTITY_MISMATCH",
      browser_runtime_telemetry: {
        extension_manifest_version: "3.0.0",
        diagnostic_schema_version: "C7C-1",
        target_tab_created: true,
        detail_wait_started: true,
        detail_wait_result: "FAIL",
        send_message_attempted: false,
        page_response_class: "NOT_REACHED",
        last_completed_runtime_boundary: "RESULT_SUBMIT_ATTEMPTED",
      },
    });
  });

  it("content-script 返回页面错误时标记 response boundary", async () => {
    tabs = [];
    pageResponse = {
      ok: false,
      status: "failed",
      message: "页面解析失败",
      result: { failure_code: "PAGE_TASK_ERROR", failure_stage: "page_parser" },
      page_runtime_telemetry: {
        content_script_message_received: true,
        page_task_started: true,
        parser_invocation_started: false,
      },
    };
    const fetchMock = stubTaskResult();
    vi.stubGlobal("fetch", fetchMock);

    await runBrowserTaskPoll();

    const body = JSON.parse(fetchMock.mock.calls[3][1].body) as Record<string, unknown>;
    expect((body.result as Record<string, unknown>).browser_runtime_telemetry).toMatchObject({
      content_script_message_received: true,
      page_task_started: true,
      parser_invocation_started: false,
      content_script_response_received: true,
      page_response_class: "PAGE_TASK_ERROR",
      last_completed_runtime_boundary: "RESULT_SUBMIT_ATTEMPTED",
    });
  });

  it("content-script 返回无效 envelope 时标记 INVALID_RESPONSE", async () => {
    tabs = [];
    pageResponse = {};
    const fetchMock = stubTaskResult();
    vi.stubGlobal("fetch", fetchMock);

    await runBrowserTaskPoll();

    expect(JSON.parse(fetchMock.mock.calls[3][1].body).result).toMatchObject({
      failure_code: "MESSAGE_RESPONSE_EMPTY",
      browser_runtime_telemetry: {
        content_script_response_received: true,
        page_response_class: "INVALID_RESPONSE",
        last_completed_runtime_boundary: "RESULT_SUBMIT_ATTEMPTED",
      },
    });
  });
});
