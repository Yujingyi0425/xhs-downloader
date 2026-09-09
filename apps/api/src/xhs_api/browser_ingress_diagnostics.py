"""浏览器任务结果 HTTP ingress 的 presence-only 诊断。"""

import logging
from collections.abc import Mapping
from typing import Any

_LOGGER = logging.getLogger(__name__)
_R4A_FIELDS = (
    "target_tab_exists",
    "last_tab_status",
    "last_route_class",
    "url_host_is_xhs",
    "expected_route_matched",
    "elapsed_ms",
    "tab_removed",
)


def observe_r4d_submission(
    task_id: str,
    result: Mapping[str, Any] | None,
) -> dict[str, bool]:
    """记录 R4D probe 与 R4A 字段是否出现在 HTTP ingress。

    Args:
        task_id: 当前浏览器任务的内部标识。
        result: 未信任的任务结果映射；只检查键是否存在。

    Returns:
        不包含字段值的 presence-only 诊断映射。
    """
    source = result if isinstance(result, Mapping) else {}
    observed = {
        "probe_present": "r4d_submission_probe" in source,
        **{f"{field}_present": field in source for field in _R4A_FIELDS},
    }
    _LOGGER.info(
        "R4D submission ingress task=%s %s",
        task_id,
        " ".join(f"{key}={value}" for key, value in observed.items()),
    )
    return observed
