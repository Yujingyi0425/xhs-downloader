"""GET_FEED_DETAIL ephemeral secret handoff tests."""

import pytest
from aiosqlite import connect
from loguru import logger
from pydantic import SecretStr
from xhs_adapters.sqlite import SqliteBrowserTaskRepository
from xhs_core.application import (
    BrowserExecutionService,
    BrowserTaskEphemeralInputChannel,
    BrowserTaskService,
)
from xhs_core.application.browser_task_ephemeral import _PendingInput, _PendingResult
from xhs_core.domain import BrowserDriver, BrowserTaskError, BrowserTaskStatus

SENTINEL = "synthetic-browser-ephemeral-xsec"


def _payload(token: str = SENTINEL) -> dict:
    return {
        "feed_id": "synthetic-feed",
        "xsec_token": token,
        "comment_limit": 10,
        "include_replies": False,
        "reply_limit": 10,
    }


def _result(token: str = SENTINEL) -> dict:
    return {
        "feed_id": "synthetic-feed",
        "xsec_token": token,
        "author": {"user_id": "synthetic-author"},
    }


async def _services(tmp_path, *, ttl=90, capacity=3):
    channel = BrowserTaskEphemeralInputChannel(ttl_seconds=ttl, capacity=capacity)
    repository = SqliteBrowserTaskRepository(tmp_path / "state.db")
    tasks = BrowserTaskService(repository, channel)
    execution = BrowserExecutionService(repository, 60, channel)
    return repository, tasks, execution, channel


@pytest.mark.asyncio
async def test_ephemeral_detail_persists_metadata_only_and_claims_once(
    tmp_path,
) -> None:
    """Verify validated detail input is transiently hydrated and single-consumed.

    Args:
        tmp_path: Pytest temporary directory.
    """
    repository, tasks, execution, _ = await _services(tmp_path)
    task = await tasks.submit_ephemeral_feed_detail(
        _payload(), "synthetic-request", BrowserDriver.EXTENSION
    )
    stored = await repository.get(task.task_id)
    assert stored is not None
    assert "xsec_token" not in stored.payload
    async with connect(tmp_path / "state.db") as database:
        rows = await database.execute_fetchall("SELECT payload FROM browser_task")
        assert SENTINEL not in str(rows)
    claim = await execution.claim("synthetic-extension")
    assert claim is not None
    assert claim.task.payload["xsec_token"] == SENTINEL
    assert await execution.claim("second-extension") is None


@pytest.mark.asyncio
async def test_success_result_is_transient_but_persisted_task_is_redacted(
    tmp_path,
) -> None:
    """Verify FeedDetailResult reaches the waiter without terminal persistence.

    Args:
        tmp_path: Pytest temporary directory.
    """
    repository, tasks, execution, _ = await _services(tmp_path)
    task = await tasks.submit_ephemeral_feed_detail(_payload())
    claim = await execution.claim("synthetic-extension")
    assert claim is not None and claim.task.task_id == task.task_id
    await execution.update(
        task.task_id, claim.lease_token, BrowserTaskStatus.RUNNING, "running"
    )
    await execution.update(
        task.task_id,
        claim.lease_token,
        BrowserTaskStatus.SUCCEEDED,
        "done",
        _result(),
    )
    persisted = await repository.get(task.task_id)
    assert persisted is not None
    assert SENTINEL not in persisted.model_dump_json()
    delivered = await tasks.wait(task.task_id, 0)
    assert delivered.result is not None
    assert delivered.result["xsec_token"] == SENTINEL
    assert SENTINEL not in (await repository.get(task.task_id)).model_dump_json()


@pytest.mark.asyncio
async def test_media_success_locator_remains_transient_after_diagnostic_change(
    tmp_path,
) -> None:
    """Verify successful media locators remain outside persisted task state.

    Args:
        tmp_path: Pytest temporary directory.
    """
    repository, tasks, execution, _ = await _services(tmp_path)
    task = await tasks.submit_ephemeral_feed_media(
        {"feed_id": "synthetic-feed", "xsec_token": SENTINEL}
    )
    claim = await execution.claim("synthetic-extension")
    assert claim is not None
    result = {
        "feed_id": "synthetic-feed",
        "note_type": "video",
        "media": [
            {
                "index": 1,
                "kind": "video",
                "url": "https://example.invalid/signed.mp4?xsec_token=secret",
                "suffix": "mp4",
            }
        ],
    }

    await execution.update(
        task.task_id,
        claim.lease_token,
        BrowserTaskStatus.SUCCEEDED,
        "done",
        result,
    )
    persisted = await repository.get(task.task_id)
    delivered = await tasks.wait(task.task_id, 0)

    assert persisted is not None
    assert persisted.result == {
        "feed_id": "synthetic-feed",
        "note_type": "video",
        "media_count": 1,
    }
    assert delivered.result is not None
    assert delivered.result["feed_id"] == "synthetic-feed"
    assert delivered.result["media"][0]["url"] == result["media"][0]["url"]
    assert "signed.mp4" not in persisted.model_dump_json()
    assert "xsec_token" not in persisted.model_dump_json()


