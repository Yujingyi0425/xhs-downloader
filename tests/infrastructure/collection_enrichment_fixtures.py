"""Synthetic fixtures shared by collection enrichment tests."""

from datetime import UTC, datetime
from pathlib import Path

from pydantic import SecretStr
from xhs_adapters.sqlite.collections import SqliteCollectionRepository
from xhs_core.domain.collection import (
    CollectionImportCommand,
    CollectionImportItem,
    collection_fingerprint,
)
from xhs_core.domain.feeds import FeedAuthor, FeedComment, FeedDetailResult, FeedMetrics


def import_command(request_id: str, feeds: list[str]) -> CollectionImportCommand:
    """Build a synthetic collection import command.

    Args:
        request_id: Synthetic request identifier.
        feeds: Synthetic feed identifiers.

    Returns:
        A synthetic import command.
    """
    return CollectionImportCommand(
        request_id=request_id,
        source_type="board",
        board_id="synthetic-board",
        items=[
            CollectionImportItem(
                feed_id=feed,
                xsec_token=SecretStr("synthetic-import-token"),
                source_order=index,
            )
            for index, feed in enumerate(feeds)
        ],
    )


async def create_snapshot(database: Path, feeds: list[str]) -> str:
    """Create a synthetic TC2 snapshot and return its identifier.

    Args:
        database: Temporary SQLite path.
        feeds: Synthetic feed identifiers.

    Returns:
        The created snapshot identifier.
    """
    repository = SqliteCollectionRepository(database)
    command = import_command("synthetic-request", feeds)
    snapshot, _ = await repository.import_snapshot(
        command, collection_fingerprint(command), datetime(2026, 1, 1, tzinfo=UTC)
    )
    return snapshot.snapshot_id


def detail(
    feed_id: str = "feed-a",
    *,
    note_type: str = "image",
    image_urls: list[str] | None = None,
) -> FeedDetailResult:
    """Build a synthetic detail result with nested comments.

    Args:
        feed_id: Synthetic feed identifier.
        note_type: Synthetic note type.
        image_urls: Synthetic image locators.

    Returns:
        A synthetic detail result.
    """
    author = FeedAuthor(user_id="author-a", nickname="合成作者")
    reply = FeedComment(comment_id="reply-a", content="合成回复", author=author)
    comment = FeedComment(
        comment_id="comment-a", content="合成评论", author=author, replies=[reply]
    )
    return FeedDetailResult(
        feed_id=feed_id,
        xsec_token="synthetic-xsec-never-persist",
        title="合成标题",
        body="Unicode 正文",
        note_type=note_type,
        author=author,
        metrics=FeedMetrics(liked=True, liked_count="7"),
        image_urls=image_urls or ["https://example.invalid/image.jpg"],
        published_at=1_700_000_000,
        ip_location="合成地点",
        comments=[comment],
        comments_has_more=True,
    )
