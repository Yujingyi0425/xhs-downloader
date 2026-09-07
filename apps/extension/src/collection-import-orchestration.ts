import type { CollectionCaptureResult } from "./collection-controller";
import {
  isSuccessfulCapture,
  type CollectionImportObservation,
  type CollectionImportPayload,
  type CollectionImportResponse,
} from "./collection-import-types";

/** 把一次成功捕获冻结为可重试的内存 observation。 */
export function createCollectionImportObservation(
  result: CollectionCaptureResult,
): CollectionImportObservation {
  if (!isSuccessfulCapture(result)) throw new Error("只有完整扫描才能保存");
  const boardId = result.boardId;
  if (!boardId) throw new Error("扫描结果缺少收藏夹标识");
  const requestId = crypto.randomUUID();
  const items = Array.from(result.items.values()).map((item, sourceOrder) => ({
    feed_id: item.feedId,
    xsec_token: item.xsecToken,
    source_order: sourceOrder,
  }));
  if (items.length > 500) throw new Error("收藏夹条目超过单次保存上限");
  return {
    requestId,
    payload: { request_id: requestId, board_id: boardId, items },
  };
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
