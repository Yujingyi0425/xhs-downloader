import { describe, expect, it } from "vitest";

import {
  FeedDetailParserError,
  parseFeedDetailDocumentWithTelemetry,
} from "./feed-detail-parser";

const FEED_ID = "telemetry-feed";
const OPTIONS = {
  feedId: FEED_ID,
  xsecToken: "requested-token",
  commentLimit: 0,
  includeReplies: false,
  replyLimit: 0,
};

function pageWithState(state: Record<string, unknown>): Document {
  const page = document.implementation.createHTMLDocument();
  const script = page.createElement("script");
  script.textContent = `window.__INITIAL_STATE__=${JSON.stringify(state)};`;
  page.body.append(script);
  return page;
}

function detailState(
  wrapper: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    note: {
      noteDetailMap: {
        [FEED_ID]: {
          note: {
            noteId: FEED_ID,
            type: "normal",
            title: "合成详情",
            desc: "仅用于自动化测试",
            user: { userId: "telemetry-author", nickname: "合成作者" },
            imageList: [{ urlDefault: "https://example.invalid/image.png" }],
          },
          comments: { value: { list: [] } },
        },
      },
    },
    ...wrapper,
  };
}

function parse(state: Record<string, unknown> = detailState()) {
  return parseFeedDetailDocumentWithTelemetry(pageWithState(state), OPTIONS);
}

function failure(state: Record<string, unknown>) {
  try {
    parseFeedDetailDocumentWithTelemetry(document.implementation.createHTMLDocument(), OPTIONS, state);
    throw new Error("expected parser failure");
  } catch (error) {
    expect(error).toBeInstanceOf(FeedDetailParserError);
    return (error as FeedDetailParserError).telemetry;
  }
}

describe("详情解析器安全遥测", () => {
  it("在成功解析时报告固定边界和有界媒体事实", () => {
    const result = parse();

    expect(result.detail.feed_id).toBe(FEED_ID);
    expect(result.telemetry).toEqual({
      initial_state_anchor_present: true,
      initial_state_parse_result: "PARSED",
      note_root_present: true,
      note_detail_map_present: true,
      note_detail_map_count: 1,
      target_wrapper_found: true,
      target_wrapper_match_mode: "EXACT_KEY",
      target_note_present: true,
      target_note_id_match: true,
      author_object_present: true,
      author_id_present: true,
      image_list_present: true,
      image_list_length: 1,
      normalized_note_type: "IMAGE",
      last_completed_parser_boundary: "PARSE_COMPLETE",
      parser_failure_subtype: "NONE",
      safe_exception_class: "NONE",
    });
  });

  it.each([
    ["note root", {}, "NOTE_ROOT_MISSING", "INITIAL_STATE_PARSED"],
    [
      "detail map",
      { note: {} },
      "NOTE_DETAIL_MAP_MISSING",
      "NOTE_ROOT_FOUND",
    ],
    [
      "target wrapper",
      { note: { noteDetailMap: { other: {} } } },
      "TARGET_WRAPPER_NOT_FOUND",
      "NOTE_DETAIL_MAP_FOUND",
    ],
  ])("报告缺失 %s 时的最后成功边界", (_name, state, subtype, boundary) => {
    const telemetry = failure(state as Record<string, unknown>);

    expect(telemetry.parser_failure_subtype).toBe(subtype);
    expect(telemetry.last_completed_parser_boundary).toBe(boundary);
  });

  it("区分目标帖子缺失与身份不匹配", () => {
    const missingNote = failure({
      note: { noteDetailMap: { [FEED_ID]: { comments: { value: {} } } } },
    });
    expect(missingNote.target_wrapper_found).toBe(true);
    expect(missingNote.target_note_present).toBe(false);
    expect(missingNote.parser_failure_subtype).toBe("TARGET_NOTE_MISSING");

    const mismatched = failure({
      note: {
        noteDetailMap: {
          [FEED_ID]: {
            note: {
              noteId: "different-feed",
              user: { userId: "telemetry-author" },
            },
          },
        },
      },
    });
    expect(mismatched.target_note_present).toBe(true);
    expect(mismatched.target_note_id_match).toBe(false);
    expect(mismatched.parser_failure_subtype).toBe("TARGET_NOTE_ID_MISMATCH");
  });

  it("把作者校验失败和缺失图片列表作为不同情况处理", () => {
    const missingAuthor = failure({
      note: {
        noteDetailMap: {
          [FEED_ID]: { note: { noteId: FEED_ID } },
        },
      },
    });
    expect(missingAuthor.parser_failure_subtype).toBe("AUTHOR_MISSING");
    expect(missingAuthor.last_completed_parser_boundary).toBe("TARGET_IDENTITY_MATCHED");

    const noImages = parse(
      detailState({
        note: {
          noteDetailMap: {
            [FEED_ID]: {
              note: {
                noteId: FEED_ID,
                type: "normal",
                user: { userId: "telemetry-author" },
              },
            },
          },
        },
      }),
    );
    expect(noImages.telemetry.image_list_present).toBe(false);
    expect(noImages.telemetry.image_list_length).toBe(0);
    expect(noImages.telemetry.last_completed_parser_boundary).toBe("PARSE_COMPLETE");
  });

  it("只报告异常类型，不泄露异常文本", () => {
    const state: Record<string, unknown> = {};
    Object.defineProperty(state, "note", {
      get() {
        throw new TypeError("secret raw exception text");
      },
    });

    try {
      parseFeedDetailDocumentWithTelemetry(
        document.implementation.createHTMLDocument(),
        OPTIONS,
        state,
      );
      throw new Error("expected parser failure");
    } catch (error) {
      expect(error).toBeInstanceOf(FeedDetailParserError);
      const parserError = error as FeedDetailParserError;
      expect(parserError.message).toBe("详情页解析失败");
      expect(parserError.telemetry.parser_failure_subtype).toBe(
        "UNEXPECTED_PARSER_EXCEPTION",
      );
      expect(parserError.telemetry.safe_exception_class).toBe("TypeError");
      expect(JSON.stringify(parserError.telemetry)).not.toContain("secret raw");
    }
  });
});
