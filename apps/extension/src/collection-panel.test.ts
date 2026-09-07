import { describe, expect, it, vi } from "vitest";
import { createCollectionPanel } from "./collection-panel";
import type { CollectionCaptureController, CollectionCaptureResult } from "./collection-controller";
import type { CollectionImportObservation, CollectionImportResponse } from "./collection-import-types";

function deferred<T>(): { promise: Promise<T>; resolve(value: T): void } {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((next) => { resolve = next; });
  return { promise, resolve };
}

function result(status: CollectionCaptureResult["status"] = "success"): CollectionCaptureResult {
  return { status, boardId: null, uniqueCount: 0, items: new Map(), rounds: 1, elapsedMs: 1, stopReason: status === "success" ? "bottom_stable" : "cancelled" };
}

function fakeController(start: Promise<CollectionCaptureResult>, cancel: () => void): CollectionCaptureController {
  return { start: () => start, cancel } as unknown as CollectionCaptureController;
}

function click(root: ShadowRoot, selector: string): void {
  root.querySelector<HTMLButtonElement>(selector)?.click();
}

function successfulResult(): CollectionCaptureResult {
  return {
    ...result(),
    boardId: "synthetic-board",
    uniqueCount: 1,
    items: new Map([["feed-1", { feedId: "feed-1", xsecToken: "synthetic-token" }]]),
  };
}

describe("TC1C-R1 collection panel lifecycle", () => {
  it("R1-01 cancels Scan A when the panel closes", () => {
    const a = deferred<CollectionCaptureResult>();
    let cancelled = false;
    const panel = createCollectionPanel(document, () => fakeController(a.promise, () => { cancelled = true; }));
    panel.toggle();
    click(panel.getRootForTest(), "[data-start]");
    panel.close();
    expect(cancelled).toBe(true);
  });

  it("R1-02 keeps Scan B controller after Scan A completes later", async () => {
    const a = deferred<CollectionCaptureResult>();
    const b = deferred<CollectionCaptureResult>();
    const controllers = [fakeController(a.promise, () => undefined), fakeController(b.promise, () => undefined)];
    let created = 0;
    const panel = createCollectionPanel(document, () => controllers[created++]);
    panel.toggle();
    click(panel.getRootForTest(), "[data-start]");
    panel.close();
    panel.toggle();
    const rootB = panel.getRootForTest();
    click(rootB, "[data-start]");
    a.resolve(result("cancelled"));
    await Promise.resolve();
    expect(created).toBe(2);
    expect(rootB.querySelector("[data-status]")?.textContent).toBe("正在扫描");
    b.resolve(result());
    await Promise.resolve();
  });

  it("R1-03 does not create Scan C while Scan B is active", () => {
    const a = deferred<CollectionCaptureResult>();
    const b = deferred<CollectionCaptureResult>();
    const controllers = [fakeController(a.promise, () => undefined), fakeController(b.promise, () => undefined)];
    let created = 0;
    const panel = createCollectionPanel(document, () => controllers[created++]);
    panel.toggle();
    click(panel.getRootForTest(), "[data-start]");
    panel.close();
    panel.toggle();
    const rootB = panel.getRootForTest();
    click(rootB, "[data-start]");
    click(rootB, "[data-start]");
    expect(created).toBe(2);
  });

  it("R1-04 old Scan A completion cannot modify Panel B", async () => {
    const a = deferred<CollectionCaptureResult>();
    const b = deferred<CollectionCaptureResult>();
    const controllers = [fakeController(a.promise, () => undefined), fakeController(b.promise, () => undefined)];
    let created = 0;
    const panel = createCollectionPanel(document, () => controllers[created++]);
    panel.toggle();
    click(panel.getRootForTest(), "[data-start]");
    panel.close();
    panel.toggle();
    const rootB = panel.getRootForTest();
    click(rootB, "[data-start]");
    a.resolve({ ...result(), uniqueCount: 999 });
    await Promise.resolve();
    expect(rootB.querySelector("[data-status]")?.textContent).toBe("正在扫描");
    b.resolve(result());
    await Promise.resolve();
  });

  it("R1-05 releases the guard only after Scan B completes", async () => {
    const b = deferred<CollectionCaptureResult>();
    let created = 0;
    const panel = createCollectionPanel(document, () => { created += 1; return fakeController(b.promise, () => undefined); });
    panel.toggle();
    const root = panel.getRootForTest();
    click(root, "[data-start]");
    click(root, "[data-start]");
    expect(created).toBe(1);
    b.resolve(result());
    await Promise.resolve();
    await Promise.resolve();
    click(root, "[data-start]");
    expect(created).toBe(2);
  });

  it("R1-06 detached old completion is harmless", async () => {
    const a = deferred<CollectionCaptureResult>();
    const panel = createCollectionPanel(document, () => fakeController(a.promise, () => undefined));
    panel.toggle();
    click(panel.getRootForTest(), "[data-start]");
    panel.close();
    a.resolve(result("failed"));
    await Promise.resolve();
    expect(document.querySelector("#xhs-collection-extension")).not.toBeNull();
  });

  it("imports only after success and retries the same observation", async () => {
    const scan = deferred<CollectionCaptureResult>();
    const observations: CollectionImportObservation[] = [];
    let failOnce = true;
    const onImport = vi.fn(async (observation: CollectionImportObservation): Promise<CollectionImportResponse> => {
      observations.push(observation);
      if (failOnce) {
        failOnce = false;
        return { ok: false, message: "保存失败，请检查本地服务后重试", kind: "network" };
      }
      return { ok: true, message: "收藏夹已保存", result: { snapshot_id: "s", source_type: "board", board_id: "synthetic-board", board_revision: 1, request_id: observation.requestId, captured_at: "2026-01-01T00:00:00Z", item_count: 1, fingerprint: "f", status: "saved", diff: { added: [], removed: [], retained: [] } } };
    });
    const panel = createCollectionPanel(document, () => fakeController(scan.promise, () => undefined), onImport);
    panel.toggle();
    const root = panel.getRootForTest();
    click(root, "[data-start]");
    scan.resolve(successfulResult());
    await Promise.resolve();
    await Promise.resolve();
    expect(onImport).toHaveBeenCalledTimes(1);
    const firstRequestId = observations[0].requestId;
    expect(root.querySelector("[data-status]")?.textContent).toContain("保存失败");
    click(root, "[data-start]");
    await Promise.resolve();
    await Promise.resolve();
    expect(onImport).toHaveBeenCalledTimes(2);
    expect(observations[1].requestId).toBe(firstRequestId);
    expect(root.querySelector("[data-status]")?.textContent).toBe("已保存到本地服务");
  });
});