@pytest.mark.parametrize(
    "status", [BrowserTaskStatus.FAILED, BrowserTaskStatus.NEEDS_REVIEW]
)
@pytest.mark.asyncio
async def test_ephemeral_failure_logs_never_include_raw_secret(
    tmp_path, status
) -> None:
    """Verify ephemeral failure logs suppress executor messages for terminal states.

    Args:
        tmp_path: Pytest temporary directory.
        status: Terminal status being exercised.
    """
    repository, tasks, execution, _ = await _services(tmp_path)
    task = await tasks.submit_ephemeral_feed_detail(_payload())
    claim = await execution.claim("synthetic-extension")
    assert claim is not None
    messages: list[str] = []
    sink_id = logger.add(messages.append, format="{message}")
    try:
        await execution.update(
            task.task_id,
            claim.lease_token,
            status,
            "navigation failed xsec_token=synthetic-ephemeral-log-xsec",
        )
    finally:
        logger.remove(sink_id)
    captured = "\n".join(messages)
    assert "synthetic-ephemeral-log-xsec" not in captured
    assert "xsec_token=" not in captured
    persisted = await repository.get(task.task_id)
    assert persisted is not None
    assert "xsec_token=" not in persisted.message


@pytest.mark.asyncio
async def test_ephemeral_claim_repr_redacts_but_data_keeps_secret(tmp_path) -> None:
    """Verify transient claim data remains available while repr stays safe.

    Args:
        tmp_path: Pytest temporary directory.
    """
    _, tasks, execution, _ = await _services(tmp_path)
    await tasks.submit_ephemeral_feed_detail(_payload("synthetic-ephemeral-repr-xsec"))
    claim = await execution.claim("synthetic-extension")
    assert claim is not None
    assert "synthetic-ephemeral-repr-xsec" not in repr(claim)
    assert "synthetic-ephemeral-repr-xsec" not in repr(claim.task)
    assert claim.task.model_dump()["payload"]["xsec_token"] == (
        "synthetic-ephemeral-repr-xsec"
    )


def test_ephemeral_pending_values_redact_secret_repr() -> None:
    """Verify channel internals do not expose input or result secrets."""
    input_value = _PendingInput(SecretStr("synthetic-ephemeral-repr-xsec"), 1)
    result_value = _PendingResult({"xsec_token": "synthetic-ephemeral-repr-xsec"}, 1)
    assert "synthetic-ephemeral-repr-xsec" not in repr(input_value)
    assert "synthetic-ephemeral-repr-xsec" not in repr(result_value)


@pytest.mark.asyncio
async def test_missing_secret_fails_closed_without_executor_payload(tmp_path) -> None:
    """Verify restart-like loss of the secret fails a claimed detail task closed.

    Args:
        tmp_path: Pytest temporary directory.
    """
    repository, tasks, execution, channel = await _services(tmp_path)
    task = await tasks.submit_ephemeral_feed_detail(_payload())
    await channel.discard(task.task_id)
    assert await execution.claim("synthetic-extension") is None
    failed = await repository.get(task.task_id)
    assert failed is not None
    assert failed.status is BrowserTaskStatus.FAILED
    assert "xsec_token" not in failed.payload
    assert SENTINEL not in failed.model_dump_json()


@pytest.mark.asyncio
async def test_duplicate_request_id_does_not_replace_secret(tmp_path) -> None:
    """Verify duplicate detail submission is idempotent and conflicts safely.

    Args:
        tmp_path: Pytest temporary directory.
    """
    _, tasks, _, channel = await _services(tmp_path)
    first = await tasks.submit_ephemeral_feed_detail(_payload(), "same-request")
    same = await tasks.submit_ephemeral_feed_detail(_payload(), "same-request")
    assert same.task_id == first.task_id
    with pytest.raises(BrowserTaskError):
        await tasks.submit_ephemeral_feed_detail(
            _payload("different-secret"), "same-request"
        )
    assert await channel.consume(first.task_id) == SENTINEL


@pytest.mark.asyncio
async def test_capacity_ttl_and_cancel_cleanup_are_bounded(tmp_path) -> None:
    """Verify bounded capacity, expiry, and pre-claim cancellation cleanup.

    Args:
        tmp_path: Pytest temporary directory.
    """
    repository, tasks, _, channel = await _services(tmp_path, capacity=1)
    first = await tasks.submit_ephemeral_feed_detail(_payload(), "first")
    with pytest.raises(BrowserTaskError):
        await tasks.submit_ephemeral_feed_detail(_payload(), "second")
    await tasks.cancel_before_running(first.task_id)
    assert await channel.consume(first.task_id) is None
    await tasks.submit_ephemeral_feed_detail(_payload(), "second")
    assert channel.capacity == 1
    assert channel.ttl_seconds == 90
    await channel.close()
    assert await repository.get(first.task_id) is not None


@pytest.mark.asyncio
async def test_managed_claim_hydration_is_not_persisted(tmp_path) -> None:
    """Verify managed claim receives full payload while stored snapshot stays safe.

    Args:
        tmp_path: Pytest temporary directory.
    """
    repository, tasks, execution, _ = await _services(tmp_path)
    task = await tasks.submit_ephemeral_feed_detail(
        _payload(), target_driver=BrowserDriver.MANAGED
    )
    claim = await execution.claim("synthetic-managed", BrowserDriver.MANAGED)
    assert claim is not None
    running = await execution.update(
        task.task_id, claim.lease_token, BrowserTaskStatus.RUNNING, "running"
    )
    execution_input = running.model_copy(update={"payload": claim.task.payload})
    assert execution_input.payload["xsec_token"] == SENTINEL
    assert "xsec_token" not in (await repository.get(task.task_id)).payload


def test_ephemeral_channel_rejects_invalid_configuration() -> None:
    """Verify channel TTL and capacity are finite and positive."""
    with pytest.raises(ValueError):
        BrowserTaskEphemeralInputChannel(ttl_seconds=0)
    with pytest.raises(ValueError):
        BrowserTaskEphemeralInputChannel(capacity=0)
