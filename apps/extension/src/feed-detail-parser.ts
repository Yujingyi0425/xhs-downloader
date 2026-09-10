import type { FeedComment, FeedDetailResult } from "@xhs-downloader/contracts";

import { parseFeedAuthor, parseFeedMetrics } from "./feed-parser";
import {
  dataBoolean,
  dataInteger,
  dataList,
  dataRecord,
  dataText,
  dataUrl,
  latestInitialState,
  unwrapState,
} from "./page-data";
import {
  boundedCount,
  exceptionClass,
  FeedDetailParserError,
  hasInitialStateAnchor,
  isRecordValue,
  normalizedNoteType,
  ParserTelemetryBuilder,
  type SafeParserTelemetry,
  type TargetWrapperMatchMode,
} from "./feed-detail-parser-telemetry";

export {
  FeedDetailParserError,
  parserTelemetryFromError,
} from "./feed-detail-parser-telemetry";
export type {
  InitialStateParseResult,
  LastCompletedParserBoundary,
  NormalizedNoteType,
  ParserFailureSubtype,
  SafeExceptionClass,
  SafeParserTelemetry,
  TargetWrapperMatchMode,
} from "./feed-detail-parser-telemetry";

interface DetailOptions {
  feedId: string;
  xsecToken: string;
  commentLimit: number;
  includeReplies: boolean;
  replyLimit: number;
}

export interface ParsedFeedDetail {
  detail: FeedDetailResult;
  telemetry: SafeParserTelemetry;
}

/** 从帖子详情页解析正文、媒体、互动状态和当前已加载评论。 */
export function parseFeedDetailDocument(
  page: Document,
  options: DetailOptions,
  currentState?: Record<string, unknown>,
): FeedDetailResult {
  return parseFeedDetailDocumentWithTelemetry(page, options, currentState).detail;
}

