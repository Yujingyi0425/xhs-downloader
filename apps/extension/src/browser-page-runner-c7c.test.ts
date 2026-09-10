import { describe, expect, it } from "vitest";

import { executeBrowserPageTask } from "./browser-page-runner";
import { pageRuntimeTelemetryFromError } from "./browser-runtime-telemetry";
import { statePage, pageTask as task } from "./browser-page-test-helpers";

describe("C7C 页面任务边界标记", () => {
  it("详情任务成功时返回 page-task invocation marker", async () => {
    const page = statePage({
      note: {
        noteDetailMap: {
          "synthetic-feed": {
            note: {
              noteId: "synthetic-feed",
              type: "normal",
              user: { userId: "synthetic-author" },
            },
            comments: { value: { list: [] } },
          },
        },
      },
    });
    const payload = {
      feed_id: "synthetic-feed",
      xsec_token: "synthetic-token",
      comment_limit: 10,
      include_replies: false,
      reply_limit: 5,
    };

    const response = await executeBrowserPageTask(
      task("get_feed_detail", payload),
      page,
      "https://www.xiaohongshu.com/explore/synthetic-feed",
    );

    expect(response.result).toMatchObject({ feed_id: "synthetic-feed" });
    expect(response.page_runtime_telemetry).toEqual({
      content_script_message_received: false,
      page_task_started: true,
      parser_invocation_started: true,
    });
    await expect(
      executeBrowserPageTask(
        task("get_feed_detail", { ...payload, comment_limit: 1.5 }),
        page,
        "https://www.xiaohongshu.com/explore/synthetic-feed",
      ),
    ).rejects.toThrow("comment_limit 无效");
  });

  it("parser 异常保留 page-task invocation marker", async () => {
    const error = await executeBrowserPageTask(
      task("get_feed_detail", {
        feed_id: "synthetic-feed",
        xsec_token: "synthetic-token",
        comment_limit: 0,
        include_replies: false,
        reply_limit: 0,
      }),
      statePage({ note: {} }),
      "https://www.xiaohongshu.com/explore/synthetic-feed",
    ).catch((value: unknown) => value);

    expect(pageRuntimeTelemetryFromError(error)).toEqual({
      content_script_message_received: false,
      page_task_started: true,
      parser_invocation_started: true,
    });
  });
});
