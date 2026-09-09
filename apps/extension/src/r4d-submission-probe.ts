import type { JsonValue } from "@xhs-downloader/contracts";

type R4aField =
  | "target_tab_exists"
  | "last_tab_status"
  | "last_route_class"
  | "url_host_is_xhs"
  | "expected_route_matched"
  | "elapsed_ms"
  | "tab_removed";

/** 为失败结果添加仅用于 R4D 的字段存在性探针，不复制任何字段值。 */
export function buildR4dSubmissionProbe(
  result?: Record<string, JsonValue>,
): Record<string, JsonValue> {
  const source = result ?? {};
  return {
    ...source,
    r4d_submission_probe: true,
    r4d_has_target_tab_exists: hasField(source, "target_tab_exists"),
    r4d_has_last_tab_status: hasField(source, "last_tab_status"),
    r4d_has_last_route_class: hasField(source, "last_route_class"),
    r4d_has_url_host_is_xhs: hasField(source, "url_host_is_xhs"),
    r4d_has_expected_route_matched: hasField(source, "expected_route_matched"),
    r4d_has_elapsed_ms: hasField(source, "elapsed_ms"),
    r4d_has_tab_removed: hasField(source, "tab_removed"),
  };
}

function hasField(result: Record<string, JsonValue>, field: R4aField): boolean {
  return Object.prototype.hasOwnProperty.call(result, field);
}
