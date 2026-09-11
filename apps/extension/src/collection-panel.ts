import type { CollectionCaptureController, CollectionCaptureResult } from "./collection-controller";
import { sanitizeCollectionReason } from "./collection-controller";
import { createCollectionImportObservation } from "./collection-import-orchestration";
import {
  renderItems,
  summarizeResults,
  updateSelectionButtons,
  type CollectionPanelViewState,
} from "./collection-panel-view";
import type {
  CollectionImageProcessResponse,
  CollectionImageItemResult,
  CollectionImportObservation,
  CollectionImportResponse,
  CollectionImportResult,
} from "./collection-import-types";

type CollectionImportHandler =
  (observation: CollectionImportObservation) => Promise<CollectionImportResponse>;
type CollectionImageProcessHandler =
  (observation: CollectionImportObservation, imported: CollectionImportResult, selectedFeedIds?: string[]) => Promise<CollectionImageProcessResponse>;

/** 收藏夹扫描与图片处理面板；选择 identity 始终使用 feed_id。 */
export function createCollectionPanel(
  document: Document,
  controllerFactory: (onProgress: (count: number, round: number) => void) => CollectionCaptureController,
  onImport?: CollectionImportHandler,
  onProcess?: CollectionImageProcessHandler,
): { toggle(): void; close(): void; getRootForTest(): ShadowRoot } {
  const host = document.createElement("div");
  host.id = "xhs-collection-extension";
  const root = host.attachShadow({ mode: "closed" });
  const style = document.createElement("style");
  style.textContent = `:host{all:initial}aside{position:fixed;right:20px;top:72px;z-index:2147483647;width:340px;max-height:calc(100vh - 100px);overflow:auto;padding:18px;border-radius:14px;background:#fff;color:#222;box-shadow:0 8px 30px #0003;font:14px system-ui,sans-serif}h2{font-size:17px;margin:0 0 14px}p{margin:8px 0;color:#666}.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}button{border:0;border-radius:8px;padding:9px 14px;background:#ff2442;color:#fff;cursor:pointer}button.secondary{background:#eee;color:#333}button:disabled{opacity:.55;cursor:default}[data-items]{margin-top:12px;border-top:1px solid #eee}.collection-item{display:grid;grid-template-columns:auto 1fr;gap:8px;padding:10px 0;border-bottom:1px solid #eee}.collection-item label{min-width:0;overflow-wrap:anywhere}.item-status{display:block;margin-top:3px;color:#777;font-size:12px}`;
  root.append(style);
  let panel: HTMLElement | null = null;
  let session: PanelSession | null = null;

  const close = (): void => {
    const current = session;
    if (!current) return;
    current.closed = true;
    current.controller?.cancel();
    current.panel.remove();
    session = null;
    panel = null;
  };

  const toggle = (): void => {
    if (panel) return close();
    panel = document.createElement("aside");
    panel.innerHTML = `<h2>小红书旅行收藏夹</h2><p data-status>尚未扫描</p><p data-progress></p><div class="actions"><button data-start>扫描当前收藏夹</button><button class="secondary" data-process-selected hidden>处理选中</button><button class="secondary" data-process-all hidden>处理全部</button></div><div class="actions"><button class="secondary" data-select-all hidden>全选</button><button class="secondary" data-clear-selection hidden>清空选择</button><button class="secondary" data-close>关闭</button></div><div data-items></div>`;
    root.append(panel);
    const current: PanelSession = {
      panel,
      controller: null,
      closed: false,
      importInFlight: false,
      processInFlight: false,
      importState: "idle",
      selectedFeedIds: new Set(),
      itemFeedIds: [],
      results: new Map(),
    };
    session = current;
    const status = panel.querySelector<HTMLElement>("[data-status]")!;
    const progress = panel.querySelector<HTMLElement>("[data-progress]")!;
    const items = panel.querySelector<HTMLElement>("[data-items]")!;
    const start = panel.querySelector<HTMLButtonElement>("[data-start]")!;
    const selected = panel.querySelector<HTMLButtonElement>("[data-process-selected]")!;
    const all = panel.querySelector<HTMLButtonElement>("[data-process-all]")!;
    const selectAll = panel.querySelector<HTMLButtonElement>("[data-select-all]")!;
    const clearSelection = panel.querySelector<HTMLButtonElement>("[data-clear-selection]")!;

    panel.querySelector("[data-close]")?.addEventListener("click", close);
    items.addEventListener("change", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLInputElement) || target.dataset.feedId === undefined) return;
      if (target.checked) current.selectedFeedIds.add(target.dataset.feedId);
      else current.selectedFeedIds.delete(target.dataset.feedId);
      updateSelectionButtons(current, selected, all, selectAll, clearSelection);
    });
    selectAll.addEventListener("click", () => {
      current.selectedFeedIds = new Set(current.itemFeedIds);
      renderItems(current);
      updateSelectionButtons(current, selected, all, selectAll, clearSelection);
    });
    clearSelection.addEventListener("click", () => {
      current.selectedFeedIds.clear();
      renderItems(current);
      updateSelectionButtons(current, selected, all, selectAll, clearSelection);
    });
    selected.addEventListener("click", () => {
      if (!current.selectedFeedIds.size) {
        status.textContent = "请先选择至少一条收藏";
        return;
      }
      void processSelection(current, status, progress, selected, all, [...current.selectedFeedIds], onProcess);
    });
    all.addEventListener("click", () => {
      void processSelection(current, status, progress, selected, all, undefined, onProcess);
    });
    start.addEventListener("click", () => {
      if (current.closed || current.controller || current.importInFlight || current.processInFlight) return;
      if (current.observation && current.importState === "retryable" && onImport) {
        void submitImport(current, start, status, progress, selected, all, selectAll, clearSelection, onImport);
        return;
      }
      start.disabled = true;
      start.textContent = "扫描中";
      status.textContent = "正在扫描";
      const controller = controllerFactory((count, round) => {
        if (current.closed || session !== current) return;
        status.textContent = "正在扫描";
        progress.textContent = `已发现 ${count} 条，第 ${round} 轮`;
      });
      current.controller = controller;
      void controller.start()
        .then((result) => {
          if (current.closed || session !== current) return;
          if (result.status !== "success" || !result.boardId || !onImport) {
            renderScanResult(status, progress, start, result);
            return;
          }
          try {
            current.observation = createCollectionImportObservation(result);
            current.importState = "idle";
            current.itemFeedIds = current.observation.payload.items.map((item) => item.feed_id);
            current.selectedFeedIds.clear();
            current.results.clear();
            renderItems(current);
            void submitImport(current, start, status, progress, selected, all, selectAll, clearSelection, onImport);
          } catch (error) {
            current.importState = "terminal";
            start.disabled = false;
            start.textContent = "重新扫描";
            status.textContent = error instanceof Error ? error.message : "扫描结果无法保存";
          }
        })
        .finally(() => {
          if (session === current) current.controller = null;
        });
    });
  };
  document.documentElement.append(host);
  return { toggle, close, getRootForTest: () => root };
}

