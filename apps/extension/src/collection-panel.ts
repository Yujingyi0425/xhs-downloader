import type { CollectionCaptureController, CollectionCaptureResult } from "./collection-controller";
import { sanitizeCollectionReason } from "./collection-controller";

/** 收藏夹扫描面板，只展示状态、轮次和数量，不展示条目字段。 */
export function createCollectionPanel(
  document: Document,
  controllerFactory: (onProgress: (count: number, round: number) => void) => CollectionCaptureController,
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
    const current: PanelSession = { panel, controller: null, closed: false };
    session = current;
    const status = panel.querySelector<HTMLElement>("[data-status]")!;
    const progress = panel.querySelector<HTMLElement>("[data-progress]")!;
    panel.querySelector("[data-close]")?.addEventListener("click", close);
    panel.querySelector("[data-start]")?.addEventListener("click", () => {
      const start = current.panel.querySelector<HTMLButtonElement>("[data-start]");
      if (!start || current.closed || current.controller) return;
      start.disabled = true;
      status.textContent = "正在扫描";
      const controller = controllerFactory((count, round) => {
        if (current.closed || session !== current) return;
        status.textContent = "正在扫描";
        progress.textContent = `已发现 ${count} 条，第 ${round} 轮`;
      });
      current.controller = controller;
      void controller.start()
        .then((result) => {
          if (!current.closed && session === current) renderResult(status, progress, start, result);
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
}

function renderResult(status: HTMLElement, progress: HTMLElement, start: HTMLButtonElement, result: CollectionCaptureResult): void {
  start.disabled = false;
  if (result.status === "success") {
    status.textContent = `扫描完成，共发现 ${result.uniqueCount} 条唯一笔记`;
    progress.textContent = "本阶段结果尚未保存到本地服务";
  } else if (result.status === "cancelled") {
    status.textContent = `扫描未完成：${sanitizeCollectionReason(result.stopReason)}`;
  } else {
    status.textContent = `扫描未完成：${sanitizeCollectionReason(result.stopReason)}`;
  }
}
