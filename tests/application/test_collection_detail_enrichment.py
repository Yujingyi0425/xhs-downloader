"""Synthetic tests for TC3-B2-B2 collection detail orchestration."""

from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from xhs_adapters.sqlite import (
    SqliteCollectionEnrichmentRepository,
    SqliteCollectionRepository,
)
from xhs_core.application import (
    CollectionDetailEnrichmentOptions,
    CollectionDetailEnrichmentService,
)
from xhs_core.domain import ProviderError, ProviderFailureCode, ProviderKind

from tests.infrastructure.collection_enrichment_fixtures import create_snapshot, detail


class _Runtime:
    def __init__(self, *, failures=None, mismatch=False):
        self.calls: list[tuple[str, str]] = []
        self.active = 0
        self.maximum = 0
        self.failures = failures or {}
        self.mismatch = mismatch

    async def get_feed_detail(self, feed_id, xsec_token, **kwargs):
        self.calls.append((feed_id, kwargs["request_id"]))
        self.active += 1
        self.maximum = max(self.maximum, self.active)
        try:
            failure = self.failures.get(feed_id)
            if failure:
                raise ProviderError(
                    ProviderKind.BROWSER, failure, "synthetic raw error"
                )
            value = detail("wrong-feed" if self.mismatch else feed_id)
            return SimpleNamespace(value=value)
        finally:
            self.active -= 1


def _service(database, runtime, *, missing=()):
    collections = SqliteCollectionRepository(database)
    enrichment = SqliteCollectionEnrichmentRepository(database)

    class _Collections:
        async def get_snapshot(self, snapshot_id):
            return await collections.get_snapshot(snapshot_id)

        async def list_snapshot_items(self, snapshot_id):
            return await collections.list_snapshot_items(snapshot_id)

        async def get_feed_access_context(self, feed_id):
            if feed_id in missing:
                return None
            return await collections.get_feed_access_context(feed_id)

    @asynccontextmanager
    async def lease():
        yield runtime

    return CollectionDetailEnrichmentService(
        _Collections(), enrichment, lease
    ), enrichment


@pytest.mark.asyncio
async def test_orchestration_preserves_order_and_sanitizes_detail(tmp_path):
    """Verify source order, latest access use, and safe persisted detail.

    Args:
        tmp_path: Pytest temporary directory.
    """
    snapshot_id = await create_snapshot(
        tmp_path / "state.db", ["feed-c", "feed-a", "feed-b"]
    )
    runtime = _Runtime()
    service, repository = _service(tmp_path / "state.db", runtime)
    summary = await service.enrich_snapshot(snapshot_id)
    assert [item.feed_id for item in summary.items] == ["feed-c", "feed-a", "feed-b"]
    assert all(item.status.value == "succeeded" for item in summary.items)
    records = await repository.list_snapshot_enrichments(snapshot_id)
    assert all(
        record.detail and "xsec_token" not in record.detail.model_dump()
        for record in records
    )
    assert all(
        record.detail and "comments_cursor" not in record.detail.model_dump()
        for record in records
    )
    assert all(
        "synthetic-import-token" not in record.model_dump_json() for record in records
    )
    assert all(
        request_id.startswith("tc3-enrich-v1-") for _, request_id in runtime.calls
    )


@pytest.mark.asyncio
async def test_missing_context_and_provider_failure_continue_batch(tmp_path):
    """Verify missing context maps safely without aborting later items.

    Args:
        tmp_path: Pytest temporary directory.
    """
    snapshot_id = await create_snapshot(
        tmp_path / "state.db", ["feed-a", "feed-b", "feed-c"]
    )
    runtime = _Runtime(failures={"feed-b": ProviderFailureCode.UNAVAILABLE})
    service, _ = _service(tmp_path / "state.db", runtime, missing={"feed-a"})
    result = await service.enrich_snapshot(snapshot_id)
    assert [item.status.value for item in result.items] == [
        "needs_reimport",
        "failed_retryable",
        "succeeded",
    ]
    assert {feed_id for feed_id, _ in runtime.calls} == {"feed-b", "feed-c"}
    assert result.items[0].last_error_code == "missing_access_context"
    assert result.items[1].last_error_code == "provider_unavailable"


@pytest.mark.asyncio
async def test_retry_attempt_changes_request_id_and_terminal_is_not_reopened(tmp_path):
    """Verify retry request ids include attempt and terminal records remain closed.

    Args:
        tmp_path: Pytest temporary directory.
    """
    snapshot_id = await create_snapshot(tmp_path / "state.db", ["feed-a"])
    runtime = _Runtime(failures={"feed-a": ProviderFailureCode.UNAVAILABLE})
    service, _ = _service(tmp_path / "state.db", runtime)
    first = await service.enrich_snapshot(snapshot_id)
    assert first.items[0].status.value == "failed_retryable"
    runtime.failures.clear()
    second = await service.enrich_snapshot(snapshot_id)
    assert second.items[0].status.value == "succeeded"
    assert runtime.calls[0][1] != runtime.calls[1][1]
    third = await service.enrich_snapshot(snapshot_id)
    assert third.items[0].status.value == "succeeded"
    assert len(runtime.calls) == 2


@pytest.mark.asyncio
async def test_identity_mismatch_is_terminal_and_concurrency_is_bounded(tmp_path):
    """Verify identity mismatch is terminal and detail reads never exceed three.

    Args:
        tmp_path: Pytest temporary directory.
    """
    feeds = [f"feed-{index}" for index in range(6)]
    snapshot_id = await create_snapshot(tmp_path / "state.db", feeds)
    runtime = _Runtime(mismatch=True)
    service, _ = _service(tmp_path / "state.db", runtime)
    result = await service.enrich_snapshot(
        snapshot_id, CollectionDetailEnrichmentOptions(limit=6)
    )
    assert all(item.status.value == "failed_terminal" for item in result.items)
    assert runtime.maximum <= 3