interface PanelSession extends CollectionPanelViewState {
  panel: HTMLElement;
  controller: CollectionCaptureController | null;
  closed: boolean;
  observation?: CollectionImportObservation;
  imported?: CollectionImportResult;
  importInFlight: boolean;
  processInFlight: boolean;
  importState: "idle" | "retryable" | "terminal" | "saved";
  selectedFeedIds: Set<string>;
  itemFeedIds: string[];
  results: Map<string, CollectionImageItemResult>;
}

function renderScanResult(status: HTMLElement, progress: HTMLElement, start: HTMLButtonElement, result: CollectionCaptureResult): void {
  start.disabled = false;
  start.textContent = "重新扫描";
  if (result.status === "success") {
    status.textContent = `扫描完成，共发现 ${result.uniqueCount} 条唯一笔记`;
    progress.textContent = "本阶段结果尚未保存到本地服务";
  } else {
    status.textContent = `扫描未完成：${sanitizeCollectionReason(result.stopReason)}`;
  }
}

async function submitImport(
  current: PanelSession,
  start: HTMLButtonElement,
  status: HTMLElement,
  progress: HTMLElement,
  selected: HTMLButtonElement,
  all: HTMLButtonElement,
  selectAll: HTMLButtonElement,
  clearSelection: HTMLButtonElement,
  onImport: CollectionImportHandler,
): Promise<void> {
  if (!current.observation) return;
  current.importInFlight = true;
  start.disabled = true;
  selected.disabled = true;
  all.disabled = true;
  start.textContent = "保存中";
  status.textContent = "正在保存到本地服务";
  try {
    const response = await onImport(current.observation);
    if (current.closed) return;
    current.importInFlight = false;
    if (response.ok && response.result) {
      current.importState = "saved";
      current.imported = response.result;
      current.itemFeedIds = current.observation.payload.items.map((item) => item.feed_id);
      renderItems(current);
      start.disabled = false;
      start.textContent = "重新扫描";
      status.textContent = "已保存，请选择要处理的收藏";
      progress.textContent = `已保存 ${response.result.item_count} 条`;
      updateSelectionButtons(current, selected, all, selectAll, clearSelection);
      return;
    }
    current.importState = response.kind === "network" || response.kind === "server" ? "retryable" : "terminal";
    clearCollectionItems(current);
    start.disabled = false;
    start.textContent = current.importState === "retryable" ? "重试保存" : "重新扫描";
    status.textContent = response.message;
    progress.textContent = current.importState === "retryable" ? "本次扫描结果仍可重试保存" : "请重新扫描后再试";
  } catch {
    if (current.closed) return;
    current.importInFlight = false;
    current.importState = "retryable";
    clearCollectionItems(current);
    start.disabled = false;
    start.textContent = "重试保存";
    status.textContent = "保存失败，请稍后重试";
    progress.textContent = "本次扫描结果仍可重试保存";
  }
}

