import type { ExtensionCredential } from "./publication-types";
import { CollectionImportUnauthorizedError } from "./collection-import-service";
import type {
  CollectionImageProcessPayload,
  CollectionImageProcessResponse,
  CollectionImageProcessResult,
} from "./collection-import-types";

/** 调用本机图片生产端点，并只接受安全状态摘要。 */
export async function processCollectionImages(
  baseUrl: string,
  credential: ExtensionCredential,
  payload: CollectionImageProcessPayload,
): Promise<CollectionImageProcessResponse> {
  let response: Response;
  try {
    response = await fetch(
      `${normalizeBase(baseUrl)}/xhs/collections/snapshots/${encodeURIComponent(payload.snapshot_id)}/process-images`,
      {
        method: "POST",
        credentials: "omit",
        headers: {
          Authorization: `Bearer ${credential.token}`,
          "Content-Type": "application/json",
          "X-Extension-Id": credential.extensionId,
          ...(credential.installationId ? { "X-Extension-Installation": credential.installationId } : {}),
        },
        body: JSON.stringify({
          board_id: payload.board_id,
          retry_failed: payload.retry_failed ?? false,
        }),
      },
    );
  } catch {
    return failure("图片处理失败，请检查本地服务后重试", "network");
  }
  if (response.status === 401) throw new CollectionImportUnauthorizedError();
  if (response.status === 403) return failure("本地服务拒绝了扩展请求", "forbidden");
  if (response.status === 404) return failure("收藏快照不存在，请重新扫描", "invalid");
  if (response.status === 422) return failure("图片处理请求无效，请重新扫描", "invalid");
  if (response.status >= 500) return failure("图片处理服务暂时不可用，请稍后重试", "server");
  if (!response.ok) return failure(`图片处理失败（HTTP ${response.status}）`, "server");
  const result = parseResult(await response.json().catch(() => null), payload);
  return result
    ? { ok: true, message: "图片处理完成", result }
    : failure("本地服务返回了无效的图片处理结果", "server");
}

function parseResult(value: unknown, payload: CollectionImageProcessPayload): CollectionImageProcessResult | null {
  if (!value || typeof value !== "object") return null;
  const result = value as Partial<CollectionImageProcessResult>;
  if (result.snapshot_id !== payload.snapshot_id || typeof result.status !== "string" || !Array.isArray(result.items)) return null;
  if (!result.items.every(isItem)) return null;
  return result as CollectionImageProcessResult;
}

function isItem(value: unknown): boolean {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return typeof item.feed_id === "string" && typeof item.source_order === "number" &&
    typeof item.enrichment_status === "string" && typeof item.media_status === "string" &&
    typeof item.image_count === "number" && typeof item.success_count === "number" &&
    typeof item.failure_count === "number" && typeof item.video_deferred === "boolean";
}

function failure(message: string, kind: CollectionImageProcessResponse["kind"]): CollectionImageProcessResponse {
  return { ok: false, message, kind };
}

function normalizeBase(value: string): string {
  return value.replace(/\/+$/, "");
}
