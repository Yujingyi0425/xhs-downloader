"""收藏详情到下载作品模型的合成映射测试。"""

from datetime import UTC, datetime

import pytest
from xhs_core.application.collection_work_mapping import (
    collection_feed_detail_to_work_detail,
)
from xhs_core.domain import (
    CollectionFeedDetail,
    CollectionSnapshotItem,
    FeedAuthor,
    FeedMetrics,
    WorkType,
)


def item(feed_id: str = "feed-a", source_order: int = 0) -> CollectionSnapshotItem:
    """构造不含敏感信息的合成收藏 membership。

    Args:
        feed_id: 合成收藏作品标识。
        source_order: 合成收藏顺序。

    Returns:
        合成收藏快照条目。
    """
    return CollectionSnapshotItem(
        snapshot_id="synthetic-snapshot", feed_id=feed_id, source_order=source_order
    )


def detail(
    feed_id: str = "feed-a",
    *,
    note_type: str = "image",
    image_urls: list[str] | None = None,
) -> CollectionFeedDetail:
    """构造不含 token、Cookie 或真实用户数据的合成详情。

    Args:
        feed_id: 合成收藏作品标识。
        note_type: 合成笔记类型。
        image_urls: 合成媒体地址列表。

    Returns:
        合成收藏详情。
    """
    return CollectionFeedDetail(
        feed_id=feed_id,
        title="合成标题",
        body="合成正文",
        note_type=note_type,
        author=FeedAuthor(user_id="author-a", nickname="合成作者"),
        metrics=FeedMetrics(
            liked=True,
            liked_count="7",
            collected_count="8",
            comment_count="9",
            shared_count="10",
        ),
        image_urls=image_urls or [],
        published_at=1_700_000_000_000,
    )


def test_single_image_mapping_and_identity() -> None:
    """单图映射为 IMAGE 且保留作品身份。"""
    mapped = collection_feed_detail_to_work_detail(
        detail(image_urls=["https://example.invalid/one.jpg"]), item()
    )
    assert mapped.work_id == "feed-a"
    assert mapped.source_url == "https://www.xiaohongshu.com/explore/feed-a"
    assert mapped.work_type is WorkType.IMAGE
    assert [media.index for media in mapped.media] == [1]
    assert mapped.media[0].url == "https://example.invalid/one.jpg"


def test_multi_image_mapping_preserves_1_to_n_order() -> None:
    """多图映射为 GALLERY，并独立使用媒体序号。"""
    mapped = collection_feed_detail_to_work_detail(
        detail(image_urls=["https://example.invalid/a.jpg", "https://example.invalid/b"]),
        item(source_order=17),
    )
    assert mapped.work_type is WorkType.GALLERY
    assert [media.index for media in mapped.media] == [1, 2]
    assert [media.url for media in mapped.media] == [
        "https://example.invalid/a.jpg",
        "https://example.invalid/b",
    ]


def test_video_maps_to_canonical_type_without_inventing_video_url() -> None:
    """视频只保留 canonical 类型，不伪造尚未获取的媒体地址。"""
    mapped = collection_feed_detail_to_work_detail(
        detail(note_type="video", image_urls=["https://example.invalid/cover.jpg"]),
        item(),
    )
    assert mapped.work_type is WorkType.VIDEO
    assert mapped.media == []


def test_unknown_type_keeps_unknown_semantics() -> None:
    """未知类型不被图片数量强行升级。"""
    mapped = collection_feed_detail_to_work_detail(
        detail(note_type="unknown", image_urls=["https://example.invalid/unknown.jpg"]),
        item(),
    )
    assert mapped.work_type is WorkType.UNKNOWN
    assert mapped.media == []


def test_missing_optional_metadata_uses_existing_optional_semantics() -> None:
    """可选发布时间、头像和文本为空时不补造内容。"""
    source = detail(image_urls=[]).model_copy(
        update={"title": "", "body": "", "published_at": None}
    )
    source.author = source.author.model_copy(
        update={"nickname": "", "avatar_url": None}
    )
    mapped = collection_feed_detail_to_work_detail(source, item())
    assert mapped.title == ""
    assert mapped.description == ""
    assert mapped.published_at is None
    assert mapped.author.nickname == "author-a"
    assert mapped.author.avatar_url is None


def test_identity_mismatch_is_rejected() -> None:
    """详情与收藏 membership 不一致时 fail closed。"""
    with pytest.raises(ValueError, match="feed_id"):
        collection_feed_detail_to_work_detail(detail("other-feed"), item("feed-a"))


def test_missing_required_identity_is_rejected() -> None:
    """绕过模型构造的空身份也必须被 mapper 拒绝。"""
    malformed = CollectionFeedDetail.model_construct(
        feed_id="",
        title="",
        body="",
        note_type="unknown",
        author=FeedAuthor(user_id="author-a"),
        metrics=FeedMetrics(),
        image_urls=[],
        published_at=None,
    )
    with pytest.raises(ValueError, match="identity"):
        collection_feed_detail_to_work_detail(malformed, item(feed_id=""))


def test_empty_media_is_valid() -> None:
    """空媒体是明确的可表示状态。"""
    mapped = collection_feed_detail_to_work_detail(detail(image_urls=[]), item())
    assert mapped.media == []


def test_invalid_media_url_is_rejected() -> None:
    """图像详情中的非法 URL 不被静默写入 WorkDetail。"""
    with pytest.raises(ValueError, match="media URL"):
        collection_feed_detail_to_work_detail(
            detail(image_urls=["not-a-url"]), item()
        )


def test_repeated_mapping_is_deterministic() -> None:
    """相同输入重复映射得到完全相同的 canonical 输出。"""
    source = detail(image_urls=["https://example.invalid/a.jpg", "https://example.invalid/b.png"])
    first = collection_feed_detail_to_work_detail(source, item())
    second = collection_feed_detail_to_work_detail(source, item())
    assert first == second
    assert first.published_at == datetime.fromtimestamp(
        1_700_000_000, tz=UTC
    )


def test_mapper_output_has_no_secret_adjacent_fields() -> None:
    """映射输出只包含脱敏详情，不携带 token、Cookie 或授权字段。"""
    mapped = collection_feed_detail_to_work_detail(
        detail(image_urls=["https://example.invalid/a.jpg"]), item()
    )
    serialized = mapped.model_dump_json().lower()
    assert "token" not in serialized
    assert "cookie" not in serialized
    assert "authorization" not in serialized
