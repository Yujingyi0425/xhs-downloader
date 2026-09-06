export type CollectionScrollDecision = "continue" | "wait" | "done" | "abort_max_rounds" | "abort_timeout";

export interface CollectionScrollInput {
  scrollTop: number;
  scrollHeight: number;
  clientHeight: number;
  newUniqueCount: number;
  loading: boolean;
  round: number;
  elapsedMs: number;
  maxRounds: number;
  maxRuntimeMs: number;
  requiredBottomStableRounds: number;
  progress: CollectionScrollProgressState;
}

export interface CollectionScrollProgressState {
  previousScrollTop: number | null;
  previousScrollHeight: number | null;
  previousUniqueCount: number | null;
  bottomStableRounds: number;
}

export interface CollectionScrollMeasurement {
  scrollTop: number;
  scrollHeight: number;
  clientHeight: number;
  uniqueCount: number;
  loading: boolean;
}

/** 根据连续测量更新 bottom stability；任一稳定条件变化都会清零。 */
export function advanceCollectionScrollProgress(
  previous: CollectionScrollProgressState,
  current: CollectionScrollMeasurement,
): CollectionScrollProgressState {
  const atBottom = current.scrollTop + current.clientHeight >= current.scrollHeight - 1;
  const stable = previous.previousScrollTop === current.scrollTop
    && previous.previousScrollHeight === current.scrollHeight
    && previous.previousUniqueCount === current.uniqueCount
    && atBottom
    && !current.loading;
  return {
    previousScrollTop: current.scrollTop,
    previousScrollHeight: current.scrollHeight,
    previousUniqueCount: current.uniqueCount,
    bottomStableRounds: stable ? previous.bottomStableRounds + 1 : 0,
  };
}

/** 只根据测量状态给出滚动决策；EXPECTED_COUNT 不参与终止。 */
export function decideCollectionScroll(input: CollectionScrollInput): CollectionScrollDecision {
  if (input.round >= input.maxRounds) return "abort_max_rounds";
  if (input.elapsedMs >= input.maxRuntimeMs) return "abort_timeout";
  const atBottom = input.scrollTop + input.clientHeight >= input.scrollHeight - 1;
  if (input.loading) return "wait";
  if (atBottom && input.newUniqueCount === 0 && input.progress.bottomStableRounds >= input.requiredBottomStableRounds) return "done";
  if (atBottom) return "wait";
  return "continue";
}
