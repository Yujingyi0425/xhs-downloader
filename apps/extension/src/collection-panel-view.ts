import type { CollectionImageItemResult } from "./collection-import-types";

export interface CollectionPanelViewState {
  panel: HTMLElement;
  importState: "idle" | "retryable" | "terminal" | "saved";
  processInFlight: boolean;
  selectedFeedIds: Set<string>;
  itemFeedIds: string[];
  results: Map<string, CollectionImageItemResult>;
}

export function renderItems(current: CollectionPanelViewState): void {
  const container = current.panel.querySelector<HTMLElement>("[data-items]");
  if (!container) return;
  const doc = current.panel.ownerDocument;
  container.replaceChildren(...current.itemFeedIds.map((feedId) => {
    const row = doc.createElement("div");
    row.className = "collection-item";
    const checkbox = doc.createElement("input");
    checkbox.type = "checkbox";
    checkbox.dataset.feedId = feedId;
    checkbox.checked = current.selectedFeedIds.has(feedId);
    checkbox.setAttribute("aria-label", `选择收藏 ${feedId}`);
    const label = doc.createElement("label");
    label.textContent = feedId;
    const state = doc.createElement("span");
    state.className = "item-status";
    state.textContent = itemStatus(current.results.get(feedId));
    label.append(state);
    row.append(checkbox, label);
    return row;
  }));
}

export function updateSelectionButtons(
  current: CollectionPanelViewState,
  selected: HTMLButtonElement,
  all: HTMLButtonElement,
  selectAll: HTMLButtonElement,
  clearSelection: HTMLButtonElement,
): void {
  const hasItems = current.itemFeedIds.length > 0 && current.importState === "saved";
  selected.hidden = !hasItems;
  all.hidden = !hasItems;
  selectAll.hidden = !hasItems;
  clearSelection.hidden = !hasItems;
  selected.disabled = !hasItems || current.processInFlight;
  all.disabled = !hasItems || current.processInFlight;
  selectAll.disabled = current.selectedFeedIds.size === current.itemFeedIds.length;
  clearSelection.disabled = current.selectedFeedIds.size === 0;
}

export function summarizeResults(items: Iterable<CollectionImageItemResult>): string {
  const values = [...items];
  const successfulItems = values.filter((item) => item.success_count > 0).length;
  const successfulImages = values.reduce((total, item) => total + item.success_count, 0);
  const failed = values.reduce((total, item) => total + item.failure_count, 0);
  const deferred = values.filter((item) => item.video_deferred).length;
  return `成功 ${successfulItems} 条（${successfulImages} 张图片）${failed ? `，失败 ${failed} 张` : ""}${deferred ? `，视频 ${deferred} 条待处理` : ""}`;
}

function itemStatus(item: CollectionImageItemResult | undefined): string {
  if (!item) return "未处理";
  if (item.video_deferred) return "视频待处理";
  if (item.media_status === "media_succeeded") return item.success_count ? `处理成功（${item.success_count} 张图片）` : "处理成功";
  if (item.media_status === "media_partial") return `部分失败：成功 ${item.success_count} 张，失败 ${item.failure_count} 张`;
  if (item.media_status === "media_failed" || item.media_status === "enrichment_failed") {
    return `失败${item.error_code ? `：${safeErrorSummary(item.error_code)}` : ""}`;
  }
  return "未处理";
}

function safeErrorSummary(code: string): string {
  const messages: Record<string, string> = {
    detail_identity_mismatch: "条目身份校验失败",
    media_identity_conflict: "媒体结果校验失败",
    enrichment_pending: "详情尚未准备好",
    unsupported_work_type: "暂不支持该类型",
  };
  return messages[code] ?? "处理失败";
}
