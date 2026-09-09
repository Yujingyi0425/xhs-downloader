import { describe, expect, it } from "vitest";

import { buildR4dSubmissionProbe } from "./r4d-submission-probe";

describe("R4D submission probe", () => {
  it("只提交 R4A 字段的 presence，不提交字段值", () => {
    const result = buildR4dSubmissionProbe({
      failure_stage: "background",
      failure_code: "DETAIL_NAVIGATION_FAILED",
      target_tab_exists: true,
      elapsed_ms: 321,
      xsec_token: "must-not-be-copied",
    });

    expect(result).toEqual({
      failure_stage: "background",
      failure_code: "DETAIL_NAVIGATION_FAILED",
      target_tab_exists: true,
      elapsed_ms: 321,
      xsec_token: "must-not-be-copied",
      r4d_submission_probe: true,
      r4d_has_target_tab_exists: true,
      r4d_has_last_tab_status: false,
      r4d_has_last_route_class: false,
      r4d_has_url_host_is_xhs: false,
      r4d_has_expected_route_matched: false,
      r4d_has_elapsed_ms: true,
      r4d_has_tab_removed: false,
    });
    expect(result.r4d_has_elapsed_ms).toBe(true);
  });

  it("缺失 result 时 fail closed 为全 false", () => {
    expect(buildR4dSubmissionProbe()).toEqual({
      r4d_submission_probe: true,
      r4d_has_target_tab_exists: false,
      r4d_has_last_tab_status: false,
      r4d_has_last_route_class: false,
      r4d_has_url_host_is_xhs: false,
      r4d_has_expected_route_matched: false,
      r4d_has_elapsed_ms: false,
      r4d_has_tab_removed: false,
    });
  });
});
