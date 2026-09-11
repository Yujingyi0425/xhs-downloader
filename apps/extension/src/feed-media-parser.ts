import type { FeedMediaResult, JsonValue } from "@xhs-downloader/contracts";
import { readLiveInitialState } from "./browser-state-bridge";
import {
  inspectInitialStateVideo,
  parseInitialStateRecord,
  parseInitialStateScript,
  parseInitialStateValue,
  type InitialStateVideoInspection,
} from "./parser";
type MediaLocatorSource =
  | "NONE"
  | "STATIC_STATE"
  | "REALTIME_STATE"
  | "VIDEO_ELEMENT_CURRENT_SRC"
  | "VIDEO_ELEMENT_SRC"
  | "SOURCE_ELEMENT_SRC";
type UrlHostClass = "XHS_MEDIA_HOST" | "OTHER" | "UNKNOWN";
type UrlPathShapeClass = "VIDEO_FILE" | "VIDEO_STREAM" | "XHS_VIDEO_PATH" | "UNKNOWN";
type LocatorRejection =
  | "NO_VIDEO_OBJECT"
  | "VIDEO_OBJECT_SCHEMA_UNSUPPORTED"
  | "STREAM_OBJECT_MISSING"
  | "STREAM_VARIANTS_EMPTY"
  | "KNOWN_FIELDS_EMPTY"
  | "DOM_VIDEO_ELEMENT_MISSING"
  | "DOM_VIDEO_SRC_EMPTY"
  | "DOM_SOURCE_SRC_EMPTY"
  | "CANDIDATE_REJECTED"
  | "UNEXPECTED_MEDIA_SCHEMA"
  | "BLOB_ONLY_SOURCE"
  | "UNKNOWN";
interface UrlAssessment {
  accepted: boolean;
  hostClass: UrlHostClass;
  pathClass: UrlPathShapeClass;
  signedQuery: "YES" | "NO";
  rejection: LocatorRejection;
}
export type FeedMediaParserDiagnostics = Record<string, JsonValue>;
export class FeedMediaParserError extends Error {
  constructor(
    message: string,
    public readonly diagnostics: FeedMediaParserDiagnostics,
  ) {
    super(message);
    this.name = "FeedMediaParserError";
  }
}
/** 从页面失败对象中读取已经脱敏的媒体 parser 结构诊断。 */
export function feedMediaParserDiagnosticsFromError(
  error: unknown,
): FeedMediaParserDiagnostics | undefined {
  return error instanceof FeedMediaParserError ? error.diagnostics : undefined;
}
/** 从同一详情页提取短期视频定位器；地址只停留在当前运行时响应中。 */
export async function parseFeedMediaDocument(
  page: Document,
  feedId: string,
  sourceUrl: string,
): Promise<FeedMediaResult> {
  let stateInspection: InitialStateVideoInspection = emptyStateInspection();
  let stateRejection: LocatorRejection = "UNKNOWN";
  const scripts = [...page.scripts]
    .map((script) => script.textContent?.trim() ?? "")
    .filter((text) => text.startsWith("window.__INITIAL_STATE__"))
    .reverse();
  for (const script of scripts) {
    try {
      const state = parseInitialStateValue(script);
      stateInspection = inspectInitialStateVideo(state, sourceUrl);
      stateRejection = stateRejectionFromInspection(stateInspection);
      const work = parseInitialStateScript(script, sourceUrl);
      if (work.workId !== feedId) throw new Error("媒体结果与请求帖子不一致");
      const result = feedMediaResult(feedId, work.media);
      if (result.media.length) return result;
    } catch (error) {
      if (error instanceof Error && error.message.includes("不一致")) throw error;
      stateRejection = "UNEXPECTED_MEDIA_SCHEMA";
    }
  }
  try {
    const state = await readLiveInitialState(page);
    stateInspection = inspectInitialStateVideo(state, sourceUrl);
    stateRejection = stateRejectionFromInspection(stateInspection);
    const work = parseInitialStateRecord(state, sourceUrl);
    if (work.workId !== feedId) throw new Error("媒体结果与请求帖子不一致");
    const result = feedMediaResult(feedId, work.media);
    if (result.media.length) return result;
  } catch (error) {
    if (error instanceof Error && error.message.includes("不一致")) throw error;
    stateRejection = stateRejection === "UNKNOWN" ? "UNEXPECTED_MEDIA_SCHEMA" : stateRejection;
  }
  const domCandidate = findDomVideoCandidate(page);
  if (domCandidate.result) {
    return {
      feed_id: feedId,
      note_type: "video",
      media: [
        {
          index: 1,
          kind: "video",
          url: domCandidate.result.url,
          suffix: "mp4",
        },
      ],
    };
  }
  throw new FeedMediaParserError(
    "页面没有请求帖子的视频媒体",
    buildDiagnostics(page, stateInspection, stateRejection, domCandidate),
  );
}
function feedMediaResult(
  feedId: string,
  media: Array<{
    kind: "video" | "image" | "live";
    index: number;
    url: string;
    suffix: string;
    previewUrl?: string;
  }>,
): FeedMediaResult {
  return {
    feed_id: feedId,
    note_type: media.some((item) => item.kind === "video") ? "video" : "unknown",
    media,
  };
}
function emptyStateInspection(): InitialStateVideoInspection {
  return {
    video_object_present: false,
    video_keys_class: "EMPTY",
    video_stream_object_present: false,
    video_variant_count: 0,
  };
}
function stateRejectionFromInspection(
  inspection: InitialStateVideoInspection,
): LocatorRejection {
  if (!inspection.video_object_present) return "NO_VIDEO_OBJECT";
  if (!inspection.video_stream_object_present) {
    return inspection.video_keys_class === "KNOWN_FIELDS"
      ? "KNOWN_FIELDS_EMPTY"
      : inspection.video_keys_class === "OTHER"
        ? "VIDEO_OBJECT_SCHEMA_UNSUPPORTED"
        : "STREAM_OBJECT_MISSING";
  }
  return inspection.video_variant_count ? "UNKNOWN" : "STREAM_VARIANTS_EMPTY";
}

