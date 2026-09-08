import type { BrowserTask } from "@xhs-downloader/contracts";

import type { BrowserPageTaskRequest, BrowserPageTaskResponse } from "./browser-page-runner";
import {
  BrowserTaskExecutionError,
  isSupportedDetailPageForFeed,
  type BrowserTaskFailureCode,
} from "./browser-task-errors";

const DETAIL_READY_ATTEMPTS = 20;
const DETAIL_READY_INTERVAL_MS = 250;

/** 等待并验证 GET_FEED_MEDIA 所需的目标详情页上下文。 */
export async function waitForMediaDetailPage(
  tabId: number,
  request: BrowserPageTaskRequest,
  assertLeaseActive: () => void,
): Promise<void> {
  const feedId = taskPayloadText(request.task, "feed_id");
  for (let attempt = 0; attempt < DETAIL_READY_ATTEMPTS; attempt += 1) {
    assertLeaseActive();
    let tab: chrome.tabs.Tab;
    try {
      tab = await chrome.tabs.get(tabId);
    } catch {
      throw new BrowserTaskExecutionError("TARGET_TAB_NOT_FOUND", "目标标签页不可用");
    }
    if (tab.status === "complete") {
      if (!tab.url) {
        throw new BrowserTaskExecutionError("DETAIL_NAVIGATION_FAILED", "详情页没有可验证地址");
      }
      if (!isSupportedDetailPageForFeed(tab.url, feedId)) {
        throw new BrowserTaskExecutionError(
          "TARGET_TAB_IDENTITY_MISMATCH",
          "详情页与目标帖子不一致",
        );
      }
      return;
    }
    await delay(DETAIL_READY_INTERVAL_MS);
  }
  throw new BrowserTaskExecutionError("DETAIL_NAVIGATION_FAILED", "详情页未在有界时间内就绪");
}

/** 将 media 任务执行异常序列化为不含凭据的结构化失败。 */
export function mediaFailureResponse(error: unknown): BrowserPageTaskResponse {
  const code: BrowserTaskFailureCode =
    error instanceof BrowserTaskExecutionError ? error.code : "MESSAGE_DISPATCH_FAILED";
  return {
    ok: false,
    status: "failed",
    message: `GET_FEED_MEDIA 执行失败：${code}`,
    result: {
      failure_code: code,
      failure_stage: "background",
    },
  };
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
