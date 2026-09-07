import { afterEach, describe, expect, it, vi } from "vitest";
import { createCollectionImportObservation } from "./collection-import-orchestration";
import { importCollection, CollectionImportUnauthorizedError } from "./collection-import-service";
import { senderMatchesBoard } from "./collection-import-runner";
import type { CollectionCaptureResult } from "./collection-controller";

const xsecSentinel = "synthetic-xsec-secret-never-leak";
const capabilitySentinel = "synthetic-extension-capability-never-leak";
const credential = { extensionId: "synthetic-extension", token: capabilitySentinel, installationId: "synthetic-installation" };

function capture(count: number, status: CollectionCaptureResult["status"] = "success"): CollectionCaptureResult {
  const items = new Map(Array.from({ length: count }, (_, index) => [
    `feed-${index}`,
    { feedId: `feed-${index}`, xsecToken: `${xsecSentinel}-${index}`, title: "hidden", author: "hidden", coverUrl: "hidden" },
  ]));
  return { status, boardId: "synthetic-board", uniqueCount: count, items, rounds: 1, elapsedMs: 1, stopReason: status === "success" ? "bottom_stable" : "error" };
}

function response(body: unknown, status = 201): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function saved(requestId: string, itemCount: number): object {
  return {
    snapshot_id: "snapshot-1", source_type: "board", board_id: "synthetic-board", board_revision: 1,
    request_id: requestId, captured_at: "2026-01-01T00:00:00Z", item_count: itemCount,
    fingerprint: "fingerprint", status: "saved", diff: { added: [], removed: [], retained: [] },
  };
}

describe("TC2B3 collection import contract", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("uses independent collection and capability sentinels", () => {
    expect(xsecSentinel).not.toBe(capabilitySentinel);
  });

  it.each([0, 1, 50, 500])("maps %i items in capture order", (count) => {
    const observation = createCollectionImportObservation(capture(count));
    expect(observation.payload.items).toHaveLength(count);
    expect(observation.payload.items.map((item) => item.source_order)).toEqual(
      Array.from({ length: count }, (_, index) => index),
    );
    if (count > 0) {
      expect(observation.payload.items[0]).toMatchObject({ feed_id: "feed-0", source_order: 0 });
      expect(observation.payload.items[0]).not.toHaveProperty("title");
      expect(observation.payload.items[0]).not.toHaveProperty("author");
      expect(observation.payload.items[0]).not.toHaveProperty("coverUrl");
    }
  });

  it("rejects partial capture and never creates an import observation", () => {
    for (const status of ["aborted", "cancelled", "failed"] as const) {
      expect(() => createCollectionImportObservation(capture(1, status))).toThrow("完整扫描");
    }
  });

  it("fails closed above the API limit", () => {
    expect(() => createCollectionImportObservation(capture(501))).toThrow("单次保存上限");
  });

  it("uses one request id for a retried observation", async () => {
    const observation = createCollectionImportObservation(capture(1));
    const fetchMock = vi.fn().mockResolvedValue(response(saved(observation.requestId, 1)));
    vi.stubGlobal("fetch", fetchMock);
    await importCollection("http://127.0.0.1:5556", credential, observation.payload);
    await importCollection("http://127.0.0.1:5556", credential, observation.payload);
    const first = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    const second = JSON.parse(fetchMock.mock.calls[1][1].body as string);
    expect(second.request_id).toBe(first.request_id);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("sends only the frozen API contract and reuses capability headers", async () => {
    const observation = createCollectionImportObservation(capture(1));
    const fetchMock = vi.fn().mockResolvedValue(response(saved(observation.requestId, 1)));
    vi.stubGlobal("fetch", fetchMock);
    await importCollection("http://127.0.0.1:5556", credential, observation.payload);
    const [url, init] = fetchMock.mock.calls[0];
    const body = JSON.parse(init.body as string);
    expect(url).toBe("http://127.0.0.1:5556/collections/board/synthetic-board/imports");
    expect(body).toEqual({ request_id: observation.requestId, items: [{ feed_id: "feed-0", xsec_token: `${xsecSentinel}-0`, source_order: 0 }] });
    expect(init.credentials).toBe("omit");
    expect(init.headers).toMatchObject({ Authorization: `Bearer ${capabilitySentinel}`, "X-Extension-Id": credential.extensionId });
    expect(init.headers).not.toHaveProperty("Origin");
  });

  it.each([[403, "forbidden"], [409, "conflict"], [422, "invalid"], [500, "server"]] as const)(
    "classifies HTTP %i without exposing response data",
    async (status, kind) => {
      const observation = createCollectionImportObservation(capture(1));
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ detail: `${xsecSentinel} ${capabilitySentinel}` }, status)));
      const result = await importCollection("http://service", credential, observation.payload);
      expect(result).toMatchObject({ ok: false, kind });
      expect(result.message).not.toContain(xsecSentinel);
      expect(result.message).not.toContain(capabilitySentinel);
    },
  );

  it("marks 401 for exactly one credential recovery", async () => {
    const observation = createCollectionImportObservation(capture(1));
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({}, 401)));
    await expect(importCollection("http://service", credential, observation.payload)).rejects.toBeInstanceOf(CollectionImportUnauthorizedError);
  });

  it("requires the sender to be the current board page", () => {
    expect(senderMatchesBoard("https://www.xiaohongshu.com/board/synthetic-board", "synthetic-board")).toBe(true);
    expect(senderMatchesBoard("https://www.xiaohongshu.com/board/other-board", "synthetic-board")).toBe(false);
    expect(senderMatchesBoard("https://www.xiaohongshu.com/explore/feed-1", "synthetic-board")).toBe(false);
    expect(senderMatchesBoard("https://example.com/board/synthetic-board", "synthetic-board")).toBe(false);
  });
});
