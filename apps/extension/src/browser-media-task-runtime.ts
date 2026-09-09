import type { BrowserTask } from "@xhs-downloader/contracts";

import type { BrowserPageTaskRequest, BrowserPageTaskResponse } from "./browser-page-runner";
import {
  BrowserTaskExecutionError,
  isSupportedDetailPageForFeed,
  type BrowserTaskFailureCode,
} from "./browser-task-errors";

const DETAIL_READY_BASE_TIMEOUT_MS = 5_000;
const DETAIL_READY_MAX_TIMEOUT_MS = 10_000;
const DETAIL_READY_INTERVAL_MS = 250;
const DETAIL_READY_MAX_ATTEMPTS = DETAIL_READY_MAX_TIMEOUT_MS / DETAIL_READY_INTERVAL_MS;
const MAX_NAVIGATION_DIAGNOSTIC_ELAPSED_MS = 60_000;

type NavigationTelemetry = {
  target_tab_exists: boolean;
  last_tab_status: "loading" | "complete" | "unknown" | "missing";
  last_route_class:
    | "/blank"
    | "/explore/<feed_id>"
    | "/discovery/item/<feed_id>"
    | "/board/<board_id>"
    | "/other-xhs"
    | "/non-xhs"
    | "/unknown";
  url_host_is_xhs: boolean;
  expected_route_matched: boolean;
  elapsed_ms: number;
  tab_removed: boolean;
};

type NavigationCreationObservation = {
  created_tab_id: number;
  create_returned: boolean;
  chrome_runtime_last_error_present: boolean;
};

type NavigationFailure = BrowserTaskExecutionError & {
  navigation_telemetry?: NavigationTelemetry;
  navigation_creation?: NavigationCreationObservation;
};

/** 等待并验证 GET_FEED_MEDIA 所需的目标详情页上下文。 */
export async function waitForMediaDetailPage(
  tabId: number,
  request: BrowserPageTaskRequest,
  assertLeaseActive: () => void,
  creationObservation: NavigationCreationObservation = {
    created_tab_id: tabId,
    create_returned: true,
    chrome_runtime_last_error_present: false,
  },
): Promise<void> {
  const feedId = taskPayloadText(request.task, "feed_id");
  const startedAt = Date.now();
  let lastTelemetry = lastKnownTelemetry(startedAt);
  for (let attempt = 0; attempt < DETAIL_READY_MAX_ATTEMPTS; attempt += 1) {
    assertLeaseActive();
    let tab: chrome.tabs.Tab;
    try {
      tab = await chrome.tabs.get(tabId);
    } catch {
      throw withNavigationTelemetry(
        new BrowserTaskExecutionError("TARGET_TAB_NOT_FOUND", "目标标签页不可用"),
        missingTabTelemetry(startedAt),
        creationObservation,
      );
    }
    const telemetry = tabTelemetry(tab, feedId, startedAt);
    lastTelemetry = telemetry;
    if (tab.status === "complete") {
      if (!tab.url) {
        throw withNavigationTelemetry(
          new BrowserTaskExecutionError("DETAIL_NAVIGATION_FAILED", "详情页没有可验证地址"),
          telemetry,
          creationObservation,
        );
      }
      if (!isSupportedDetailPageForFeed(tab.url, feedId)) {
        throw withNavigationTelemetry(
          new BrowserTaskExecutionError(
            "TARGET_TAB_IDENTITY_MISMATCH",
            "详情页与目标帖子不一致",
          ),
          telemetry,
          creationObservation,
        );
      }
      return;
    }
    if (Date.now() - startedAt >= DETAIL_READY_BASE_TIMEOUT_MS) {
      if (!hasExpectedPendingDetail(tab, feedId)) {
        throw withNavigationTelemetry(
          new BrowserTaskExecutionError("DETAIL_NAVIGATION_FAILED", "详情页未在有界时间内就绪"),
          telemetry,
          creationObservation,
        );
      }
    }
    await delay(DETAIL_READY_INTERVAL_MS);
  }
  throw withNavigationTelemetry(
    new BrowserTaskExecutionError("DETAIL_NAVIGATION_FAILED", "详情页未在有界时间内就绪"),
    lastTelemetry,
    creationObservation,
  );
}