function findDomVideoCandidate(page: Document): {
  result?: { url: string; source: MediaLocatorSource };
  videoElementCount: number;
  sourceElementCount: number;
  videoSrcPresent: boolean;
  videoCurrentSrcPresent: boolean;
  sourceSrcPresent: boolean;
  hostClass: UrlHostClass;
  pathClass: UrlPathShapeClass;
  signedQuery: "YES" | "NO";
  rejection: LocatorRejection;
} {
  const videos = [...page.querySelectorAll("video")];
  const sources = [...page.querySelectorAll<HTMLSourceElement>("video source")];
  const candidates: Array<{ value: string; source: MediaLocatorSource }> = [];
  let videoSrcPresent = false;
  let videoCurrentSrcPresent = false;
  let sourceSrcPresent = false;
  for (const video of videos) {
    const currentSrc = video.currentSrc || "";
    const src = video.src || video.getAttribute("src") || "";
    if (currentSrc) {
      videoCurrentSrcPresent = true;
      candidates.push({ value: currentSrc, source: "VIDEO_ELEMENT_CURRENT_SRC" });
    }
    if (src) {
      videoSrcPresent = true;
      candidates.push({ value: src, source: "VIDEO_ELEMENT_SRC" });
    }
  }
  for (const source of sources) {
    const src = source.src || source.getAttribute("src") || "";
    if (src) {
      sourceSrcPresent = true;
      candidates.push({ value: src, source: "SOURCE_ELEMENT_SRC" });
    }
  }
  let latest = emptyLocatorAssessment("DOM_VIDEO_ELEMENT_MISSING");
  for (const candidate of candidates) {
    const assessment = assessVideoUrl(candidate.value);
    latest = { ...assessment, source: candidate.source };
    if (assessment.accepted) {
      return {
        result: { url: candidate.value, source: candidate.source },
        videoElementCount: videos.length,
        sourceElementCount: sources.length,
        videoSrcPresent,
        videoCurrentSrcPresent,
        sourceSrcPresent,
        hostClass: assessment.hostClass,
        pathClass: assessment.pathClass,
        signedQuery: assessment.signedQuery,
        rejection: "UNKNOWN",
      };
    }
  }
  const rejection = videos.length === 0
    ? "DOM_VIDEO_ELEMENT_MISSING"
    : candidates.length === 0
      ? sources.length
        ? "DOM_SOURCE_SRC_EMPTY"
        : "DOM_VIDEO_SRC_EMPTY"
      : latest.rejection;
  return {
    videoElementCount: videos.length,
    sourceElementCount: sources.length,
    videoSrcPresent,
    videoCurrentSrcPresent,
    sourceSrcPresent,
    hostClass: latest.hostClass,
    pathClass: latest.pathClass,
    signedQuery: latest.signedQuery,
    rejection,
  };
}

