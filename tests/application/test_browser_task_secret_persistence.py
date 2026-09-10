"""Browser task xsec secret persistence boundary tests."""

import pytest
from aiosqlite import connect
from xhs_adapters.sqlite import SqliteBrowserTaskRepository
from xhs_core.application import BrowserExecutionService, BrowserTaskService
from xhs_core.domain import (
    BrowserTaskKind,
    BrowserTaskStatus,
    sanitize_browser_task_result,
)

TEST_ONLY_FAKE_XSEC_TOKEN = "TEST_ONLY_FAKE_XSEC_TOKEN"


async def _services(tmp_path):
    repository = SqliteBrowserTaskRepository(tmp_path / "state.db")
    tasks = BrowserTaskService(repository)
    execution = BrowserExecutionService(repository, 60)
    return repository, tasks, execution


@pytest.mark.parametrize(
    ("kind", "payload"),
    [
        (
            BrowserTaskKind.GET_FEED_MEDIA,
            {
                "feed_id": "synthetic-feed",
                "xsec_token": TEST_ONLY_FAKE_XSEC_TOKEN,
            },
        ),
        (
            BrowserTaskKind.SET_LIKE,
            {
                "feed_id": "synthetic-feed",
                "xsec_token": TEST_ONLY_FAKE_XSEC_TOKEN,
                "active": True,
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_generic_xsec_task_submit_never_persists_input_secret(
    tmp_path,
    kind,
    payload,
) -> None:
    """Verify the generic task boundary keeps xsec input transient.

    Args:
        tmp_path: Pytest temporary directory.
        kind: Browser task kind under test.
        payload: Synthetic secret-bearing task input.
    """
    repository, tasks, execution = await _services(tmp_path)
    task = await tasks.submit(kind, payload)

    stored = await repository.get(task.task_id)
    assert stored is not None
    assert "xsec_token" not in stored.payload
    async with connect(tmp_path / "state.db") as database:
        rows = await database.execute_fetchall("SELECT payload FROM browser_task")
        assert TEST_ONLY_FAKE_XSEC_TOKEN not in str(rows)

    claim = await execution.claim("synthetic-extension")
    assert claim is not None
    assert claim.task.payload["xsec_token"] == TEST_ONLY_FAKE_XSEC_TOKEN


@pytest.mark.asyncio
async def test_success_result_secret_is_transient_and_api_snapshot_is_safe(
    tmp_path,
) -> None:
    """Verify nested result secrets are delivered once but never read back.

    Args:
        tmp_path: Pytest temporary directory.
    """
    repository, tasks, execution = await _services(tmp_path)
    task = await tasks.submit(BrowserTaskKind.LIST_FEEDS, {})
    claim = await execution.claim("synthetic-extension")
    assert claim is not None
    result = {
        "items": [
            {
                "feed_id": "synthetic-feed",
                "xsec_token": TEST_ONLY_FAKE_XSEC_TOKEN,
                "author": {"user_id": "synthetic-author"},
            }
        ],
        "source": "home",
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
    assert delivered.result is not None
    assert (
        delivered.result["items"][0]["xsec_token"]
        == TEST_ONLY_FAKE_XSEC_TOKEN
    )
    assert "xsec_token" not in persisted.model_dump_json()
    async with connect(tmp_path / "state.db") as database:
        rows = await database.execute_fetchall("SELECT payload FROM browser_task")
        assert TEST_ONLY_FAKE_XSEC_TOKEN not in str(rows)


def test_success_result_sanitizer_removes_secret_adjacent_fields() -> None:
    """Verify persisted result sanitization removes token-bearing URL inputs.

    Returns:
        None.
    """
    safe = sanitize_browser_task_result(
        {
            "url": (
                "https://example.invalid/media?xsec_token="
                f"{TEST_ONLY_FAKE_XSEC_TOKEN}&keep=1"
            ),
            "pending_url": "https://example.invalid/pending",
            "cookie": "synthetic-cookie",
            "authorization": "Bearer synthetic",
            "nested": {"xsec_token": TEST_ONLY_FAKE_XSEC_TOKEN},
        }
    )

    assert safe == {"url": "https://example.invalid/media?keep=1", "nested": {}}
