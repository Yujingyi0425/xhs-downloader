# TC4 Real Video Locator Runtime Repair R1

## Scope

This evidence records the read-only-to-repair transition after the confirmed real canary failure. R1 changes only the Extension `GET_FEED_MEDIA` runtime boundary. It does not rerun the real canary, change the downloader, alter the frozen TC4-MVP-B implementation, or start TC5/TC6.

Frozen baseline:

```text
11ec7b2832d4cd4c0abd68620b7fb09bf75bc8dd
```

## Production chain audited and repaired

```text
runBrowserTaskPoll
  -> executeBrowserTaskClaim
  -> executeInXhsTab
  -> executeInNewTab
  -> chrome.tabs.create(detail URL)
  -> waitForMediaDetailPage
  -> sendWhenReady(browser-page-task)
  -> browser-page.ts runtime listener
  -> executeBrowserPageTask(get_feed_media)
  -> parseFeedMediaDocument
  -> BrowserPageTaskResponse
  -> executeBrowserTaskClaim result report
```

| Boundary                    | Implementation                                                                                                                             | Contract / failure behavior                                                                                                                                                          |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Request dispatch            | `apps/extension/src/browser-task-runner.ts`: `runBrowserTaskPoll`, `executeInXhsTab`                                                       | Claims an Extension task and builds `BrowserPageTaskRequest` with message type `browser-page-task`.                                                                                  |
| Detail navigation           | `apps/extension/src/browser-task-runner.ts`: `taskTargetUrl`; `apps/extension/src/browser-media-task-runtime.ts`: `waitForMediaDetailPage` | Opens `/explore/<feed_id>` with the ephemeral task context, waits with a bounded poll for `status=complete`, and verifies the URL identity before messaging. Board URLs fail closed. |
| Content-script delivery     | `apps/extension/src/browser-task-runner.ts`: `sendWhenReady`                                                                               | Bounded 20-attempt readiness window. Receiving-end/message-port failures become `CONTENT_SCRIPT_NOT_READY`; malformed or empty responses become `MESSAGE_RESPONSE_EMPTY`.            |
| Content-script registration | `apps/extension/manifest.json`                                                                                                             | `content.js` matches `/explore/*` and `/discovery/item/*`; the separate `browser-page.js` listener is registered on all XHS pages.                                                   |
| Page execution              | `apps/extension/src/browser-page.ts`; `apps/extension/src/browser-page-runner.ts`: `executeBrowserPageTask`                                | `get_feed_media` calls the existing `parseFeedMediaDocument`; parser failures return safe `failure_code` and `failure_stage=page_parser`.                                            |
| Parser                      | `apps/extension/src/feed-media-parser.ts`; existing `apps/extension/src/parser.ts`                                                         | Existing `originVideoKey`, H264/H265, backup URL, master URL, and preview behavior is reused unchanged. Identity mismatch remains fail-closed.                                       |
| Result serialization        | `apps/extension/src/browser-task-runner.ts`: `mediaFailureResponse`; `apps/extension/src/browser-task-claim-execution.ts`                  | Media boundary failures are returned as non-null safe structured results, instead of escaping to the generic `result=null` path. No URL, token, Cookie, or credential is included.   |

The proven runtime defect was that the previous media path sent the message immediately after `tabs.create` without a target-page completion/identity boundary. A bounded `sendMessage` retry then surfaced only through the generic task catch, so the service observed `result=null`. The live canary's inner branch (readiness versus parser) remains intentionally unclaimed because R1 forbids another real canary; synthetic tests now distinguish both branches.

## Regression evidence

Synthetic tests added or finalized:

```text
apps/extension/src/browser-media-task-runner.test.ts
  GET_FEED_MEDIA 后台执行边界 > 从 feed_id 打开详情页，确认 identity 后再发送消息
  GET_FEED_MEDIA 后台执行边界 > content script 未就绪时返回明确 failure code
  GET_FEED_MEDIA 后台执行边界 > board context identity 不匹配时不发送 media 消息

apps/extension/src/browser-media-page-runner.test.ts
  GET_FEED_MEDIA 页面执行边界 > 在详情页读取视频 locator，并对空媒体 fail closed

apps/extension/src/browser-task-errors.test.ts
  浏览器任务失败边界 > 区分 parser 空结果、parser 异常和 identity mismatch
  浏览器任务失败边界 > 将 content script 消息失败保持为明确错误
  浏览器任务失败边界 > 对空消息响应和详情页 identity fail closed
```

Final gates:

```text
Extension typecheck: PASS
Extension lint: PASS
Extension tests: 62 files, 413 tests, PASS
Extension coverage: 89.94% statements, 85.41% branches, PASS
Extension build: PASS
Ruff check: PASS
Ruff format --check: PASS (338 files)
Python pytest: 699 passed
Python coverage: 90.54%, gate PASS
Architecture/file-size gate: PASS
```

Commit ancestry:

```text
R1_TEST_IMPLEMENTATION_COMMIT=f63dc99
R1_SOURCE_COMMIT=9df1b7a
R1_SOURCE_FINALIZATION_COMMIT=dc20f2e
R1_TEST_FINALIZATION_COMMIT=8372fb7
```

## Security and stage boundaries

```text
Cookie extraction: NOT USED
Browser profile scraping: NOT USED
Credential export: NOT USED
Hard-coded token/signed URL: NO
Real user data fixture: NO
Real video fixture/bytes: NO
Source of Truth changed: NO
TC4-MVP-B frozen baseline changed: NO
Real canary executed in R1: NO
TC5/TC6 work started: NO
```

R1 is a repair candidate only. Human Gate approval is required before any real canary. The frozen `TC4_MVP_B_FROZEN_AT` remains `11ec7b2832d4cd4c0abd68620b7fb09bf75bc8dd`.
