import { detectCollectionPage } from "./collection-page-detection";
import { clearExtensionCredential, ensureExtensionCredential } from "./extension-credential";
import { registerBrowserExtension } from "./browser-task-service";
import { processCollectionImages } from "./collection-image-service";
import { loadSettings } from "./storage";
import type {
  CollectionImageProcessMessage,
  CollectionImageProcessResponse,
} from "./collection-import-types";
import { CollectionImportUnauthorizedError } from "./collection-import-service";

/** 在 Service Worker 中校验页面身份并完成一次图片生产。 */
export async function handleCollectionImageProcessRequest(
  request: CollectionImageProcessMessage,
  senderUrl?: string,
): Promise<CollectionImageProcessResponse> {
  try {
    if (!senderMatchesBoard(senderUrl, request.payload.board_id)) {
      return { ok: false, message: "当前页面不是请求收藏夹", kind: "forbidden" };
    }
    const settings = await loadSettings();
    let credential = await ensureExtensionCredential(settings.serviceUrl, registerBrowserExtension);
    try {
      return await processCollectionImages(settings.serviceUrl, credential, request.payload);
    } catch (error) {
      if (!(error instanceof CollectionImportUnauthorizedError)) {
        return { ok: false, message: "图片处理失败，请稍后重试", kind: "network" };
      }
      await clearExtensionCredential();
      credential = await ensureExtensionCredential(settings.serviceUrl, registerBrowserExtension);
      try {
        return await processCollectionImages(settings.serviceUrl, credential, request.payload);
      } catch (retryError) {
        return retryError instanceof CollectionImportUnauthorizedError
          ? { ok: false, message: "扩展授权已失效，请稍后重试", kind: "unauthorized" }
          : { ok: false, message: "图片处理失败，请稍后重试", kind: "network" };
      }
    }
  } catch {
    return { ok: false, message: "图片处理失败，请稍后重试", kind: "network" };
  }
}

function senderMatchesBoard(senderUrl: string | undefined, boardId: string): boolean {
  if (!senderUrl) return false;
  try {
    const url = new URL(senderUrl);
    return url.origin === "https://www.xiaohongshu.com" &&
      detectCollectionPage(url.pathname).boardId === boardId;
  } catch {
    return false;
  }
}
