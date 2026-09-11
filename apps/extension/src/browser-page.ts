import {
  executeBrowserPageTask,
  isBrowserPageTaskRequest,
  type BrowserPageTaskResponse,
} from "./browser-page-runner";
import {
  isBrowserAccountChallengeRequest,
  proveBrowserAccount,
  type BrowserAccountProof,
} from "./account-proof";
import { UncertainBrowserActionError } from "./browser-action-errors";
import { buildPageCompatibilityDiagnostics } from "./browser-page-diagnostics";
import {
  classifyBrowserTaskFailure,
  classifyPageTaskError,
} from "./browser-task-errors";
import { requestBrowserInteraction } from "./browser-interaction-input";
import { CollectionCaptureController } from "./collection-controller";
import { createCollectionPanel } from "./collection-panel";
import { sendCollectionImages, sendCollectionImport, sendNoteExtraction } from "./collection-import-orchestration";
import { shouldOpenCollectionPanel } from "./collection-action-routing";
import { parserTelemetryFromError } from "./feed-detail-parser";
import { pageRuntimeTelemetryFromError, type PageRuntimeTelemetry } from "./browser-runtime-telemetry";

const collectionPanel = createCollectionPanel(
  document,
  (onProgress) =>
    new CollectionCaptureController({
      page: document,
      location,
      scrollOwner: document.scrollingElement as unknown as {
        scrollTop: number;
        scrollHeight: number;
        clientHeight: number;
        scrollTo(options: { top: number }): void;
      } | null,
      onProgress,
    }),
  (observation) => sendCollectionImport(observation.payload),
  sendCollectionImages,
  sendNoteExtraction,
);

chrome.runtime.onMessage.addListener(
  (
    message: { type?: string },
    _sender,
    sendResponse: (response: BrowserPageTaskResponse | BrowserAccountProof) => void,
  ) => {
    if (shouldOpenCollectionPanel(message.type, location.pathname)) {
      collectionPanel.toggle();
      return;
    }
    if (isBrowserAccountChallengeRequest(message)) {
      void proveBrowserAccount(document, message.challenge)
        .then(sendResponse)
        .catch(() => sendResponse({ status: "unverified" }));
      return true;
    }
    if (!isBrowserPageTaskRequest(message)) return;
    void executeBrowserPageTask(message.task, document, location.href, {
      activateInteraction: requestBrowserInteraction,
    })
      .then((response) =>
        sendResponse({
          ...response,
          page_runtime_telemetry: pageRuntimeTelemetry(
            response.page_runtime_telemetry,
          ),
        }),
      )
      .catch((error: unknown) => {
        const failureCode = classifyPageTaskError(message.task.kind, error);
        const parserTelemetry = parserTelemetryFromError(error);
        const pageTelemetry = pageRuntimeTelemetry(pageRuntimeTelemetryFromError(error));
        sendResponse({
          ok: false,
          message:
            message.task.kind === "get_feed_media"
              ? `媒体读取失败：${failureCode}`
              : error instanceof Error
                ? error.message
                : "页面数据解析失败",
          status: error instanceof UncertainBrowserActionError ? "needs_review" : "failed",
          result: {
            ...buildPageCompatibilityDiagnostics(document, location.href),
            failure_code: failureCode,
            failure_class: classifyBrowserTaskFailure(failureCode),
            failure_stage: "page_parser",
            ...(parserTelemetry ? { parser_telemetry: parserTelemetry } : {}),
          },
          page_runtime_telemetry: pageTelemetry,
        });
      });
    return true;
  },
);

function pageRuntimeTelemetry(
  observed?: PageRuntimeTelemetry,
): PageRuntimeTelemetry {
  return {
    content_script_message_received: true,
    page_task_started: true,
    parser_invocation_started: observed?.parser_invocation_started ?? false,
  };
}
