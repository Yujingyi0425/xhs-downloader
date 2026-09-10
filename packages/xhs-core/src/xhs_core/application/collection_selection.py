"""收藏快照选择性处理的稳定 identity 校验。"""

from collections.abc import Sequence

from xhs_core.domain import CollectionSnapshotItem


class CollectionSelectionError(ValueError):
    """选择的收藏条目不能安全映射到目标快照。"""


def select_snapshot_items(
    items: Sequence[CollectionSnapshotItem],
    selected_feed_ids: Sequence[str] | None,
    *,
    snapshot_id: str | None = None,
) -> list[CollectionSnapshotItem]:
    """按 snapshot membership 顺序选择收藏条目。

    Args:
        items: 目标 snapshot 的有序 membership。
        selected_feed_ids: 可选的稳定 feed identity；为空表示全量。
        snapshot_id: 可选的目标 snapshot identity。

    Returns:
        按原 snapshot `source_order` 排列的选择结果。

    Raises:
        CollectionSelectionError: 选择为空、重复或不属于目标 snapshot。
    """
    ordered_items = list(items)
    if snapshot_id is not None and any(
        item.snapshot_id != snapshot_id for item in ordered_items
    ):
        raise CollectionSelectionError("snapshot item 不属于目标快照")
    if selected_feed_ids is None:
        return ordered_items
    requested = list(selected_feed_ids)
    if not requested:
        raise CollectionSelectionError("selected_feed_ids 不能为空")
    if len(set(requested)) != len(requested):
        raise CollectionSelectionError("selected_feed_ids 不能重复")
    known = {item.feed_id for item in ordered_items}
    unknown = [feed_id for feed_id in requested if feed_id not in known]
    if unknown:
        raise CollectionSelectionError("选择的收藏条目不属于该快照")
    selected = {feed_id for feed_id in requested}
    return [item for item in ordered_items if item.feed_id in selected]
