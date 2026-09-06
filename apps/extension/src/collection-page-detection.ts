/** 收藏夹页面与卡片路由的纯解析结果。 */
export interface CollectionPageContext {
  isCollectionPage: boolean;
  boardId: string | null;
}

export interface CollectionRoute {
  kind: "board" | "explore" | "profile" | "other";
  feedId: string | null;
  boardId: string | null;
  xsecToken: string;
  xsecSource: string;
}

/** 识别当前页面是否为收藏夹根页面。 */
export function detectCollectionPage(pathname: string): CollectionPageContext {
  const match = pathname.match(/^\/board\/([^/?#]+)\/?$/);
  return { isCollectionPage: match !== null, boardId: match?.[1] ?? null };
}

/** 解析 board、explore 与 profile 路由，不访问网络或浏览器状态。 */
export function parseCollectionRoute(href: string): CollectionRoute {
  try {
    const url = new URL(href, "https://www.xiaohongshu.com");
    if (url.origin !== "https://www.xiaohongshu.com") return otherRoute();
    const parts = url.pathname.split("/").filter(Boolean);
    const kind = parts[0];
    if (kind === "board" && parts.length === 3 && parts[1] && parts[2]) {
      return {
        kind: "board",
        boardId: parts[1],
        feedId: parts[2],
        xsecToken: url.searchParams.get("xsec_token")?.trim() ?? "",
        xsecSource: url.searchParams.get("xsec_source")?.trim() ?? "",
      };
    }
    if (kind === "explore" && parts.length === 2 && parts[1]) {
      return { kind: "explore", boardId: null, feedId: parts[1], xsecToken: "", xsecSource: "" };
    }
    if (kind === "user" && parts.length === 3 && parts[1] === "profile" && parts[2]) {
      return { kind: "profile", boardId: null, feedId: null, xsecToken: "", xsecSource: "" };
    }
  } catch {
    // Invalid hrefs are simply non-candidates.
  }
  return otherRoute();
}

function otherRoute(): CollectionRoute {
  return { kind: "other", boardId: null, feedId: null, xsecToken: "", xsecSource: "" };
}
