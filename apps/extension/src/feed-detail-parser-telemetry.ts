export type InitialStateParseResult = "PARSED" | "MISSING" | "INVALID" | "UNEXPECTED_SHAPE";
export type TargetWrapperMatchMode = "EXACT_KEY" | "NOTE_ID_SCAN" | "NONE" | "NOT_REACHED";
export type NormalizedNoteType = "IMAGE" | "VIDEO" | "UNKNOWN" | "NOT_REACHED";
export type LastCompletedParserBoundary =
  | "NONE"
  | "INITIAL_STATE_PARSED"
  | "NOTE_ROOT_FOUND"
  | "NOTE_DETAIL_MAP_FOUND"
  | "TARGET_WRAPPER_FOUND"
  | "TARGET_NOTE_FOUND"
  | "TARGET_IDENTITY_MATCHED"
  | "AUTHOR_VALIDATED"
  | "MEDIA_FIELDS_VALIDATED"
  | "PARSE_COMPLETE";
export type ParserFailureSubtype =
  | "NONE"
  | "INITIAL_STATE_MISSING"
  | "INITIAL_STATE_PARSE_FAILED"
  | "NOTE_ROOT_MISSING"
  | "NOTE_DETAIL_MAP_MISSING"
  | "TARGET_WRAPPER_NOT_FOUND"
  | "TARGET_NOTE_MISSING"
  | "TARGET_NOTE_ID_MISMATCH"
  | "AUTHOR_MISSING"
  | "AUTHOR_ID_MISSING"
  | "UNEXPECTED_PARSER_EXCEPTION";
export type SafeExceptionClass = "TypeError" | "Error" | "SyntaxError" | "Unknown" | "NONE";

/** 只包含有界枚举、布尔值和数量的 parser 诊断。 */
export interface SafeParserTelemetry {
  [key: string]: string | number | boolean;
  initial_state_anchor_present: boolean;
  initial_state_parse_result: InitialStateParseResult;
  note_root_present: boolean;
  note_detail_map_present: boolean;
  note_detail_map_count: number;
  target_wrapper_found: boolean;
  target_wrapper_match_mode: TargetWrapperMatchMode;
  target_note_present: boolean;
  target_note_id_match: boolean;
  author_object_present: boolean;
  author_id_present: boolean;
  image_list_present: boolean;
  image_list_length: number;
  normalized_note_type: NormalizedNoteType;
  last_completed_parser_boundary: LastCompletedParserBoundary;
  parser_failure_subtype: ParserFailureSubtype;
  safe_exception_class: SafeExceptionClass;
}

/** parser 失败时携带安全遥测，原始异常文本仍只留在进程内。 */
export class FeedDetailParserError extends Error {
  constructor(
    message: string,
    public readonly telemetry: SafeParserTelemetry,
  ) {
    super(message);
    this.name = "FeedDetailParserError";
  }
}

export function parserTelemetryFromError(error: unknown): SafeParserTelemetry | undefined {
  return error instanceof FeedDetailParserError ? error.telemetry : undefined;
}

export class ParserTelemetryBuilder {
  initial_state_anchor_present: boolean;
  initial_state_parse_result: InitialStateParseResult = "MISSING";
  note_root_present = false;
  note_detail_map_present = false;
  note_detail_map_count = 0;
  target_wrapper_found = false;
  target_wrapper_match_mode: TargetWrapperMatchMode = "NOT_REACHED";
  target_note_present = false;
  target_note_id_match = false;
  author_object_present = false;
  author_id_present = false;
  image_list_present = false;
  image_list_length = 0;
  normalized_note_type: NormalizedNoteType = "NOT_REACHED";
  last_completed_parser_boundary: LastCompletedParserBoundary = "NONE";
  parser_failure_subtype: ParserFailureSubtype = "NONE";
  safe_exception_class: SafeExceptionClass = "NONE";

  constructor(initialStateAnchorPresent: boolean) {
    this.initial_state_anchor_present = initialStateAnchorPresent;
  }

  complete(boundary: LastCompletedParserBoundary): void {
    this.last_completed_parser_boundary = boundary;
  }

  fail(
    subtype: ParserFailureSubtype,
    message: string,
    exception: SafeExceptionClass,
  ): never {
    this.parser_failure_subtype = subtype;
    this.safe_exception_class = exception;
    throw new FeedDetailParserError(message, this.snapshot());
  }

  snapshot(): SafeParserTelemetry {
    return {
      initial_state_anchor_present: this.initial_state_anchor_present,
      initial_state_parse_result: this.initial_state_parse_result,
      note_root_present: this.note_root_present,
      note_detail_map_present: this.note_detail_map_present,
      note_detail_map_count: this.note_detail_map_count,
      target_wrapper_found: this.target_wrapper_found,
      target_wrapper_match_mode: this.target_wrapper_match_mode,
      target_note_present: this.target_note_present,
      target_note_id_match: this.target_note_id_match,
      author_object_present: this.author_object_present,
      author_id_present: this.author_id_present,
      image_list_present: this.image_list_present,
      image_list_length: this.image_list_length,
      normalized_note_type: this.normalized_note_type,
      last_completed_parser_boundary: this.last_completed_parser_boundary,
      parser_failure_subtype: this.parser_failure_subtype,
      safe_exception_class: this.safe_exception_class,
    };
  }
}

export function hasInitialStateAnchor(page: Document): boolean {
  return [...page.scripts].some((script) =>
    script.textContent?.trim().startsWith("window.__INITIAL_STATE__"),
  );
}

export function isRecordValue(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

export function boundedCount(value: number): number {
  return Math.min(Math.max(0, Math.trunc(value)), 1_000);
}

export function normalizedNoteType(value: unknown): NormalizedNoteType {
  const type = typeof value === "string" ? value.toLowerCase() : "";
  if (type === "video") return "VIDEO";
  if (type === "normal" || type === "image") return "IMAGE";
  return "UNKNOWN";
}

export function exceptionClass(error: unknown): SafeExceptionClass {
  if (error instanceof TypeError) return "TypeError";
  if (error instanceof SyntaxError) return "SyntaxError";
  if (error instanceof Error) return "Error";
  return "Unknown";
}
