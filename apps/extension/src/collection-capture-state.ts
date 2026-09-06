import type { CollectionFeedCandidate } from "./collection-feed-parser";

export interface CollectionCaptureState {
  items: Map<string, CollectionFeedCandidate>;
}

/** 创建一个不依赖 DOM 或持久化的累计状态。 */
export function createCollectionCaptureState(): CollectionCaptureState {
  return { items: new Map() };
}

/** 合并当前可见候选；同一 feed 只保留一条，最新非空 token/source 优先。 */
export function mergeVisibleCollectionFeeds(
  previous: CollectionCaptureState,
  visible: readonly CollectionFeedCandidate[],
): CollectionCaptureState {
  const items = new Map(previous.items);
  for (const candidate of visible) {
    const old = items.get(candidate.feedId);
    if (!old) {
      items.set(candidate.feedId, { ...candidate });
      continue;
    }
    items.set(candidate.feedId, {
      ...old,
      ...candidate,
      xsecToken: candidate.xsecToken || old.xsecToken,
      xsecSource: candidate.xsecSource || old.xsecSource,
      title: candidate.title || old.title,
      author: candidate.author || old.author,
      coverUrl: candidate.coverUrl || old.coverUrl,
    });
  }
  return { items };
}

