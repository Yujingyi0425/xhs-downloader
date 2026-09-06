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
  bottomStableRounds: number;
  requiredBottomStableRounds: number;
}

/** 只根据测量状态给出滚动决策；EXPECTED_COUNT 不参与终止。 */
export function decideCollectionScroll(input: CollectionScrollInput): CollectionScrollDecision {
  if (input.round >= input.maxRounds) return "abort_max_rounds";
  if (input.elapsedMs >= input.maxRuntimeMs) return "abort_timeout";
  const atBottom = input.scrollTop + input.clientHeight >= input.scrollHeight - 1;
  if (input.loading) return "wait";
  if (atBottom && input.newUniqueCount === 0 && input.bottomStableRounds >= input.requiredBottomStableRounds) return "done";
  if (atBottom) return "wait";
  return "continue";
}

