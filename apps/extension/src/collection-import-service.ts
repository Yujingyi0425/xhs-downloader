import type { ExtensionCredential } from "./publication-types";
import type {
  CollectionImportPayload,
  CollectionImportResponse,
  CollectionImportResult,
} from "./collection-import-types";

export class CollectionImportUnauthorizedError extends Error {}

/** 向已认证的本机 Collection API 提交一次冻结 observation。 */
export async function importCollection(
  baseUrl: string,
  credential: ExtensionCredential,
  payload: CollectionImportPayload,
): Promise<CollectionImportResponse> {
  const url = `${normalizeBase(baseUrl)}/collections/board/${encodeURIComponent(payload.board_id)}/imports`;
  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      credentials: "omit",
      headers: {
        Authorization: `Bearer ${credential.token}`,
        "Content-Type": "application/json",
        "X-Extension-Id": credential.extensionId,
        ...(credential.installationId ? { "X-Extension-Installation": credential.installationId } : {}),
      },
      body: JSON.stringify({ request_id: payload.request_id, items: payload.items }),
    });
  } catch {
    return failure("保存失败，请检查本地服务后重试", "network");
  }
  if (response.status === 401) throw new CollectionImportUnauthorizedError();
  if (response.status === 403) return failure("本地服务拒绝了扩展请求", "forbidden");
  if (response.status === 409) return failure("保存请求发生幂等冲突，请重新扫描", "conflict");
  if (response.status === 422) return failure("收藏夹数据无效，请重新扫描", "invalid");
  if (response.status >= 500) return failure("本地服务暂时不可用，请稍后重试", "server");
  if (!response.ok) return failure(`保存失败（HTTP ${response.status}）`, "server");
  const body = await response.json().catch(() => null);
  const result = parseResult(body, payload);
  if (!result) return failure("本地服务返回了无效的保存结果", "server");
  return { ok: true, message: "收藏夹已保存", result };
}

function parseResult(value: unknown, payload: CollectionImportPayload): CollectionImportResult | null {
  if (!value || typeof value !== "object") return null;
  const result = value as Partial<CollectionImportResult>;
  if (
    result.source_type !== "board" || result.board_id !== payload.board_id ||
    result.request_id !== payload.request_id || result.item_count !== payload.items.length ||
    typeof result.snapshot_id !== "string" || typeof result.board_revision !== "number" ||
    typeof result.captured_at !== "string" || typeof result.fingerprint !== "string" ||
    typeof result.status !== "string" || !isDiff(result.diff)
  ) return null;
  return result as CollectionImportResult;
}

function isDiff(value: unknown): value is CollectionImportResult["diff"] {
  if (!value || typeof value !== "object") return false;
  const diff = value as Record<string, unknown>;
  return ["added", "removed", "retained"].every((key) =>
    Array.isArray(diff[key]) && diff[key].every((item) => typeof item === "string"),
  );
}

function failure(message: string, kind: CollectionImportResponse["kind"]): CollectionImportResponse {
  return { ok: false, message, kind };
}

function normalizeBase(value: string): string {
  return value.replace(/\/+$/, "");
}
