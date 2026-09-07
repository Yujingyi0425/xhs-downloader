"""Synthetic state-transition tests for collection enrichment."""

from pathlib import Path

import pytest
from xhs_adapters.sqlite.collection_enrichments import (
    SqliteCollectionEnrichmentRepository,
)
from xhs_core.domain.collection_enrichment import (
    CollectionEnrichmentStatus,
    CollectionFeedDetail,
)
from xhs_core.domain.collection_enrichment_ports import EnrichmentStateConflictError

from .collection_enrichment_fixtures import create_snapshot, detail


@pytest.mark.asyncio
async def test_domain_conversion_and_status_contract() -> None:
    """Verify domain conversion, status contract, and sensitive-field exclusion."""
    converted = CollectionFeedDetail.from_feed_detail(detail(), "feed-a")
    assert converted.title == "合成标题"
    assert "xsec_token" not in converted.model_dump()
    assert "comments_cursor" not in converted.model_dump()
    assert "synthetic-xsec-never-persist" not in converted.model_dump_json()
    with pytest.raises(ValueError, match="feed_id"):
        CollectionFeedDetail.from_feed_detail(detail(), "feed-other")
    assert CollectionEnrichmentStatus.PENDING not in {
        CollectionEnrichmentStatus.SUCCEEDED,
        CollectionEnrichmentStatus.FAILED_TERMINAL,
        CollectionEnrichmentStatus.NEEDS_REIMPORT,
        CollectionEnrichmentStatus.NEEDS_REVIEW,
    }


@pytest.mark.asyncio
async def test_create_cas_success_and_stale_failure_are_safe(tmp_path: Path) -> None:
    """Verify idempotent creation, CAS, retries, and stale-worker protection.

    Args:
        tmp_path: Pytest temporary directory.
    """
    database = tmp_path / "state.db"
    snapshot_id = await create_snapshot(database, ["feed-a", "feed-b"])
    repository = SqliteCollectionEnrichmentRepository(database)
    first = await repository.ensure_enrichment(snapshot_id, "feed-a")
    assert await repository.ensure_enrichment(snapshot_id, "feed-a") == first
    running = await repository.transition_enrichment(
        snapshot_id,
        "feed-a",
        {CollectionEnrichmentStatus.PENDING},
        CollectionEnrichmentStatus.RUNNING,
    )
    assert running.attempt_count == 1
    again = await repository.transition_enrichment(
        snapshot_id,
        "feed-a",
        {CollectionEnrichmentStatus.RUNNING},
        CollectionEnrichmentStatus.RUNNING,
    )
    assert again.attempt_count == 1
    succeeded = await repository.save_detail(
        snapshot_id, "feed-a", CollectionFeedDetail.from_feed_detail(detail(), "feed-a")
    )
    assert succeeded.status is CollectionEnrichmentStatus.SUCCEEDED
    assert succeeded.detail is not None and succeeded.enriched_at is not None
    with pytest.raises(EnrichmentStateConflictError):
        await repository.transition_enrichment(
            snapshot_id,
            "feed-a",
            {CollectionEnrichmentStatus.RUNNING},
            CollectionEnrichmentStatus.FAILED_RETRYABLE,
            error_code="late-worker",
        )
    assert (
        await repository.get_enrichment(snapshot_id, "feed-a")
    ).status is CollectionEnrichmentStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_terminal_statuses_are_persistent_and_immutable(tmp_path: Path) -> None:
    """Verify terminal statuses persist and cannot be reopened.

    Args:
        tmp_path: Pytest temporary directory.
    """
    database = tmp_path / "state.db"
    snapshot_id = await create_snapshot(database, ["feed-a", "feed-b", "feed-c"])
    repository = SqliteCollectionEnrichmentRepository(database)
    statuses = [
        CollectionEnrichmentStatus.FAILED_TERMINAL,
        CollectionEnrichmentStatus.NEEDS_REIMPORT,
        CollectionEnrichmentStatus.NEEDS_REVIEW,
    ]
    for feed_id, status in zip(["feed-a", "feed-b", "feed-c"], statuses, strict=True):
        await repository.ensure_enrichment(snapshot_id, feed_id)
        await repository.transition_enrichment(
            snapshot_id,
            feed_id,
            {CollectionEnrichmentStatus.PENDING},
            status,
            error_code="synthetic-token-expired",
        )
    reopened = SqliteCollectionEnrichmentRepository(database)
    for feed_id, status in zip(["feed-a", "feed-b", "feed-c"], statuses, strict=True):
        record = await reopened.get_enrichment(snapshot_id, feed_id)
        assert record.status is status
        assert record.detail is None and record.enriched_at is None
        with pytest.raises(EnrichmentStateConflictError):
            await reopened.transition_enrichment(
                snapshot_id, feed_id, {status}, CollectionEnrichmentStatus.RUNNING
            )


@pytest.mark.asyncio
async def test_success_transition_and_error_code_bounds_fail_closed(
    tmp_path: Path,
) -> None:
    """Verify success-transition restrictions and the error-code bound.

    Args:
        tmp_path: Pytest temporary directory.
    """
    database = tmp_path / "state.db"
    snapshot_id = await create_snapshot(database, ["feed-a", "feed-b", "feed-c"])
    repository = SqliteCollectionEnrichmentRepository(database)
    await repository.ensure_enrichment(snapshot_id, "feed-a")
    with pytest.raises(EnrichmentStateConflictError):
        await repository.transition_enrichment(
            snapshot_id,
            "feed-a",
            {CollectionEnrichmentStatus.PENDING},
            CollectionEnrichmentStatus.SUCCEEDED,
        )
    await repository.ensure_enrichment(snapshot_id, "feed-b")
    await repository.transition_enrichment(
        snapshot_id,
        "feed-b",
        {CollectionEnrichmentStatus.PENDING},
        CollectionEnrichmentStatus.FAILED_RETRYABLE,
        error_code="synthetic-timeout",
    )
    retried = await repository.transition_enrichment(
        snapshot_id,
        "feed-b",
        {CollectionEnrichmentStatus.FAILED_RETRYABLE},
        CollectionEnrichmentStatus.RUNNING,
    )
    assert retried.attempt_count == 1
    await repository.ensure_enrichment(snapshot_id, "feed-c")
    with pytest.raises(EnrichmentStateConflictError):
        await repository.transition_enrichment(
            snapshot_id,
            "feed-c",
            {CollectionEnrichmentStatus.PENDING},
            CollectionEnrichmentStatus.FAILED_RETRYABLE,
            error_code="x" * 201,
        )
    assert (
        await repository.get_enrichment(snapshot_id, "feed-c")
    ).status is CollectionEnrichmentStatus.PENDING
