"""收藏详情 enrichment 汇总辅助函数。"""

from hashlib import sha256

from xhs_core.domain import CollectionEnrichmentStatus, CollectionFeedEnrichment


def detail_request_id(
    snapshot_id: str, feed_id: str, version: int, attempt: int
) -> str:
    """从非敏感 enrichment 身份生成 attempt-specific request id。

    Args:
        snapshot_id: 快照标识。
        feed_id: 帖子标识。
        version: enrichment 版本。
        attempt: 当前尝试次数。

    Returns:
        稳定且不含 secret 的请求标识。
    """
    identity = f"{snapshot_id}\x00{feed_id}\x00{version}\x00{attempt}"
    return "tc3-enrich-v1-" + sha256(identity.encode()).hexdigest()


def item_summary(source_order: int, record: CollectionFeedEnrichment, concurrent=False):
    """把 enrichment 记录转换为安全摘要。

    Args:
        source_order: membership 中的原始顺序。
        record: enrichment 记录。
        concurrent: 是否因并发 CAS 冲突而跳过。

    Returns:
        安全条目摘要。
    """
    from .collection_enrichment import CollectionEnrichmentItemSummary

    return CollectionEnrichmentItemSummary(
        feed_id=record.feed_id,
        source_order=source_order,
        status=record.status,
        attempt_count=record.attempt_count,
        last_error_code="concurrent_skipped" if concurrent else record.last_error_code,
        detail=record.detail,
    )


def summary(snapshot_id: str, items):
    """汇总并按状态统计 enrichment 结果。

    Args:
        snapshot_id: 快照标识。
        items: 安全条目摘要列表。

    Returns:
        批次安全汇总。
    """
    from .collection_enrichment import CollectionEnrichmentSummary

    counts = {
        status: sum(item.status is status for item in items)
        for status in CollectionEnrichmentStatus
    }
    return CollectionEnrichmentSummary(
        snapshot_id=snapshot_id,
        total=len(items),
        succeeded=counts[CollectionEnrichmentStatus.SUCCEEDED],
        already_succeeded=counts[CollectionEnrichmentStatus.SUCCEEDED],
        failed_retryable=counts[CollectionEnrichmentStatus.FAILED_RETRYABLE],
        failed_terminal=counts[CollectionEnrichmentStatus.FAILED_TERMINAL],
        needs_reimport=counts[CollectionEnrichmentStatus.NEEDS_REIMPORT],
        needs_review=counts[CollectionEnrichmentStatus.NEEDS_REVIEW],
        running_skipped=counts[CollectionEnrichmentStatus.RUNNING],
        concurrent_skipped=sum(
            item.last_error_code == "concurrent_skipped" for item in items
        ),
        items=items,
    )
