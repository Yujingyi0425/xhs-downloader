import { detectCollectionPage } from "./collection-page-detection";
import { clearExtensionCredential, ensureExtensionCredential } from "./extension-credential";
import { registerBrowserExtension } from "./browser-task-service";
import { importCollection, CollectionImportUnauthorizedError } from "./collection-import-service";
import { loadSettings } from "./storage";
import type {
  CollectionImportMessage,
  CollectionImportResponse,
} from "./collection-import-types";

/** 在 Service Worker 中校验页面身份并完成一次有界的收藏导入。 */
export async function handleCollectionImportRequest(
  request: CollectionImportMessage,
  senderUrl?: string,
): Promise<CollectionImportResponse> {
  try {
    if (!senderMatchesBoard(senderUrl, request.payload.board_id)) {
      return { ok: false, message: "当前页面不是请求收藏夹", kind: "forbidden" };
    }
    const settings = await loadSettings();
    let credential = await ensureExtensionCredential(settings.serviceUrl, registerBrowserExtension);
    try {
      return await importCollection(settings.serviceUrl, credential, request.payload);
    } catch (error) {
      if (!(error instanceof CollectionImportUnauthorizedError)) {
        return { ok: false, message: "保存失败，请稍后重试", kind: "network" };
      }
      await clearExtensionCredential();
      credential = await ensureExtensionCredential(settings.serviceUrl, registerBrowserExtension);
      try {
        return await importCollection(settings.serviceUrl, credential, request.payload);
      } catch (retryError) {
        if (retryError instanceof CollectionImportUnauthorizedError) {
          return { ok: false, message: "扩展授权已失效，请稍后重试", kind: "unauthorized" };
        }
        return { ok: false, message: "保存失败，请稍后重试", kind: "network" };
      }
    }
  } catch {
    return { ok: false, message: "保存失败，请稍后重试", kind: "network" };
  }
}

export function senderMatchesBoard(senderUrl: string | undefined, boardId: string): boolean {
  if (!senderUrl) return false;
  try {
    const url = new URL(senderUrl);
    if (url.origin !== "https://www.xiaohongshu.com") return false;
    return detectCollectionPage(url.pathname).boardId === boardId;
  } catch {
    return false;
  }
}
