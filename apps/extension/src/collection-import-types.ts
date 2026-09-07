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
}

export interface CollectionImportObservation {
  requestId: string;
  payload: CollectionImportPayload;
}

export type CollectionImportMessage = {
  type: "collection-import";
  payload: CollectionImportPayload;
};

export function isSuccessfulCapture(result: CollectionCaptureResult): boolean {
  return result.status === "success" && result.boardId !== null;
}
