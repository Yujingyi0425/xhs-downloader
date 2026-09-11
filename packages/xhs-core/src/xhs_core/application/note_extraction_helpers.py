"""原始笔记抽取的纯数据辅助函数。"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from xhs_core.domain import (
    NoteExtractionRecord,
    NoteExtractionStatus,
    TextProvenance,
    TextProvenanceSource,
)


def _base_record(snapshot_id, feed_id, current, detail, media_type):
    sources = []
    if detail.title.strip():
        sources.append(
            TextProvenance(source=TextProvenanceSource.NOTE_TITLE, text=detail.title)
        )
    if detail.body.strip():
        sources.append(
            TextProvenance(source=TextProvenanceSource.NOTE_BODY, text=detail.body)
        )
    record = current or NoteExtractionRecord(snapshot_id=snapshot_id, feed_id=feed_id)
    return record.model_copy(
        update={
            "media_type": media_type,
            "title": detail.title or None,
            "body": detail.body or None,
            "author_metadata": {
                "user_id": detail.author.user_id,
                "nickname": detail.author.nickname or None,
            },
            "publish_time": detail.published_at,
            "location": detail.ip_location or None,
            "text_provenance": sources,
            "combined_text": _combined_text(sources),
            "updated_at": datetime.now(UTC),
        }
    )


def _combined_text(sources: list[TextProvenance]) -> str | None:
    values = [entry.text.strip() for entry in sources if entry.text.strip()]
    return "\n".join(values) or None


def _safe_media_path(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    if root not in candidate.parents:
        raise ValueError("media artifact path escapes configured root")
    return candidate


async def _save_partial(
    repository: Any,
    record: NoteExtractionRecord,
    artifacts: list | None,
    errors: list[str],
    media_type=None,
) -> NoteExtractionRecord:
    update: dict[str, Any] = {
        "extraction_status": NoteExtractionStatus.PARTIAL,
        "extraction_error_codes": errors,
    }
    if artifacts is not None:
        update["media_artifacts"] = artifacts
    if media_type is not None:
        update["media_type"] = media_type
    return await repository.save(record.model_copy(update=update))
