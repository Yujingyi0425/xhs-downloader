import { describe, expect, it } from "vitest";
import { createCollectionPanel } from "./collection-panel";
import type { CollectionCaptureController, CollectionCaptureResult } from "./collection-controller";

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
});