function clearCollectionItems(current: PanelSession): void {
  current.itemFeedIds = [];
  current.selectedFeedIds.clear();
  current.results.clear();
  renderItems(current);
}

async function processSelection(
  current: PanelSession,
  status: HTMLElement,
  progress: HTMLElement,
  selected: HTMLButtonElement,
  all: HTMLButtonElement,
  selectedFeedIds: string[] | undefined,
  onProcess: CollectionImageProcessHandler | undefined,
): Promise<void> {
  if (!onProcess || !current.observation || !current.imported) {
    status.textContent = "请先保存扫描结果";
    return;
  }
  current.processInFlight = true;
  selected.disabled = true;
  all.disabled = true;
  status.textContent = selectedFeedIds ? "正在处理选中的收藏" : "正在处理全部收藏";
  progress.textContent = "图片处理中";
  try {
    const response = await onProcess(current.observation, current.imported, selectedFeedIds);
    if (current.closed) return;
    current.processInFlight = false;
    if (!response.ok || !response.result) {
      selected.disabled = false;
      all.disabled = false;
      status.textContent = response.message;
      progress.textContent = "本次处理未完成，可稍后重试";
      return;
    }
    for (const item of response.result.items) current.results.set(item.feed_id, item);
    renderItems(current);
    selected.disabled = false;
    all.disabled = false;
    status.textContent = response.result.status === "partial" ? "图片处理部分完成" : "图片处理完成";
    progress.textContent = summarizeResults(current.results.values());
  } catch {
    if (current.closed) return;
    current.processInFlight = false;
    selected.disabled = false;
    all.disabled = false;
    status.textContent = "图片处理失败，请稍后重试";
    progress.textContent = "本次处理未完成，可稍后重试";
  }
}
