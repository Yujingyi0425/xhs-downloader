import type { JsonValue } from "@xhs-downloader/contracts";

/** C7C 浏览器任务边界遥测；只允许固定枚举、布尔值和短版本号。 */

export const EXTENSION_MANIFEST_VERSION = "3.0.0" as const;
export const DIAGNOSTIC_SCHEMA_VERSION = "C7C-1" as const;

export type DetailWaitResult = "PASS" | "FAIL" | "NOT_APPLICABLE" | "NOT_REACHED";
export type PageResponseClass =
  | "SUCCESS"
  | "PAGE_TASK_ERROR"
  | "INVALID_RESPONSE"
  | "NO_RESPONSE"
  | "NOT_REACHED";
export type SendMessageFailureClass =
  | "NO_RECEIVER"
  | "PORT_CLOSED"
  | "RUNTIME_ERROR"
  | "TAB_REMOVED"
  | "UNKNOWN"
  | "NOT_APPLICABLE";
export type LastCompletedRuntimeBoundary =
  | "TASK_CLAIMED"
  | "TARGET_TAB_CREATED"
  | "DETAIL_WAIT_STARTED"
  | "DETAIL_READY"
  | "SEND_MESSAGE_ATTEMPTED"
  | "SEND_MESSAGE_RESOLVED"
  | "CONTENT_SCRIPT_RESPONSE_RECEIVED"
  | "PAGE_RESPONSE_PARSED"
  | "EXTENSION_RESULT_BUILT"
  | "RESULT_SUBMIT_ATTEMPTED"
  | "RESULT_SUBMITTED";

export interface PageRuntimeTelemetry {
  content_script_message_received: boolean;
  page_task_started: boolean;
  parser_invocation_started: boolean;
}

export interface BrowserRuntimeTelemetry extends PageRuntimeTelemetry {
  [key: string]: JsonValue;
  extension_manifest_version: typeof EXTENSION_MANIFEST_VERSION;
  diagnostic_schema_version: typeof DIAGNOSTIC_SCHEMA_VERSION;
  target_tab_created: boolean;
  detail_wait_started: boolean;
  detail_wait_result: DetailWaitResult;
  send_message_attempted: boolean;
  send_message_resolved: boolean;
  send_message_rejected: boolean;
  send_message_failure_class: SendMessageFailureClass;
  content_script_response_received: boolean;
  page_response_class: PageResponseClass;
  extension_result_built: boolean;
  result_submit_attempted: boolean;
  result_submit_resolved: boolean;
  result_submit_rejected: boolean;
  last_completed_runtime_boundary: LastCompletedRuntimeBoundary;
}

type TelemetryCarrier = {
  page_runtime_telemetry?: PageRuntimeTelemetry;
  browser_runtime_telemetry?: BrowserRuntimeTelemetry;
};

export class BrowserRuntimeTelemetryBuilder {
  private readonly value: BrowserRuntimeTelemetry = {
    extension_manifest_version: EXTENSION_MANIFEST_VERSION,
    diagnostic_schema_version: DIAGNOSTIC_SCHEMA_VERSION,
    target_tab_created: false,
    detail_wait_started: false,
    detail_wait_result: "NOT_REACHED",
    send_message_attempted: false,
    send_message_resolved: false,
    send_message_rejected: false,
    send_message_failure_class: "NOT_APPLICABLE",
    content_script_message_received: false,
    page_task_started: false,
    parser_invocation_started: false,
    content_script_response_received: false,
    page_response_class: "NOT_REACHED",
    extension_result_built: false,
    result_submit_attempted: false,
    result_submit_resolved: false,
    result_submit_rejected: false,
    last_completed_runtime_boundary: "TASK_CLAIMED",
  };

  markTargetTabCreated(): void {
    this.value.target_tab_created = true;
    this.complete("TARGET_TAB_CREATED");
  }

  markDetailWaitStarted(): void {
    this.value.detail_wait_started = true;
    this.complete("DETAIL_WAIT_STARTED");
  }

