import type { BrowserTaskClaim, JsonValue } from "@xhs-downloader/contracts";

import type { BrowserPageTaskResponse } from "./browser-page-runner";
import {
  BrowserRuntimeTelemetryBuilder,
  withBrowserRuntimeTelemetry,
} from "./browser-runtime-telemetry";
import { heartbeatIntervalMilliseconds, startBrowserTaskHeartbeat } from "./browser-task-heartbeat";
import {
  BrowserTaskLeaseLostError,
  reportBrowserTaskResult,
  reportBrowserTaskRunning,
} from "./browser-task-service";
import {
  BrowserTaskExecutionError,
  classifyBrowserTaskFailure,
} from "./browser-task-errors";
import type { ExtensionCredential } from "./publication-types";

type CredentialOperation = <T>(
  operation: (credential: ExtensionCredential) => Promise<T>,
) => Promise<T>;

type ExecuteBrowserTask = (
  assertLeaseActive: () => void,
  telemetry: BrowserRuntimeTelemetryBuilder,
) => Promise<BrowserPageTaskResponse>;

/**
 * 在单次页面动作外维护任务租约并回传终态。
 *
 * 续租失败后不会重新调用 ``execute``；明确的陈旧租约也不会继续写入
 * 普通结果，交由服务端按读写副作用规则恢复到安全状态。
 */
export async function executeBrowserTaskClaim(
  baseUrl: string,
  claim: BrowserTaskClaim,
  execute: ExecuteBrowserTask,
  withCredential: CredentialOperation,
): Promise<void> {
  const taskId = claim.task.task_id;
  const leaseToken = claim.lease_token;
  const telemetry = new BrowserRuntimeTelemetryBuilder();
  await withLeaseRequestTimeout(claim, (signal) =>
    withCredential((credential) =>
      reportBrowserTaskRunning(baseUrl, credential, taskId, leaseToken, signal),
    ),
  );
  const heartbeat = startBrowserTaskHeartbeat(claim, (signal) =>
    withCredential((credential) =>
      reportBrowserTaskRunning(baseUrl, credential, taskId, leaseToken, signal),
    ),
  );
  let response: BrowserPageTaskResponse;
  try {
    response = await execute(heartbeat.assertActive, telemetry);
  } catch (error) {
    const leaseFailure = await heartbeat.stop();
    if (leaseFailure !== undefined) {
      await settleAfterLeaseFailure(baseUrl, claim, leaseFailure, withCredential);
      return;
    }
    const message = error instanceof Error ? error.message : "浏览器任务执行失败";
    telemetry.markExtensionResultBuilt();
    await submitFailure(
      baseUrl,
      claim,
      isWriteTask(claim) ? "needs_review" : "failed",
      message,
      failureResult(error, telemetry),
      telemetry,
      withCredential,
    );
    return;
  }
  const leaseFailure = await heartbeat.stop();
  if (leaseFailure !== undefined) {
    await settleAfterLeaseFailure(baseUrl, claim, leaseFailure, withCredential);
    return;
  }
  const status = response.status ?? (response.ok ? "succeeded" : "failed");
  if (status === "succeeded" && response.ok) {
    await reportResultWithTimeout(
      baseUrl,
      claim,
      status,
      response.message,
      response.result,
      withCredential,
    );
    return;
  }
  telemetry.absorbPageRuntimeTelemetry(response.page_runtime_telemetry);
  telemetry.markExtensionResultBuilt();
  const failureStatus = status === "needs_review" ? "needs_review" : "failed";
  await submitFailure(
    baseUrl,
    claim,
    failureStatus,
    response.message,
    withBrowserRuntimeTelemetry(response.result, telemetry.snapshot()),
    telemetry,
    withCredential,
  );
}

async function submitFailure(
  baseUrl: string,
  claim: BrowserTaskClaim,
  status: "failed" | "needs_review",
  message: string,
  result: Record<string, JsonValue>,
  telemetry: BrowserRuntimeTelemetryBuilder,
  withCredential: CredentialOperation,
): Promise<void> {
  telemetry.markResultSubmitAttempted();
  try {
    await reportResultWithTimeout(
      baseUrl,
      claim,
      status,
      message,
      withBrowserRuntimeTelemetry(result, telemetry.snapshot()),
      withCredential,
    );
    telemetry.markResultSubmitResolved();
  } catch (error) {
    telemetry.markResultSubmitRejected();
    throw error;
  }
}

function failureResult(
  error: unknown,
  telemetry: BrowserRuntimeTelemetryBuilder,
): Record<string, JsonValue> {
  return withBrowserRuntimeTelemetry(
    {
      failure_stage: "background",
      failure_code:
        error instanceof BrowserTaskExecutionError
          ? error.code
          : "PAGE_TASK_ERROR",
      failure_class: classifyBrowserTaskFailure(
        error instanceof BrowserTaskExecutionError ? error.code : "PAGE_TASK_ERROR",
      ),
    },
    telemetry.snapshot(),
  );
}

async function settleAfterLeaseFailure(
  baseUrl: string,
  claim: BrowserTaskClaim,
  failure: unknown,
  withCredential: CredentialOperation,
): Promise<void> {
  if (failure instanceof BrowserTaskLeaseLostError) return;
  try {
    await reportResultWithTimeout(
      baseUrl,
      claim,
      isWriteTask(claim) ? "needs_review" : "failed",
      "浏览器任务续租中断，结果未能安全确认",
      undefined,
      withCredential,
    );
  } catch (error) {
    if (!(error instanceof BrowserTaskLeaseLostError)) throw error;
  }
}

async function reportResultWithTimeout(
  baseUrl: string,
  claim: BrowserTaskClaim,
  status: "succeeded" | "failed" | "needs_review",
  message: string,
  result: BrowserPageTaskResponse["result"],
  withCredential: CredentialOperation,
): Promise<void> {
  await withLeaseRequestTimeout(claim, (signal) =>
    withCredential((credential) =>
      reportBrowserTaskResult(
        baseUrl,
        credential,
        claim.task.task_id,
        claim.lease_token,
        status,
        message,
        result,
        signal,
      ),
    ),
  );
}

async function withLeaseRequestTimeout<T>(
  claim: BrowserTaskClaim,
  operation: (signal: AbortSignal) => Promise<T>,
): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), heartbeatIntervalMilliseconds(claim));
  try {
    return await operation(controller.signal);
  } finally {
    clearTimeout(timeout);
  }
}

function isWriteTask(claim: BrowserTaskClaim): boolean {
  return ["set_like", "set_favorite", "post_comment", "reply_comment"].includes(claim.task.kind);
}
