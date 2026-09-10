"""把收藏详情安全转换为现有下载领域的作品模型。"""

from datetime import UTC, datetime
from urllib.parse import quote, urlsplit

from xhs_core.domain import (
    Author,
    CollectionFeedDetail,
    CollectionSnapshotItem,
    MediaKind,
    MediaResource,
    WorkDetail,
    WorkType,
)


def collection_feed_detail_to_work_detail(
    detail: CollectionFeedDetail,
    item: CollectionSnapshotItem,
) -> WorkDetail:
    """把一个收藏条目详情转换为 canonical ``WorkDetail``。

    Args:
        detail: 已脱敏的收藏条目详情。
        item: 收藏快照中的条目，用于校验 membership 身份；其
            ``source_order`` 不会被转换成媒体序号。

    Returns:
        可供现有下载领域使用的作品详情。

    Raises:
        ValueError: 收藏条目身份、作者身份或媒体 URL 无效。
    """
    _validate_identity(detail, item)
    work_type = _work_type(detail)
    return WorkDetail(
        work_id=detail.feed_id,
        source_url=_canonical_source_url(detail.feed_id),
        title=detail.title,
        description=detail.body,
        work_type=work_type,
        published_at=_published_at(detail.published_at),
        liked_count=detail.metrics.liked_count,
        collected_count=detail.metrics.collected_count,
        comment_count=detail.metrics.comment_count,
        share_count=detail.metrics.shared_count,
        author=Author(
            author_id=detail.author.user_id,
            nickname=detail.author.nickname or detail.author.user_id,
            profile_url=_canonical_profile_url(detail.author.user_id),
            avatar_url=str(detail.author.avatar_url)
            if detail.author.avatar_url is not None
            else None,
        ),
        media=_media_resources(detail, work_type),
    )


def _validate_identity(
    detail: CollectionFeedDetail, item: CollectionSnapshotItem
) -> None:
    """校验收藏 membership、详情和作者身份，失败时拒绝映射。"""
    if not item.snapshot_id.strip():
        raise ValueError("collection snapshot identity is missing")
    if not item.feed_id.strip() or not detail.feed_id.strip():
        raise ValueError("collection feed identity is missing")
    if item.feed_id != detail.feed_id:
        raise ValueError("collection item and detail feed_id do not match")
    if not detail.author.user_id.strip():
        raise ValueError("author identity is missing")


def _work_type(detail: CollectionFeedDetail) -> WorkType:
    """按现有详情类型和可靠媒体数量选择作品类型。"""
    note_type = detail.note_type.strip().lower()
    if note_type == "video":
        return WorkType.VIDEO
    if note_type == "image":
        return WorkType.GALLERY if len(detail.image_urls) > 1 else WorkType.IMAGE
    return WorkType.UNKNOWN


def _media_resources(
    detail: CollectionFeedDetail, work_type: WorkType
) -> list[MediaResource]:
    """只从可靠图像详情生成有序媒体资源，不虚构视频地址。"""
    if work_type not in {WorkType.IMAGE, WorkType.GALLERY}:
        return []
    resources: list[MediaResource] = []
    for index, raw_url in enumerate(detail.image_urls, start=1):
        media_url = raw_url.strip()
        _validate_media_url(media_url)
        resources.append(
            MediaResource(
                index=index,
                kind=MediaKind.IMAGE,
                url=media_url,
                suffix=_suffix(media_url),
            )
        )
    return resources


def _validate_media_url(value: str) -> None:
    """拒绝空值和非 HTTP(S) 媒体引用。"""
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("media URL is invalid")


def _suffix(value: str) -> str:
    """从 URL 路径读取稳定扩展名，未知时沿用下载器的 ``auto``。"""
    name = urlsplit(value).path.rsplit("/", 1)[-1]
    candidate = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    return candidate if candidate.isalnum() and len(candidate) <= 10 else "auto"


def _published_at(value: int | None) -> datetime | None:
    """把现有毫秒 Unix 时间戳转换为 UTC datetime。"""
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(value / 1000, tz=UTC)
    except (OverflowError, OSError, ValueError) as error:
        raise ValueError("published_at is invalid") from error


def _canonical_source_url(feed_id: str) -> str:
    """根据已校验的 feed identity 构造无敏感参数的 canonical URL。"""
    return f"https://www.xiaohongshu.com/explore/{quote(feed_id, safe='')}"


def _canonical_profile_url(user_id: str) -> str:
    """根据已校验的作者 identity 构造 canonical profile URL。"""
    return f"https://www.xiaohongshu.com/user/profile/{quote(user_id, safe='')}"
