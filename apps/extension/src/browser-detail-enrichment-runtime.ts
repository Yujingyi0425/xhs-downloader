import { BrowserTaskExecutionError, isSupportedDetailPageForFeed } from "./browser-task-errors";

const DETAIL_PAGE_READY_MAX_TIMEOUT_MS = 15_000;
const DETAIL_PAGE_READY_INTERVAL_MS = 250;
const DETAIL_PAGE_READY_MAX_ATTEMPTS =
  DETAIL_PAGE_READY_MAX_TIMEOUT_MS / DETAIL_PAGE_READY_INTERVAL_MS;
const DETAIL_PAGE_URL_STABLE_ATTEMPTS = 4;

/** 在详情 enrichment 解析前等待有界、身份匹配的详情页状态。 */
export async function waitForDetailEnrichmentPage(
  tabId: number,
  feedId: string,
  assertLeaseActive: () => void,
): Promise<void> {
  for (let attempt = 0; attempt < DETAIL_PAGE_READY_MAX_ATTEMPTS; attempt += 1) {
    assertLeaseActive();
    let tab: chrome.tabs.Tab;
    try {
      tab = await chrome.tabs.get(tabId);
    } catch {
      throw new BrowserTaskExecutionError("TARGET_TAB_NOT_FOUND", "目标详情页不可用");
    }
    if (tab.status === "complete") {
      if (!tab.url) {
        throw new BrowserTaskExecutionError(
          "DETAIL_NAVIGATION_FAILED",
          "详情页没有可验证地址",
        );
      }
      if (!isSupportedDetailPageForFeed(tab.url, feedId)) {
        throw new BrowserTaskExecutionError(
          "TARGET_TAB_IDENTITY_MISMATCH",
          "详情页与目标帖子不一致",
        );
      }
      return;
    }
    if (
      attempt >= DETAIL_PAGE_URL_STABLE_ATTEMPTS &&
      hasExpectedDetailUrl(tab, feedId)
    ) {
      return;
    }
    await delay(DETAIL_PAGE_READY_INTERVAL_MS);
  }
  throw new BrowserTaskExecutionError(
    "DETAIL_NAVIGATION_FAILED",
    "详情页未在有界时间内就绪",
  );
}

function hasExpectedDetailUrl(tab: chrome.tabs.Tab, feedId: string): boolean {
  return [tab.url, tab.pendingUrl].some(
    (value) => typeof value === "string" && isSupportedDetailPageForFeed(value, feedId),
  );
}

function delay(milliseconds: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}
