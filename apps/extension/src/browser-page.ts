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
import { classifyPageTaskError } from "./browser-task-errors";
import { requestBrowserInteraction } from "./browser-interaction-input";
import { CollectionCaptureController } from "./collection-controller";
import { createCollectionPanel } from "./collection-panel";
import { sendCollectionImport } from "./collection-import-orchestration";
import { shouldOpenCollectionPanel } from "./collection-action-routing";

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
      .then(sendResponse)
      .catch((error: unknown) => {
        const failureCode = classifyPageTaskError(message.task.kind, error);
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
            failure_stage: "page_parser",
          },
        });
      });
    return true;
  },
);
