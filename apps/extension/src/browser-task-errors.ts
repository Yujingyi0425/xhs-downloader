import type { BrowserTaskKind } from "@xhs-downloader/contracts";

/** 浏览器任务跨扩展消息边界的可诊断失败类型。 */
export type BrowserTaskFailureCode =
  | "DETAIL_NAVIGATION_FAILED"
  | "TARGET_TAB_NOT_FOUND"
  | "TARGET_TAB_IDENTITY_MISMATCH"
  | "CONTENT_SCRIPT_NOT_READY"
  | "MESSAGE_DISPATCH_FAILED"
  | "MESSAGE_RESPONSE_EMPTY"
  | "MEDIA_PARSER_EMPTY"
  | "MEDIA_PARSER_ERROR"
  | "MEDIA_IDENTITY_MISMATCH"
  | "PAGE_TASK_ERROR";

export type BrowserTaskFailureClass =
  | "DETAIL_NAVIGATION"
  | "CONTENT_SCRIPT"
  | "PAGE_TASK"
  | "PARSER"
  | "UNKNOWN";

/** 带有安全失败类型的扩展运行时错误，不携带页面 URL 或凭据。 */
export class BrowserTaskExecutionError extends Error {
  constructor(
    public readonly code: BrowserTaskFailureCode,
    message: string,
  ) {
    super(message);
    this.name = "BrowserTaskExecutionError";
  }
}

/** 将失败码归并为不含页面原文的有界失败类别。 */
export function classifyBrowserTaskFailure(
  code: BrowserTaskFailureCode,
): BrowserTaskFailureClass {
  if (
    code === "DETAIL_NAVIGATION_FAILED" ||
    code === "TARGET_TAB_NOT_FOUND" ||
    code === "TARGET_TAB_IDENTITY_MISMATCH"
  ) {
    return "DETAIL_NAVIGATION";
  }
  if (
    code === "CONTENT_SCRIPT_NOT_READY" ||
    code === "MESSAGE_DISPATCH_FAILED" ||
    code === "MESSAGE_RESPONSE_EMPTY"
  ) {
    return "CONTENT_SCRIPT";
  }
  if (
    code === "MEDIA_PARSER_EMPTY" ||
    code === "MEDIA_PARSER_ERROR" ||
    code === "MEDIA_IDENTITY_MISMATCH"
  ) {
    return "PARSER";
  }
  if (code === "PAGE_TASK_ERROR") return "PAGE_TASK";
  return "UNKNOWN";
}

/** 将浏览器消息通道异常归类为可重试且不泄露底层细节的错误。 */
export function classifyMessageDispatchError(
  error: unknown,
): "CONTENT_SCRIPT_NOT_READY" | "MESSAGE_DISPATCH_FAILED" {
  const message =
    error instanceof Error ? error.message.toLowerCase() : String(error).toLowerCase();
  if (
    message.includes("could not establish connection") ||
    message.includes("receiving end does not exist") ||
    message.includes("no receiving end") ||
    message.includes("message port closed")
  ) {
    return "CONTENT_SCRIPT_NOT_READY";
  }
  return "MESSAGE_DISPATCH_FAILED";
}

/** 将页面任务异常归类为 parser 空结果、parser 异常或 identity mismatch。 */
export function classifyPageTaskError(
  taskKind: BrowserTaskKind,
  error: unknown,
): "MEDIA_PARSER_EMPTY" | "MEDIA_PARSER_ERROR" | "MEDIA_IDENTITY_MISMATCH" | "PAGE_TASK_ERROR" {
  const message = error instanceof Error ? error.message : String(error);
  if (taskKind !== "get_feed_media") return "PAGE_TASK_ERROR";
  if (message.includes("不一致")) return "MEDIA_IDENTITY_MISMATCH";
  if (message.includes("没有请求帖子的视频媒体")) return "MEDIA_PARSER_EMPTY";
  return "MEDIA_PARSER_ERROR";
}

/** 验证目标标签页仍是预期的小红书详情页，拒绝 board 或其他帖子上下文。 */
export function isSupportedDetailPageForFeed(pageUrl: string, feedId: string): boolean {
  try {
    const url = new URL(pageUrl);
    if (url.origin !== "https://www.xiaohongshu.com") return false;
    const segments = url.pathname.split("/").filter(Boolean).map(decodeURIComponent);
    if (segments.length === 2 && segments[0] === "explore") {
      return segments[1] === feedId;
    }
    return (
      segments.length === 3 &&
      segments[0] === "discovery" &&
      segments[1] === "item" &&
      segments[2] === feedId
    );
  } catch {
    return false;
  }
}
