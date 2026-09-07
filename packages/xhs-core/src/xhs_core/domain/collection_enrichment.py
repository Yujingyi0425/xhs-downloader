"""收藏条目详情 enrichment 的非敏感领域模型。"""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from .feeds import FeedAuthor, FeedComment, FeedDetailResult, FeedMetrics


class CollectionEnrichmentStatus(StrEnum):
    """收藏条目详情 enrichment 的独立生命周期。"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_TERMINAL = "failed_terminal"
    NEEDS_REIMPORT = "needs_reimport"
    NEEDS_REVIEW = "needs_review"


ENRICHMENT_VERSION = 1
TERMINAL_ENRICHMENT_STATUSES = frozenset(
    {
        CollectionEnrichmentStatus.SUCCEEDED,
        CollectionEnrichmentStatus.FAILED_TERMINAL,
        CollectionEnrichmentStatus.NEEDS_REIMPORT,
        CollectionEnrichmentStatus.NEEDS_REVIEW,
    }
)


class CollectionFeedDetail(BaseModel):
    """不含访问令牌的可持久化收藏条目详情。"""

    model_config = ConfigDict(extra="forbid")

    feed_id: str = Field(min_length=1, max_length=128)
    title: str = Field(default="", max_length=500)
    body: str = Field(default="", max_length=20_000)
    note_type: str = Field(default="unknown", max_length=32)
    author: FeedAuthor
    metrics: FeedMetrics = Field(default_factory=FeedMetrics)
    image_urls: list[str] = Field(default_factory=list, max_length=100)
    published_at: int | None = Field(default=None, ge=0)
    ip_location: str = Field(default="", max_length=200)
    comments: list[FeedComment] = Field(default_factory=list, max_length=500)
    comments_has_more: bool = False

    @classmethod
    def from_feed_detail(
        cls, detail: FeedDetailResult, expected_feed_id: str
    ) -> "CollectionFeedDetail":
        """显式转换详情结果并校验条目身份。

        Args:
            detail: 现有详情能力返回的结果。
            expected_feed_id: enrichment 记录要求的 feed 标识。

        Returns:
            不含敏感字段的可持久化详情。

        Raises:
            ValueError: 详情身份与 enrichment 条目不一致。
        """
        if detail.feed_id != expected_feed_id:
            raise ValueError("详情 feed_id 与 enrichment 条目不一致")
        return cls(
            feed_id=detail.feed_id,
            title=detail.title,
            body=detail.body,
            note_type=detail.note_type,
            author=detail.author,
            metrics=detail.metrics,
            image_urls=[str(url) for url in detail.image_urls],
            published_at=detail.published_at,
            ip_location=detail.ip_location,
            comments=detail.comments,
            comments_has_more=detail.comments_has_more,
        )


class CollectionFeedEnrichment(BaseModel):
    """一个 snapshot/feed/version 的详情 enrichment 持久化记录。"""

    model_config = ConfigDict(extra="forbid")

    snapshot_id: str = Field(min_length=1, max_length=128)
    feed_id: str = Field(min_length=1, max_length=128)
    enrichment_version: int = Field(default=ENRICHMENT_VERSION, ge=1)
    status: CollectionEnrichmentStatus = CollectionEnrichmentStatus.PENDING
    detail: CollectionFeedDetail | None = None
    attempt_count: int = Field(default=0, ge=0)
    last_error_code: str | None = Field(default=None, max_length=200)
    created_at: datetime
    updated_at: datetime
    enriched_at: datetime | None = None

    def validate_invariants(self) -> None:
        """验证状态与详情、时间字段之间的不变量。"""
        if self.status is CollectionEnrichmentStatus.SUCCEEDED:
            if self.detail is None or self.enriched_at is None:
                raise ValueError("成功 enrichment 必须有 detail 和 enriched_at")
            if self.last_error_code is not None:
                raise ValueError("成功 enrichment 不得保留错误码")
        elif self.detail is not None or self.enriched_at is not None:
            raise ValueError("非成功 enrichment 不得保存 detail 或 enriched_at")

    @classmethod
    def new(
        cls, snapshot_id: str, feed_id: str, now: datetime | None = None
    ) -> "CollectionFeedEnrichment":
        """创建待执行的 enrichment 记录。

        Args:
            snapshot_id: 收藏快照标识。
            feed_id: 快照条目标识。
            now: 可选的合成创建时间。

        Returns:
            初始为 pending 的 enrichment 记录。
        """
        timestamp = now or datetime.now(UTC)
        return cls(
            snapshot_id=snapshot_id,
            feed_id=feed_id,
            created_at=timestamp,
            updated_at=timestamp,
        )
