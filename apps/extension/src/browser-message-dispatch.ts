import type { BrowserPageTaskRequest, BrowserPageTaskResponse } from "./browser-page-runner";
import { BrowserTaskExecutionError, classifyMessageDispatchError } from "./browser-task-errors";
import {
  BrowserRuntimeTelemetryBuilder,
  classifySendMessageFailure,
} from "./browser-runtime-telemetry";

const PAGE_READY_ATTEMPTS = 20;

export async function sendToTab(
  tabId: number,
  request: BrowserPageTaskRequest,
): Promise<BrowserPageTaskResponse> {
  return chrome.tabs.sendMessage<BrowserPageTaskRequest, BrowserPageTaskResponse>(tabId, request);
}

export async function sendWhenReady(
  tabId: number,
  request: BrowserPageTaskRequest,
  assertLeaseActive: () => void,
  telemetry: BrowserRuntimeTelemetryBuilder,
): Promise<BrowserPageTaskResponse> {
  let lastError: unknown;
  for (let attempt = 0; attempt < PAGE_READY_ATTEMPTS; attempt += 1) {
    try {
      assertLeaseActive();
      telemetry.markSendMessageAttempted();
      const response = await chrome.tabs.sendMessage<
        BrowserPageTaskRequest,
        BrowserPageTaskResponse
      >(tabId, request);
      assertLeaseActive();
      telemetry.markSendMessageResolved();
      telemetry.markContentScriptResponseReceived();
      if (!response || typeof response !== "object" || typeof response.ok !== "boolean") {
        telemetry.markPageResponse("INVALID_RESPONSE");
        throw new BrowserTaskExecutionError("MESSAGE_RESPONSE_EMPTY", "内容脚本返回了空响应");
      }
      telemetry.markPageResponse(response.ok ? "SUCCESS" : "PAGE_TASK_ERROR");
      return response;
    } catch (error) {
      if (error instanceof BrowserTaskExecutionError) throw error;
      telemetry.markSendMessageRejected(classifySendMessageFailure(error));
      lastError = error;
      await delay(250);
    }
  }
  const code = classifyMessageDispatchError(lastError);
  telemetry.markSendMessageRejected(classifySendMessageFailure(lastError));
  throw new BrowserTaskExecutionError(code, "内容脚本未能在有界时间内响应");
}

function delay(milliseconds: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}