function hasExpectedPendingDetail(tab: chrome.tabs.Tab, feedId: string): boolean {
  return (
    tab.status === "loading" &&
    typeof tab.pendingUrl === "string" &&
    isSupportedDetailPageForFeed(tab.pendingUrl, feedId)
  );
}

/** 将 media 任务执行异常序列化为不含凭据的结构化失败。 */
export function mediaFailureResponse(error: unknown): BrowserPageTaskResponse {
  const code: BrowserTaskFailureCode =
    error instanceof BrowserTaskExecutionError ? error.code : "MESSAGE_DISPATCH_FAILED";
  const telemetry = navigationTelemetry(error);
  return {
    ok: false,
    status: "failed",
    message: `GET_FEED_MEDIA 执行失败：${code}`,
    result: {
      failure_code: code,
      failure_stage: "background",
      ...(telemetry ?? {}),
    },
  };
}

function withNavigationTelemetry(
  error: BrowserTaskExecutionError,
  telemetry: NavigationTelemetry,
  creation: NavigationCreationObservation,
): NavigationFailure {
  const enriched = error as NavigationFailure;
  enriched.navigation_telemetry = telemetry;
  enriched.navigation_creation = creation;
  return enriched;
}

function navigationTelemetry(error: unknown): NavigationTelemetry | undefined {
  if (!error || typeof error !== "object") return undefined;
  const value = error as NavigationFailure;
  return value.navigation_telemetry;
}

function tabTelemetry(
  tab: chrome.tabs.Tab,
  feedId: string,
  startedAt: number,
): NavigationTelemetry {
  const url = typeof tab.url === "string" ? tab.url : undefined;
  return {
    target_tab_exists: true,
    last_tab_status: safeTabStatus(tab.status),
    last_route_class: safeRouteClass(url),
    url_host_is_xhs: isXhsHost(url),
    expected_route_matched: Boolean(url && isSupportedDetailPageForFeed(url, feedId)),
    elapsed_ms: boundedElapsed(startedAt),
    tab_removed: false,
  };
}

function missingTabTelemetry(startedAt: number): NavigationTelemetry {
  return {
    target_tab_exists: false,
    last_tab_status: "missing",
    last_route_class: "/unknown",
    url_host_is_xhs: false,
    expected_route_matched: false,
    elapsed_ms: boundedElapsed(startedAt),
    tab_removed: true,
  };
}

function lastKnownTelemetry(startedAt: number): NavigationTelemetry {
  return {
    target_tab_exists: true,
    last_tab_status: "loading",
    last_route_class: "/unknown",
    url_host_is_xhs: false,
    expected_route_matched: false,
    elapsed_ms: boundedElapsed(startedAt),
    tab_removed: false,
  };
}

function safeTabStatus(status: chrome.tabs.Tab["status"]): "loading" | "complete" | "unknown" {
  if (status === "loading" || status === "complete") return status;
  return "unknown";
}

function safeRouteClass(value: string | undefined): NavigationTelemetry["last_route_class"] {
  if (!value) return "/unknown";
  try {
    const url = new URL(value);
    if (url.protocol === "about:") return "/blank";
    if (url.hostname !== "www.xiaohongshu.com") return "/non-xhs";
    const segments = url.pathname.split("/").filter(Boolean);
    if (segments[0] === "explore" && segments.length >= 2) return "/explore/<feed_id>";
    if (segments[0] === "discovery" && segments[1] === "item") {
      return "/discovery/item/<feed_id>";
    }
    if (segments[0] === "board") return "/board/<board_id>";
    return "/other-xhs";
  } catch {
    return "/unknown";
  }
}

function isXhsHost(value: string | undefined): boolean {
  if (!value) return false;
  try {
    return new URL(value).hostname === "www.xiaohongshu.com";
  } catch {
    return false;
  }
}

function boundedElapsed(startedAt: number): number {
  return Math.min(
    MAX_NAVIGATION_DIAGNOSTIC_ELAPSED_MS,
    Math.max(0, Math.trunc(Date.now() - startedAt)),
  );
}

function taskPayloadText(task: BrowserTask, field: string): string {
  const value = task.payload[field];
  if (typeof value !== "string" || !value) {
    throw new BrowserTaskExecutionError("DETAIL_NAVIGATION_FAILED", `浏览器任务缺少参数 ${field}`);
  }
  return value;
}

function delay(milliseconds: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}
