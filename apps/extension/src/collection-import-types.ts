import type { CollectionCaptureResult } from "./collection-controller";

export interface CollectionImportItemPayload {
  feed_id: string;
  xsec_token: string;
  source_order: number;
}

export interface CollectionImportPayload {
  request_id: string;
  board_id: string;
  items: CollectionImportItemPayload[];
}

export interface CollectionImportDiff {
  added: string[];
  removed: string[];
  retained: string[];
}

export interface CollectionImportResult {
  snapshot_id: string;
  source_type: "board";
  board_id: string;
  board_revision: number;
  request_id: string;
  captured_at: string;
  item_count: number;
  fingerprint: string;
  status: string;
  diff: CollectionImportDiff;
}

export type CollectionImportFailureKind =
  | "unauthorized"
  | "forbidden"
  | "conflict"
  | "invalid"
  | "server"
  | "network";

export interface CollectionImportResponse {
  ok: boolean;
  message: string;
  kind?: CollectionImportFailureKind;
  result?: CollectionImportResult;
  processing?: CollectionImageProcessResult;
}

export interface CollectionImageProcessPayload {
  snapshot_id: string;
  board_id: string;
  retry_failed?: boolean;
  selected_feed_ids?: string[];
}

export interface CollectionImageItemResult {
  feed_id: string;
  source_order: number;
  enrichment_status: string;
  media_status: string;
  image_count: number;
  success_count: number;
  failure_count: number;
  video_deferred: boolean;
  error_code?: string | null;
}

export interface CollectionImageProcessResult {
  snapshot_id: string;
  status: string;
  items: CollectionImageItemResult[];
}

export interface CollectionImageProcessResponse {
  ok: boolean;
  message: string;
  kind?: CollectionImportFailureKind;
  result?: CollectionImageProcessResult;
}

export interface NoteExtractionResponse {
  ok: boolean;
  message: string;
  job_status?: string;
}

export interface CollectionImportObservation {
  requestId: string;
  payload: CollectionImportPayload;
}

export type CollectionImportMessage = {
  type: "collection-import";
  payload: CollectionImportPayload;
};

export type CollectionImageProcessMessage = {
  type: "collection-image-process";
  payload: CollectionImageProcessPayload;
};

export function isSuccessfulCapture(result: CollectionCaptureResult): boolean {
  return result.status === "success" && result.boardId !== null;
}
