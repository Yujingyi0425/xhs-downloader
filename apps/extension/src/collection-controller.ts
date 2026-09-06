import { detectCollectionPage } from "./collection-page-detection";
import { parseVisibleCollectionFeeds } from "./collection-feed-parser";
import { createCollectionCaptureState, mergeVisibleCollectionFeeds } from "./collection-capture-state";
import {
  advanceCollectionScrollProgress,
  decideCollectionScroll,
  type CollectionScrollProgressState,
} from "./collection-scroll-policy";

export type CollectionScanStatus = "success" | "aborted" | "cancelled" | "failed";
export type CollectionStopReason = "bottom_stable" | "max_rounds" | "timeout" | "page_changed" | "cancelled" | "error";

export interface CollectionCaptureResult {
  status: CollectionScanStatus;
  boardId: string | null;
  uniqueCount: number;
  items: ReturnType<typeof createCollectionCaptureState>["items"];
  rounds: number;
  elapsedMs: number;
  stopReason: CollectionStopReason;
}

export interface CollectionScrollOwner {
  scrollTop: number;
  scrollHeight: number;
  clientHeight: number;
  scrollTo(options: { top: number }): void;
}

export interface CollectionClock {
  now(): number;
  setTimeout(callback: () => void, delayMs: number): number;
  clearTimeout(handle: number): void;
}

export interface CollectionScanOptions {
  page: Document;
  location: Pick<Location, "pathname">;
  scrollOwner: CollectionScrollOwner | null;
  clock?: CollectionClock;
  settle?: () => Promise<boolean>;
  maxRounds?: number;
  maxRuntimeMs?: number;
  onProgress?: (uniqueCount: number, round: number) => void;
}

const DEFAULT_MAX_ROUNDS = 200;
const DEFAULT_MAX_RUNTIME_MS = 120_000;
const SCROLL_VIEWPORT_RATIO = 0.7;
const REQUIRED_BOTTOM_STABLE_ROUNDS = 3;

/** 扫描当前收藏夹的唯一编排层；不持久化、不发送条目、不获取详情。 */
export class CollectionCaptureController {
  private readonly options: Required<Pick<CollectionScanOptions, "maxRounds" | "maxRuntimeMs">>;
  private activePromise: Promise<CollectionCaptureResult> | null = null;
  private cancelled = false;

  public constructor(private readonly input: CollectionScanOptions) {
    this.options = {
      maxRounds: input.maxRounds ?? DEFAULT_MAX_ROUNDS,
      maxRuntimeMs: input.maxRuntimeMs ?? DEFAULT_MAX_RUNTIME_MS,
    };
  }

  /** 同一 controller 只允许一条扫描循环。 */
  public start(): Promise<CollectionCaptureResult> {
    if (!this.activePromise) {
      this.cancelled = false;
      this.activePromise = this.run().finally(() => { this.activePromise = null; });
    }
    return this.activePromise;
  }

  /** 取消请求在下一次可观察边界生效，并由 finally 恢复滚动位置。 */
  public cancel(): void {
    this.cancelled = true;
  }

