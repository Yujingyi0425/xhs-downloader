import type { CollectionCaptureResult } from "./collection-controller";
import {
  isSuccessfulCapture,
  type CollectionImportObservation,
  type CollectionImportPayload,
  type CollectionImportResult,
  type CollectionImportResponse,
  type CollectionImageProcessResponse,
  type NoteExtractionResponse,
} from "./collection-import-types";

/** 把一次成功捕获冻结为可重试的内存 observation。 */
export function createCollectionImportObservation(
  result: CollectionCaptureResult,
): CollectionImportObservation {
  if (!isSuccessfulCapture(result)) throw new Error("只有完整扫描才能保存");
  const boardId = result.boardId;
  if (!boardId) throw new Error("扫描结果缺少收藏夹标识");
  const items = Array.from(result.items.values()).map((item, sourceOrder) => ({
    feed_id: item.feedId,
    xsec_token: item.xsecToken,
    source_order: sourceOrder,
  }));
  const requestId = stableRequestId(boardId, items.map((item) => item.feed_id));
  if (items.length > 500) throw new Error("收藏夹条目超过单次保存上限");
  return {
    requestId,
    payload: { request_id: requestId, board_id: boardId, items },
  };
}

function stableRequestId(boardId: string, feedIds: string[]): string {
  let hash = 2166136261;
  for (const char of `${boardId}\u0000${feedIds.join("\u0000")}`) {
    hash ^= char.codePointAt(0) ?? 0;
    hash = Math.imul(hash, 16777619);
  }
  return `tc2-board-${(hash >>> 0).toString(16).padStart(8, "0")}`;
}

/** 通过 background message 保存 observation；重试时传入同一个 observation。 */
export async function sendCollectionImport(
  payload: CollectionImportPayload,
): Promise<CollectionImportResponse> {
  try {
    const response = await chrome.runtime.sendMessage<
      { type: "collection-import"; payload: CollectionImportPayload },
      CollectionImportResponse
    >({ type: "collection-import", payload });
    return response ?? { ok: false, message: "本地服务没有返回保存结果", kind: "network" };
  } catch {
    return { ok: false, message: "保存失败，请检查本地服务后重试", kind: "network" };
  }
}

/** 对已保存快照启动图片生产；视频条目由服务端安全 deferred。 */
export async function sendCollectionImages(
  observation: CollectionImportObservation,
  imported: CollectionImportResult,
  selectedFeedIds?: string[],
): Promise<CollectionImageProcessResponse> {
  try {
    const processed = await chrome.runtime.sendMessage(
      {
        type: "collection-image-process",
        payload: {
          snapshot_id: imported.snapshot_id,
          board_id: observation.payload.board_id,
          retry_failed: true,
          ...(selectedFeedIds ? { selected_feed_ids: selectedFeedIds } : {}),
        },
      },
    ) as CollectionImageProcessResponse | null;
    return processed ?? { ok: false, message: "图片处理失败，请稍后重试", kind: "network" };
  } catch {
    return { ok: false, message: "图片处理失败，请稍后重试", kind: "network" };
  }
}

/** 触发已保存快照的原始文本抽取；只发送非敏感 snapshot identity。 */
export async function sendNoteExtraction(
  imported: CollectionImportResult,
): Promise<NoteExtractionResponse> {
  try {
    const response = await fetch(
      `http://127.0.0.1:5556/xhs/collections/snapshots/${encodeURIComponent(imported.snapshot_id)}/extractions/process`,
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ retry_failed: true }) },
    );
    if (!response.ok) return { ok: false, message: "原始抽取未启动" };
    const result = await response.json() as { job_status?: string };
    return { ok: true, message: "原始抽取已启动", job_status: result.job_status };
  } catch {
    return { ok: false, message: "原始抽取启动失败，请检查本地服务" };
  }
}
