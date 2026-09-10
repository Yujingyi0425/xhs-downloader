import type { CollectionCaptureController, CollectionCaptureResult } from "./collection-controller";
import { sanitizeCollectionReason } from "./collection-controller";
import { createCollectionImportObservation } from "./collection-import-orchestration";
import type {
  CollectionImportObservation,
  CollectionImportResponse,
} from "./collection-import-types";

/** 收藏夹扫描面板，只展示状态、轮次和数量，不展示条目字段。 */
export function createCollectionPanel(
  document: Document,
  controllerFactory: (onProgress: (count: number, round: number) => void) => CollectionCaptureController,
  onImport?: (observation: CollectionImportObservation) => Promise<CollectionImportResponse>,
): { toggle(): void; close(): void; getRootForTest(): ShadowRoot } {
  const host = document.createElement("div");
  host.id = "xhs-collection-extension";
  const root = host.attachShadow({ mode: "closed" });
  const style = document.createElement("style");
  style.textContent = `:host{all:initial}aside{position:fixed;right:20px;top:72px;z-index:2147483647;width:300px;padding:18px;border-radius:14px;background:#fff;color:#222;box-shadow:0 8px 30px #0003;font:14px system-ui,sans-serif}h2{font-size:17px;margin:0 0 14px}p{margin:8px 0;color:#666}button{border:0;border-radius:8px;padding:9px 14px;background:#ff2442;color:#fff;cursor:pointer}button.secondary{margin-left:8px;background:#eee;color:#333}`;
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
    panel.innerHTML = `<h2>小红书旅行收藏夹</h2><p data-status>尚未扫描</p><p data-progress></p><button data-start>扫描当前收藏夹</button><button class="secondary" data-close>关闭</button>`;
    root.append(panel);
    const current: PanelSession = {
      panel,
      controller: null,
      closed: false,
      importInFlight: false,
      importState: "idle",
    };
    session = current;
    const status = panel.querySelector<HTMLElement>("[data-status]")!;
    const progress = panel.querySelector<HTMLElement>("[data-progress]")!;
    panel.querySelector("[data-close]")?.addEventListener("click", close);
    panel.querySelector("[data-start]")?.addEventListener("click", () => {
      const start = current.panel.querySelector<HTMLButtonElement>("[data-start]");
      if (!start || current.closed || current.controller || current.importInFlight) return;
      if (current.observation && current.importState === "retryable" && onImport) {
        void submitImport(current, start, status, progress, current.observation, onImport);
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
            const observation = createCollectionImportObservation(result);
            current.observation = observation;
            void submitImport(current, start, status, progress, observation, onImport);
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

interface PanelSession {
  panel: HTMLElement;
  controller: CollectionCaptureController | null;
  closed: boolean;
  observation?: CollectionImportObservation;
  importInFlight: boolean;
  importState: "idle" | "retryable" | "terminal" | "saved";
}

function renderScanResult(status: HTMLElement, progress: HTMLElement, start: HTMLButtonElement, result: CollectionCaptureResult): void {
  start.disabled = false;
  start.textContent = "重新扫描";
  if (result.status === "success") {
    status.textContent = `扫描完成，共发现 ${result.uniqueCount} 条唯一笔记`;
    progress.textContent = "本阶段结果尚未保存到本地服务";
  } else if (result.status === "cancelled") {
    status.textContent = `扫描未完成：${sanitizeCollectionReason(result.stopReason)}`;
  } else {
    status.textContent = `扫描未完成：${sanitizeCollectionReason(result.stopReason)}`;
  }
}

async function submitImport(
  current: PanelSession,
  start: HTMLButtonElement,
  status: HTMLElement,
  progress: HTMLElement,
  observation: CollectionImportObservation,
  onImport: (observation: CollectionImportObservation) => Promise<CollectionImportResponse>,
): Promise<void> {
  current.importInFlight = true;
  start.disabled = true;
  start.textContent = "保存中";
  status.textContent = "正在保存到本地服务";
  try {
    const response = await onImport(observation);
    if (current.closed) return;
    current.importInFlight = false;
    start.disabled = false;
    if (response.ok && response.result) {
      current.importState = "saved";
      start.textContent = "重新扫描";
      if (response.processing) {
        const processing = response.processing;
        const deferred = processing.items.filter((item) => item.video_deferred).length;
        const failed = processing.items.reduce((total, item) => total + item.failure_count, 0);
        status.textContent = "已保存并完成图片处理";
        progress.textContent = `已处理 ${processing.items.length} 条，成功 ${processing.items.reduce((total, item) => total + item.success_count, 0)} 张${failed ? `，失败 ${failed} 张` : ""}${deferred ? `，视频 ${deferred} 条待处理` : ""}`;
      } else {
        status.textContent = "已保存到本地服务";
        progress.textContent = `已保存 ${response.result.item_count} 条`;
      }
    } else if (response.kind === "network" || response.kind === "server") {
      current.importState = "retryable";
      start.textContent = "重试保存";
      status.textContent = response.message;
      progress.textContent = "本次扫描结果仍可重试保存";
    } else {
      current.importState = "terminal";
      start.textContent = "重新扫描";
      status.textContent = response.message;
      progress.textContent = "请重新扫描后再试";
    }
  } catch {
    if (current.closed) return;
    current.importInFlight = false;
    current.importState = "retryable";
    start.disabled = false;
    start.textContent = "重试保存";
    status.textContent = "保存失败，请稍后重试";
    progress.textContent = "本次扫描结果仍可重试保存";
  }
}
