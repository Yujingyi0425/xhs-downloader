import { describe, expect, it } from "vitest";

import {
  BrowserRuntimeTelemetryBuilder,
  classifySendMessageFailure,
  withBrowserRuntimeTelemetry,
} from "./browser-runtime-telemetry";

describe("C7C 浏览器任务边界遥测", () => {
  it("记录详情页 readiness 到页面错误的最后边界", () => {
    const telemetry = new BrowserRuntimeTelemetryBuilder();
    telemetry.markTargetTabCreated();
    telemetry.markDetailWaitStarted();
    telemetry.markDetailWaitResult("PASS");
    telemetry.markSendMessageAttempted();
    telemetry.markSendMessageResolved();
    telemetry.markContentScriptResponseReceived();
    telemetry.absorbPageRuntimeTelemetry({
      content_script_message_received: true,
      page_task_started: true,
      parser_invocation_started: true,
    });
    telemetry.markPageResponse("PAGE_TASK_ERROR");
    telemetry.markExtensionResultBuilt();
    telemetry.markResultSubmitAttempted();

    expect(telemetry.snapshot()).toEqual({
      extension_manifest_version: "3.0.0",
      diagnostic_schema_version: "C7C-1",
      target_tab_created: true,
      detail_wait_started: true,
      detail_wait_result: "PASS",
      send_message_attempted: true,
      send_message_resolved: true,
      send_message_rejected: false,
      send_message_failure_class: "NOT_APPLICABLE",
      content_script_message_received: true,
      page_task_started: true,
      parser_invocation_started: true,
      content_script_response_received: true,
      page_response_class: "PAGE_TASK_ERROR",
      extension_result_built: true,
      result_submit_attempted: true,
      result_submit_resolved: false,
      result_submit_rejected: false,
      last_completed_runtime_boundary: "RESULT_SUBMIT_ATTEMPTED",
    });
  });

  it.each([
    ["Could not establish connection. Receiving end does not exist.", "NO_RECEIVER"],
    ["The message port closed before a response was received.", "PORT_CLOSED"],
    ["The target tab was closed.", "TAB_REMOVED"],
    ["Unexpected extension runtime error", "RUNTIME_ERROR"],
  ] as const)("把 sendMessage 错误 %s 映射为 %s", (message, expected) => {
    expect(classifySendMessageFailure(new Error(message))).toBe(expected);
  });

  it("只通过显式 envelope 携带 bounded telemetry", () => {
    const result = withBrowserRuntimeTelemetry(
      { failure_stage: "background", raw_error: "must not be persisted" },
      new BrowserRuntimeTelemetryBuilder().snapshot(),
    );
    expect(result.browser_runtime_telemetry).toMatchObject({
      extension_manifest_version: "3.0.0",
      diagnostic_schema_version: "C7C-1",
    });
    expect(result.raw_error).toBe("must not be persisted");
  });
});
