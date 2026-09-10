import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { executeBrowserTaskClaim } from "./browser-task-claim-execution";
import { BrowserTaskExecutionError } from "./browser-task-errors";
import { makeBrowserTaskClaim, WRITE_PAYLOAD } from "./browser-task-test-helpers";
import type { ExtensionCredential } from "./publication-types";

const credential: ExtensionCredential = {
  extensionId: "synthetic-extension",
  token: "synthetic-token",
};

const withCredential = <T>(operation: (value: ExtensionCredential) => Promise<T>): Promise<T> =>
  operation(credential);

/** 记录服务端收到的状态与结果回传。 */
interface ReportedCall {
  url: string;
  body: Record<string, unknown>;
}

let reported: ReportedCall[];

function stubFetch(onResult?: (body: Record<string, unknown>) => Response | undefined): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      const body = init?.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : {};
      reported.push({ url, body });
      if (url.endsWith("/result")) {
        const override = onResult?.(body);
        if (override) return override;
      }
      return new Response(JSON.stringify({ task_id: "synthetic-task" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
}

beforeEach(() => {
  reported = [];
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("浏览器任务租约执行", () => {
  it("成功执行后按响应状态回传结果", async () => {
    stubFetch();
    const claim = makeBrowserTaskClaim("list_feeds");

    await executeBrowserTaskClaim(
      "http://service",
      claim,
      async () => ({
        ok: true,
        message: "读取完成",
        result: { items: [], source: "home", keyword: null, has_more: false },
      }),
      withCredential,
    );

    const result = reported.find((call) => call.url.endsWith("/result"));
    expect(result?.body.status).toBe("succeeded");
    expect(result?.body.message).toBe("读取完成");
  });

  it("响应显式给出状态时以该状态为准", async () => {
    stubFetch();
    const claim = makeBrowserTaskClaim("get_feed_detail");

    await executeBrowserTaskClaim(
      "http://service",
      claim,
      async () => ({
        ok: false,
        message: "页面结构不兼容",
        status: "needs_review" as const,
      }),
      withCredential,
    );

    const result = reported.find((call) => call.url.endsWith("/result"));
    expect(result?.body.status).toBe("needs_review");
  });

  it("响应未成功且未给出状态时记为失败", async () => {
    stubFetch();
    const claim = makeBrowserTaskClaim("list_feeds");

    await executeBrowserTaskClaim(
      "http://service",
      claim,
      async () => ({ ok: false, message: "读取失败" }),
      withCredential,
    );

    const result = reported.find((call) => call.url.endsWith("/result"));
    expect(result?.body.status).toBe("failed");
  });

  it("只读任务执行抛错时记为明确失败", async () => {
    stubFetch();
    const claim = makeBrowserTaskClaim("search_feeds");

    await executeBrowserTaskClaim(
      "http://service",
      claim,
      async () => {
        throw new Error("页面导航超时");
      },
      withCredential,
    );

    const result = reported.find((call) => call.url.endsWith("/result"));
    expect(result?.body.status).toBe("failed");
    expect(result?.body.message).toBe("页面导航超时");
  });

  it("写任务执行抛错时转人工核对而不是失败", async () => {
    stubFetch();
    const claim = makeBrowserTaskClaim("post_comment", {
      ...WRITE_PAYLOAD,
      content: "合成评论",
    });

    await executeBrowserTaskClaim(
      "http://service",
      claim,
      async () => {
        throw new Error("点击后页面无响应");
      },
      withCredential,
    );

    const result = reported.find((call) => call.url.endsWith("/result"));
    expect(result?.body.status).toBe("needs_review");
  });

  it("非 Error 异常回退为固定文案", async () => {
    stubFetch();
    const claim = makeBrowserTaskClaim("list_feeds");

    await executeBrowserTaskClaim(
      "http://service",
      claim,
      async () => {
        throw "字符串异常";
      },
      withCredential,
    );

    const result = reported.find((call) => call.url.endsWith("/result"));
    expect(result?.body.message).toBe("浏览器任务执行失败");
  });

  it("后台边界异常也回传 bounded runtime envelope", async () => {
    stubFetch();
    const claim = makeBrowserTaskClaim("get_feed_detail");

    await executeBrowserTaskClaim(
      "http://service",
      claim,
      async (_assertLeaseActive, telemetry) => {
        telemetry.markTargetTabCreated();
        throw new BrowserTaskExecutionError(
          "DETAIL_NAVIGATION_FAILED",
          "页面原始异常不应进入持久化结果",
        );
      },
      withCredential,
    );

    const result = reported.find((call) => call.url.endsWith("/result"));
    const body = result?.body ?? {};
    const runtime = body.result && typeof body.result === "object"
      ? (body.result as Record<string, unknown>).browser_runtime_telemetry
      : undefined;
    expect(runtime).toMatchObject({
      extension_manifest_version: "3.0.0",
      diagnostic_schema_version: "C7C-1",
      target_tab_created: true,
      detail_wait_result: "NOT_REACHED",
      last_completed_runtime_boundary: "RESULT_SUBMIT_ATTEMPTED",
      parser_invocation_started: false,
    });
    expect(JSON.stringify(body.result)).not.toContain("页面原始异常");
  });

  it("结果提交拒绝时不伪造已提交状态", async () => {
    stubFetch(() => new Response(JSON.stringify({ detail: "拒绝" }), { status: 503 }));
    const claim = makeBrowserTaskClaim("get_feed_detail");

    await expect(
      executeBrowserTaskClaim(
        "http://service",
        claim,
        async (_assertLeaseActive, telemetry) => {
          telemetry.markTargetTabCreated();
          return { ok: false, status: "failed", message: "页面失败" };
        },
        withCredential,
      ),
    ).rejects.toThrow();
    const result = reported.find((call) => call.url.endsWith("/result"));
    expect(result?.body.status).toBe("failed");
    expect(result?.body.result).toMatchObject({
      browser_runtime_telemetry: {
        result_submit_attempted: true,
        result_submit_resolved: false,
      },
    });
  });
});
