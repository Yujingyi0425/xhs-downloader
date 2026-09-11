import { afterEach, describe, expect, it, vi } from "vitest";
import { processCollectionImages } from "./collection-image-service";

const credential = { token: "synthetic-token", extensionId: "synthetic-extension" };
const result = {
  snapshot_id: "snapshot-1",
  status: "ready",
  items: [{
    feed_id: "feed-a",
    source_order: 0,
    enrichment_status: "succeeded",
    media_status: "media_succeeded",
    image_count: 1,
    success_count: 1,
    failure_count: 0,
    video_deferred: false,
  }],
};

afterEach(() => vi.restoreAllMocks());

describe("collection image process request", () => {
  it("forwards selected_feed_ids without changing the selected identity", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(result), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const response = await processCollectionImages("http://127.0.0.1:5556", credential, {
      snapshot_id: "snapshot-1",
      board_id: "board-1",
      retry_failed: true,
      selected_feed_ids: ["feed-a", "feed-c"],
    });

    expect(response.ok).toBe(true);
    const request = fetchMock.mock.calls[0][1] as RequestInit;
    expect(JSON.parse(String(request.body))).toEqual({
      board_id: "board-1",
      retry_failed: true,
      selected_feed_ids: ["feed-a", "feed-c"],
    });
  });

  it("omits selected_feed_ids only for an explicit full processing request", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(result), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await processCollectionImages("http://127.0.0.1:5556", credential, {
      snapshot_id: "snapshot-1",
      board_id: "board-1",
      retry_failed: true,
    });

    const request = fetchMock.mock.calls[0][1] as RequestInit;
    expect(JSON.parse(String(request.body))).toEqual({ board_id: "board-1", retry_failed: true });
  });
});
