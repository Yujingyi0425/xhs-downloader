"""TC4-R6 video locator fail-closed proof."""

from pathlib import Path

import pytest
from xhs_adapters.video import SafeVideoArtifactStore
from xhs_core.domain import FeedMediaResource, FeedMediaResult


@pytest.mark.asyncio
async def test_video_artifact_store_without_video_fails_closed(
    tmp_path: Path,
) -> None:
    """验证没有 video resource 的 locator 不会伪装成功。

    Args:
        tmp_path: pytest 提供的临时目录。
    """
    image_url = "https://example.invalid/r6-image-only"
    with pytest.raises(LookupError):
        await SafeVideoArtifactStore(tmp_path, object()).save(
            "snapshot-no-video",
            "feed-no-video",
            FeedMediaResult(
                feed_id="feed-no-video",
                note_type="video",
                media=[
                    FeedMediaResource(
                        index=1, kind="image", url=image_url, suffix="jpg"
                    )
                ],
            ),
        )
