import { parseCollectionRoute } from "./collection-page-detection";

/** 一个严格有效的收藏夹 Feed 候选。token 只在内存结果中流转。 */
export interface CollectionFeedCandidate {
  feedId: string;
  xsecToken: string;
  xsecSource: string;
  title?: string;
  author?: string;
  coverUrl?: string;
}

/** 从当前可见 DOM 卡片提取严格有效的收藏 Feed。 */
export function parseVisibleCollectionFeeds(
  page: Document,
  boardId: string,
): CollectionFeedCandidate[] {
  const roots = new Set<Element>();
  for (const anchor of Array.from(page.querySelectorAll("a[href]"))) {
    const route = parseCollectionRoute(anchor.getAttribute("href") ?? "");
    if (route.kind !== "board" || route.boardId !== boardId) continue;
    const root = findCardRoot(anchor, boardId);
    if (root) roots.add(root);
  }

  const results = new Map<string, CollectionFeedCandidate>();
  for (const root of roots) {
    const candidate = parseCard(root, boardId);
    if (candidate && !results.has(candidate.feedId)) results.set(candidate.feedId, candidate);
  }
  return [...results.values()];
}

function findCardRoot(anchor: Element, boardId: string): Element | null {
  let current: Element | null = anchor;
  for (let depth = 0; current && depth < 9; depth += 1, current = current.parentElement) {
    const routes = Array.from(current.querySelectorAll("a[href]")).map((item) =>
      parseCollectionRoute(item.getAttribute("href") ?? ""),
    );
    const board = routes.find((route) => route.kind === "board" && route.boardId === boardId);
    if (board?.feedId && routes.some((route) => route.kind === "explore" && route.feedId === board.feedId)) {
      return current;
    }
  }
  return null;
}

function parseCard(root: Element, boardId: string): CollectionFeedCandidate | null {
  const routes = Array.from(root.querySelectorAll("a[href]")).map((item) =>
    parseCollectionRoute(item.getAttribute("href") ?? ""),
  );
  const board = routes.find(
    (route) => route.kind === "board" && route.boardId === boardId && route.feedId && route.xsecToken && route.xsecSource,
  );
  if (!board?.feedId) return null;
  const hasMatchingExplore = routes.some((route) => route.kind === "explore" && route.feedId === board.feedId);
  if (!hasMatchingExplore) return null;
  return {
    feedId: board.feedId,
    xsecToken: board.xsecToken,
    xsecSource: board.xsecSource,
  };
}
