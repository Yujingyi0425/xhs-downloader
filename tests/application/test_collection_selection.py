"""收藏快照选择性处理的 identity 校验测试。"""

import pytest
from xhs_core.application import CollectionSelectionError
from xhs_core.application.collection_selection import select_snapshot_items
from xhs_core.domain import CollectionSnapshotItem


def items() -> list[CollectionSnapshotItem]:
    """构造按收藏顺序排列的合成 membership。

    Returns:
        按收藏顺序排列的合成 membership。
    """
    return [
        CollectionSnapshotItem(
            snapshot_id="snapshot-a", feed_id=feed_id, source_order=order
        )
        for order, feed_id in enumerate(("feed-a", "feed-b", "feed-c"))
    ]


def test_selection_uses_feed_identity_and_snapshot_order() -> None:
    """请求顺序变化时仍按 snapshot source_order 返回。"""
    selected = select_snapshot_items(items(), ["feed-c", "feed-a"])
    assert [item.feed_id for item in selected] == ["feed-a", "feed-c"]


def test_omitted_selection_keeps_all_items() -> None:
    """省略选择时保持既有全量语义。"""
    assert select_snapshot_items(items(), None) == items()


@pytest.mark.parametrize(
    "selection",
    [[], ["feed-a", "feed-a"], ["feed-not-in-snapshot"]],
)
def test_invalid_selection_is_rejected(selection: list[str]) -> None:
    """空选择、重复 identity 和未知 feed 都 fail closed。

    Args:
        selection: 待校验的合成选择。
    """
    with pytest.raises(CollectionSelectionError):
        select_snapshot_items(items(), selection)


def test_feed_from_another_snapshot_is_rejected() -> None:
    """同名 feed 不存在于当前 snapshot 时不能跨快照处理。"""
    other_snapshot = [
        CollectionSnapshotItem(
            snapshot_id="snapshot-b", feed_id="feed-b", source_order=0
        )
    ]
    with pytest.raises(CollectionSelectionError):
        select_snapshot_items(
            other_snapshot, [other_snapshot[0].feed_id], snapshot_id="snapshot-a"
        )