  markDetailWaitResult(result: Exclude<DetailWaitResult, "NOT_REACHED">): void {
    this.value.detail_wait_result = result;
    if (result === "PASS") this.complete("DETAIL_READY");
  }

  markSendMessageAttempted(): void {
    this.value.send_message_attempted = true;
    this.complete("SEND_MESSAGE_ATTEMPTED");
  }

  markSendMessageResolved(): void {
    this.value.send_message_resolved = true;
    this.complete("SEND_MESSAGE_RESOLVED");
  }

  markSendMessageRejected(failureClass: SendMessageFailureClass): void {
    this.value.send_message_rejected = true;
    this.value.send_message_failure_class = failureClass;
  }

  markContentScriptResponseReceived(): void {
    this.value.content_script_response_received = true;
    this.complete("CONTENT_SCRIPT_RESPONSE_RECEIVED");
  }

  markPageResponse(responseClass: Exclude<PageResponseClass, "NOT_REACHED">): void {
    this.value.page_response_class = responseClass;
    this.complete("PAGE_RESPONSE_PARSED");
  }

  absorbPageRuntimeTelemetry(value: PageRuntimeTelemetry | undefined): void {
    if (!value) return;
    this.value.content_script_message_received ||= value.content_script_message_received;
    this.value.page_task_started ||= value.page_task_started;
    this.value.parser_invocation_started ||= value.parser_invocation_started;
  }

  markExtensionResultBuilt(): void {
    this.value.extension_result_built = true;
    this.complete("EXTENSION_RESULT_BUILT");
  }

  markResultSubmitAttempted(): void {
    this.value.result_submit_attempted = true;
    this.complete("RESULT_SUBMIT_ATTEMPTED");
  }

  markResultSubmitResolved(): void {
    this.value.result_submit_resolved = true;
    this.complete("RESULT_SUBMITTED");
  }

  markResultSubmitRejected(): void {
    this.value.result_submit_rejected = true;
  }

  snapshot(): BrowserRuntimeTelemetry {
    return { ...this.value };
  }

  complete(boundary: LastCompletedRuntimeBoundary): void {
    this.value.last_completed_runtime_boundary = boundary;
  }
}

export function pageRuntimeTelemetryFromError(error: unknown): PageRuntimeTelemetry | undefined {
  if (!error || typeof error !== "object") return undefined;
  const value = (error as { page_runtime_telemetry?: unknown }).page_runtime_telemetry;
  return isPageRuntimeTelemetry(value) ? value : undefined;
}

export function attachPageRuntimeTelemetry(
  error: unknown,
  telemetry: PageRuntimeTelemetry,
): void {
  if (!error || typeof error !== "object") return;
  (error as { page_runtime_telemetry?: PageRuntimeTelemetry }).page_runtime_telemetry = telemetry;
}

export function withBrowserRuntimeTelemetry(
  result: Record<string, JsonValue> | undefined,
  telemetry: BrowserRuntimeTelemetry,
): Record<string, JsonValue> {
  return { ...(result ?? {}), browser_runtime_telemetry: telemetry };
}

export function browserRuntimeTelemetryFromCarrier(
  value: TelemetryCarrier | undefined,
): BrowserRuntimeTelemetry | undefined {
  return value?.browser_runtime_telemetry;
}

export function classifySendMessageFailure(error: unknown): SendMessageFailureClass {
  const message = error instanceof Error ? error.message.toLowerCase() : String(error).toLowerCase();
  if (message.includes("tab") && (message.includes("closed") || message.includes("removed"))) {
    return "TAB_REMOVED";
  }
  if (
    message.includes("could not establish connection") ||
    message.includes("receiving end does not exist") ||
    message.includes("no receiving end")
  ) {
    return "NO_RECEIVER";
  }
  if (message.includes("message port closed")) return "PORT_CLOSED";
  if (message) return "RUNTIME_ERROR";
  return "UNKNOWN";
}

function isPageRuntimeTelemetry(value: unknown): value is PageRuntimeTelemetry {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    typeof item.content_script_message_received === "boolean" &&
    typeof item.page_task_started === "boolean" &&
    typeof item.parser_invocation_started === "boolean"
  );
}
