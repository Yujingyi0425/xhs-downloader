import { detectCollectionPage } from "./collection-page-detection";

/** action 消息只在收藏夹根页面打开收藏面板，避免覆盖帖子下载面板。 */
export function shouldOpenCollectionPanel(messageType: string | undefined, pathname: string): boolean {
  return messageType === "toggle-panel" && detectCollectionPage(pathname).isCollectionPage;
}