/** 解析详情并返回不含页面字段值的 parser 遥测。 */
export function parseFeedDetailDocumentWithTelemetry(
  page: Document,
  options: DetailOptions,
  currentState?: Record<string, unknown>,
): ParsedFeedDetail {
  const telemetry = new ParserTelemetryBuilder(hasInitialStateAnchor(page));
  try {
    let state: unknown;
    try {
      state = currentState ?? latestInitialState(page);
    } catch (error) {
      telemetry.initial_state_parse_result = telemetry.initial_state_anchor_present
        ? "INVALID"
        : "MISSING";
      telemetry.fail(
        telemetry.initial_state_anchor_present
          ? "INITIAL_STATE_PARSE_FAILED"
          : "INITIAL_STATE_MISSING",
        "当前页面没有可解析的小红书状态数据",
        exceptionClass(error),
      );
    }
    if (!isRecordValue(state)) {
      telemetry.initial_state_parse_result = "UNEXPECTED_SHAPE";
      telemetry.fail(
        "INITIAL_STATE_PARSE_FAILED",
        "当前页面没有可解析的小红书状态数据",
        "Error",
      );
    }
    const stateRecord = state as Record<string, unknown>;
    telemetry.initial_state_parse_result = "PARSED";
    telemetry.complete("INITIAL_STATE_PARSED");

    const noteRoot = stateRecord.note;
    const noteState = dataRecord(noteRoot);
    telemetry.note_root_present = isRecordValue(noteRoot);
    if (!telemetry.note_root_present) {
      telemetry.fail("NOTE_ROOT_MISSING", "详情页没有请求的帖子数据", "Error");
    }
    telemetry.complete("NOTE_ROOT_FOUND");

    const detailMapValue = noteState.noteDetailMap;
    const detailMap = dataRecord(detailMapValue);
    telemetry.note_detail_map_present = isRecordValue(detailMapValue);
    telemetry.note_detail_map_count = boundedCount(Object.keys(detailMap).length);
    if (!telemetry.note_detail_map_present || telemetry.note_detail_map_count === 0) {
      telemetry.fail("NOTE_DETAIL_MAP_MISSING", "详情页没有请求的帖子数据", "Error");
    }
    telemetry.complete("NOTE_DETAIL_MAP_FOUND");

    const located = findDetail(detailMap, options.feedId);
    if (!located) {
      telemetry.target_wrapper_match_mode = "NONE";
      telemetry.fail("TARGET_WRAPPER_NOT_FOUND", "详情页没有请求的帖子数据", "Error");
    }
    const locatedRecord = located as { wrapper: Record<string, unknown>; matchMode: TargetWrapperMatchMode };
    telemetry.target_wrapper_found = true;
    telemetry.target_wrapper_match_mode = locatedRecord.matchMode;
    telemetry.complete("TARGET_WRAPPER_FOUND");

    const noteValue = locatedRecord.wrapper.note;
    const note = dataRecord(noteValue);
    telemetry.target_note_present = isRecordValue(noteValue);
    if (!telemetry.target_note_present) {
      telemetry.fail("TARGET_NOTE_MISSING", "详情页数据与请求的帖子不一致", "Error");
    }
    telemetry.complete("TARGET_NOTE_FOUND");

    const noteId = dataText(note.noteId);
    telemetry.target_note_id_match = noteId === options.feedId;
    if (!telemetry.target_note_id_match) {
      telemetry.fail("TARGET_NOTE_ID_MISMATCH", "详情页数据与请求的帖子不一致", "Error");
    }
    telemetry.complete("TARGET_IDENTITY_MATCHED");

    const authorValue = note.user;
    const authorObject = dataRecord(authorValue);
    telemetry.author_object_present = isRecordValue(authorValue);
    if (!telemetry.author_object_present) {
      telemetry.fail("AUTHOR_MISSING", "详情页数据与请求的帖子不一致", "Error");
    }
    const authorId = dataText(authorObject.userId ?? authorObject.user_id);
    telemetry.author_id_present = Boolean(authorId);
    if (!telemetry.author_id_present) {
      telemetry.fail("AUTHOR_ID_MISSING", "详情页数据与请求的帖子不一致", "Error");
    }
    const author = parseFeedAuthor(authorValue);
    if (!author) {
      telemetry.fail("AUTHOR_MISSING", "详情页数据与请求的帖子不一致", "Error");
    }
    const parsedAuthor = author as NonNullable<typeof author>;
    telemetry.complete("AUTHOR_VALIDATED");

    const imageListValue: unknown = note.imageList;
    telemetry.image_list_present = Array.isArray(imageListValue);
    telemetry.image_list_length = Array.isArray(imageListValue)
      ? boundedCount(imageListValue.length)
      : 0;
    telemetry.normalized_note_type = normalizedNoteType(note.type);
    telemetry.complete("MEDIA_FIELDS_VALIDATED");

    const comments = dataRecord(unwrapState(locatedRecord.wrapper.comments));
    const detail: FeedDetailResult = {
      feed_id: options.feedId,
      xsec_token: dataText(note.xsecToken) || options.xsecToken,
      title: dataText(note.title).slice(0, 500),
      body: dataText(note.desc).slice(0, 20_000),
      note_type: noteType(note.type),
      author: parsedAuthor,
      metrics: parseFeedMetrics(note.interactInfo),
      image_urls: dataList(note.imageList)
        .map((item) => {
          const image = dataRecord(item);
          return dataUrl(image.urlDefault ?? image.urlPre ?? image.url);
        })
        .filter((url): url is string => url !== null)
        .slice(0, 100),
      published_at: dataInteger(note.time),
      ip_location: dataText(note.ipLocation).slice(0, 200),
      comments: dataList(unwrapState(comments.list))
        .slice(0, options.commentLimit)
        .map((item) => parseComment(item, options.includeReplies, options.replyLimit))
        .filter((item): item is FeedComment => item !== null),
      comments_has_more: dataBoolean(comments.hasMore),
      comments_cursor: dataText(comments.cursor).slice(0, 2048),
    };
    telemetry.parser_failure_subtype = "NONE";
    telemetry.safe_exception_class = "NONE";
    telemetry.complete("PARSE_COMPLETE");
    return { detail, telemetry: telemetry.snapshot() };
  } catch (error) {
    if (error instanceof FeedDetailParserError) throw error;
    return telemetry.fail(
      "UNEXPECTED_PARSER_EXCEPTION",
      "详情页解析失败",
      exceptionClass(error),
    );
  }
}

function findDetail(
  detailMap: Record<string, unknown>,
  feedId: string,
): { wrapper: Record<string, unknown>; matchMode: TargetWrapperMatchMode } | undefined {
  const direct = dataRecord(detailMap[feedId]);
  if (Object.keys(direct).length) return { wrapper: direct, matchMode: "EXACT_KEY" };
  const match = Object.values(detailMap)
    .map(dataRecord)
    .find((item) => dataText(dataRecord(item.note).noteId) === feedId);
  if (!match) return undefined;
  return { wrapper: match, matchMode: "NOTE_ID_SCAN" };
}

function parseComment(
  value: unknown,
  includeReplies: boolean,
  replyLimit: number,
): FeedComment | null {
  const comment = dataRecord(value);
  const author = parseFeedAuthor(comment.userInfo);
  const commentId = dataText(comment.id);
  if (!commentId || !author) return null;
  const replies = includeReplies
    ? dataList(unwrapState(comment.subComments))
        .slice(0, replyLimit)
        .map((item) => parseComment(item, false, 0))
        .filter((item): item is FeedComment => item !== null)
    : [];
  return {
    comment_id: commentId,
    content: dataText(comment.content).slice(0, 5000),
    author,
    liked: dataBoolean(comment.liked),
    like_count: dataText(comment.likeCount) || "0",
    created_at: dataInteger(comment.createTime),
    ip_location: dataText(comment.ipLocation).slice(0, 200),
    reply_count: dataText(comment.subCommentCount) || String(replies.length),
    replies,
  };
}

function noteType(value: unknown): FeedDetailResult["note_type"] {
  const type = dataText(value).toLowerCase();
  if (type === "video") return "video";
  if (type === "normal" || type === "image") return "image";
  return "unknown";
}
