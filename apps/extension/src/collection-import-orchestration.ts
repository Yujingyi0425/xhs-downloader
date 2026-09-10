import type { CollectionCaptureResult } from "./collection-controller";
import {
  isSuccessfulCapture,
  type CollectionImportObservation,
  type CollectionImportPayload,
  type CollectionImportResponse,
  type CollectionImageProcessResponse,
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

/** 保存成功后立即启动图片生产，视频条目由服务端安全 deferred。 */
export async function sendCollectionImportAndProcess(
  observation: CollectionImportObservation,
): Promise<CollectionImportResponse> {
  const imported = await sendCollectionImport(observation.payload);
  if (!imported.ok || !imported.result) return imported;
  try {
    const processed = await chrome.runtime.sendMessage(
      {
        type: "collection-image-process",
        payload: {
          snapshot_id: imported.result.snapshot_id,
          board_id: observation.payload.board_id,
          retry_failed: true,
        },
      },
    ) as CollectionImageProcessResponse | null;
    if (!processed || !processed.ok || !processed.result) {
      return {
        ...imported,
        ok: false,
        message: processed?.message ?? "图片处理失败，请稍后重试",
        kind: processed?.kind ?? "network",
      };
    }
    return {
      ...imported,
      message: "收藏夹已保存，图片处理完成",
      processing: processed.result,
    };
  } catch {
    return { ...imported, ok: false, message: "图片处理失败，请稍后重试", kind: "network" };
  }
}