function buildDiagnostics(
  page: Document,
  state: InitialStateVideoInspection,
  stateRejection: LocatorRejection,
  dom: ReturnType<typeof findDomVideoCandidate>,
): FeedMediaParserDiagnostics {
  return {
    video_element_count: dom.videoElementCount,
    source_element_count: dom.sourceElementCount,
    video_src_present: dom.videoSrcPresent ? "YES" : "NO",
    video_current_src_present: dom.videoCurrentSrcPresent ? "YES" : "NO",
    source_src_present: dom.sourceSrcPresent ? "YES" : "NO",
    initial_state_video_object_present: state.video_object_present ? "YES" : "NO",
    initial_state_video_keys_class: state.video_keys_class,
    video_stream_object_present: state.video_stream_object_present ? "YES" : "NO",
    video_variant_count: state.video_variant_count,
    locator_candidate_source: dom.result?.source ?? "NONE",
    url_host_class: dom.hostClass,
    url_path_shape_class: dom.pathClass,
    signed_query_present: dom.signedQuery,
    locator_rejection_reason:
      dom.videoElementCount > 0 || dom.sourceElementCount > 0
        ? dom.rejection
        : stateRejection,
    page_has_initial_state_script: page.scripts.length > 0 ? "YES" : "NO",
  };
}

function emptyLocatorAssessment(rejection: LocatorRejection): UrlAssessment & {
  source: MediaLocatorSource;
} {
  return {
    accepted: false,
    hostClass: "UNKNOWN" as UrlHostClass,
    pathClass: "UNKNOWN" as UrlPathShapeClass,
    signedQuery: "NO" as const,
    rejection,
    source: "NONE" as MediaLocatorSource,
  };
}

function assessVideoUrl(value: string): UrlAssessment {
  if (value.startsWith("blob:")) return emptyLocatorAssessment("BLOB_ONLY_SOURCE");
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    return emptyLocatorAssessment("CANDIDATE_REJECTED");
  }
  const hostClass: UrlHostClass = isXhsVideoHost(parsed.hostname)
    ? "XHS_MEDIA_HOST"
    : "OTHER";
  const pathClass: UrlPathShapeClass = videoPathShape(parsed.pathname);
  const signedQuery: "YES" | "NO" = parsed.search ? "YES" : "NO";
  if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
    return { accepted: false, hostClass, pathClass, signedQuery, rejection: "CANDIDATE_REJECTED" as const };
  }
  if (hostClass !== "XHS_MEDIA_HOST" || !parsed.pathname || parsed.pathname === "/") {
    return { accepted: false, hostClass, pathClass, signedQuery, rejection: "CANDIDATE_REJECTED" as const };
  }
  return { accepted: true, hostClass, pathClass, signedQuery, rejection: "UNKNOWN" as const };
}

function isXhsVideoHost(hostname: string): boolean {
  return /^sns-video-[a-z0-9-]+\.xhscdn\.(com|net)$/i.test(hostname);
}

function videoPathShape(pathname: string): UrlPathShapeClass {
  if (/\.(mp4|webm)(?:$|\/)/i.test(pathname)) return "VIDEO_FILE";
  if (/\.(m3u8|mpd)(?:$|\/)/i.test(pathname)) return "VIDEO_STREAM";
  if (pathname.includes("/video") || pathname.includes("/stream")) return "XHS_VIDEO_PATH";
  return "UNKNOWN";
}