  private async run(): Promise<CollectionCaptureResult> {
    const startedAt = this.clock().now();
    const context = detectCollectionPage(this.input.location.pathname);
    const originalTop = this.input.scrollOwner?.scrollTop ?? 0;
    if (!context.isCollectionPage || !context.boardId || !this.input.scrollOwner) {
      return this.result("failed", context.boardId, createCollectionCaptureState(), 0, startedAt, "error");
    }
    let state = createCollectionCaptureState();
    let progress = emptyProgress();
    let rounds = 0;
    try {
      this.input.scrollOwner.scrollTo({ top: 0 });
      await this.settle();
      while (rounds < this.options.maxRounds) {
        if (this.cancelled) return this.result("cancelled", context.boardId, state, rounds, startedAt, "cancelled");
        if (this.clock().now() - startedAt >= this.options.maxRuntimeMs) return this.result("aborted", context.boardId, state, rounds, startedAt, "timeout");
        if (!this.isSameBoard(context.boardId)) return this.result("aborted", context.boardId, state, rounds, startedAt, "page_changed");
        rounds += 1;
        const before = state.items.size;
        const nextState = mergeVisibleCollectionFeeds(state, parseVisibleCollectionFeeds(this.input.page, context.boardId));
        const newUniqueCount = nextState.items.size - before;
        const owner = this.input.scrollOwner;
        const settled = await this.settle();
        progress = advanceCollectionScrollProgress(progress, {
          scrollTop: owner.scrollTop,
          scrollHeight: owner.scrollHeight,
          clientHeight: owner.clientHeight,
          uniqueCount: nextState.items.size,
          loading: !settled,
        });
        this.input.onProgress?.(nextState.items.size, rounds);
        const decision = decideCollectionScroll({
          scrollTop: owner.scrollTop,
          scrollHeight: owner.scrollHeight,
          clientHeight: owner.clientHeight,
          newUniqueCount,
          loading: !settled,
          round: rounds,
          elapsedMs: this.clock().now() - startedAt,
          maxRounds: this.options.maxRounds,
          maxRuntimeMs: this.options.maxRuntimeMs,
          requiredBottomStableRounds: REQUIRED_BOTTOM_STABLE_ROUNDS,
          progress,
        });
        state = nextState;
        if (decision === "done") return this.result("success", context.boardId, state, rounds, startedAt, "bottom_stable");
        if (decision === "abort_max_rounds") return this.result("aborted", context.boardId, state, rounds, startedAt, "max_rounds");
        if (decision === "abort_timeout") return this.result("aborted", context.boardId, state, rounds, startedAt, "timeout");
        if (decision === "continue") owner.scrollTo({ top: owner.scrollTop + Math.max(1, owner.clientHeight * SCROLL_VIEWPORT_RATIO) });
      }
      return this.result("aborted", context.boardId, state, rounds, startedAt, "max_rounds");
    } catch {
      return this.result("failed", context.boardId, state, rounds, startedAt, "error");
    } finally {
      this.input.scrollOwner.scrollTo({ top: originalTop });
    }
  }

  private isSameBoard(boardId: string): boolean {
    const current = detectCollectionPage(this.input.location.pathname);
    return current.isCollectionPage && current.boardId === boardId;
  }

  private clock(): CollectionClock {
    return this.input.clock ?? {
      now: () => Date.now(),
      setTimeout: (callback, delayMs) => window.setTimeout(callback, delayMs),
      clearTimeout: (handle) => window.clearTimeout(handle),
    };
  }

  private settle(): Promise<boolean> {
    return this.input.settle?.() ?? waitForCollectionDomQuiet(this.input.page, this.clock());
  }

  private result(status: CollectionScanStatus, boardId: string | null, state: ReturnType<typeof createCollectionCaptureState>, rounds: number, startedAt: number, stopReason: CollectionStopReason): CollectionCaptureResult {
    return { status, boardId, uniqueCount: state.items.size, items: state.items, rounds, elapsedMs: this.clock().now() - startedAt, stopReason };
  }
}

function emptyProgress(): CollectionScrollProgressState {
  return { previousScrollTop: null, previousScrollHeight: null, previousUniqueCount: null, bottomStableRounds: 0 };
}

/** 用 MutationObserver + quiet window + 最大等待时间完成 bounded settle。 */
export function waitForCollectionDomQuiet(page: Document, clock: CollectionClock, quietMs = 80, maxMs = 500): Promise<boolean> {
  return new Promise((resolve) => {
    let settled = false;
    let quietHandle: number | null = null;
    const observer = new MutationObserver(() => {
      if (quietHandle !== null) clock.clearTimeout(quietHandle);
      quietHandle = clock.setTimeout(() => finish(true), quietMs);
    });
    const timeoutHandle = clock.setTimeout(() => finish(false), maxMs);
    const finish = (value: boolean): void => {
      if (settled) return;
      settled = true;
      observer.disconnect();
      if (quietHandle !== null) clock.clearTimeout(quietHandle);
      clock.clearTimeout(timeoutHandle);
      resolve(value);
    };
    if (!page.body) finish(true);
    else {
      observer.observe(page.body, { childList: true, subtree: true, attributes: true });
      quietHandle = clock.setTimeout(() => finish(true), quietMs);
    }
  });
}

/** 仅允许安全、固定的错误原因进入 UI。 */
export function sanitizeCollectionReason(reason: CollectionStopReason): string {
  if (reason === "page_changed") return "页面已变化";
  if (reason === "timeout") return "达到时间上限";
  if (reason === "max_rounds") return "达到扫描轮数上限";
  if (reason === "cancelled") return "用户已取消";
  if (reason === "bottom_stable") return "到底且状态稳定";
  return "页面扫描失败";
}
