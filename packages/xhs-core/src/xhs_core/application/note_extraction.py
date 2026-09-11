"""收藏笔记原始文本抽取的可重启应用服务。"""

from pathlib import Path

from xhs_core.domain import (
    CollectionEnrichmentStatus,
    CollectionMediaArtifactRepository,
    CollectionRepository,
    ExtractionArtifact,
    ExtractionMediaType,
    ImageOcr,
    ImageOcrRecord,
    MediaKind,
    NoteExtractionRecord,
    NoteExtractionRepository,
    NoteExtractionStatus,
    TextProvenance,
    TextProvenanceSource,
    VideoContentRepository,
)

from .collection_media_service import collection_media_request_id
from .note_extraction_helpers import (
    _base_record,
    _combined_text,
    _failed_image_errors,
    _safe_media_path,
    _save_partial,
    _video_provenance,
)


class NoteExtractionService:
    """从已持久化详情和本地产物生成 canonical extraction record。"""

    def __init__(
        self,
        collections: CollectionRepository,
        enrichments,
        media: CollectionMediaArtifactRepository,
        extractions: NoteExtractionRepository,
        videos: VideoContentRepository,
        ocr: ImageOcr | None,
        media_root: Path,
    ) -> None:
        self._collections = collections
        self._enrichments = enrichments
        self._media = media
        self._extractions = extractions
        self._videos = videos
        self._ocr = ocr
        self._media_root = media_root.resolve()

    async def process_snapshot(
        self,
        snapshot_id: str,
        limit: int | None = None,
        retry_failed: bool = False,
    ) -> list[NoteExtractionRecord]:
        """按收藏顺序处理有详情的条目，单条失败不阻断批次。

        Args:
            snapshot_id: 收藏快照标识。
            limit: 本轮最多处理的条目数。
            retry_failed: 是否重试历史失败或部分成功记录。

        Returns:
            本轮处理或读回的抽取记录。
        """
        if await self._collections.get_snapshot(snapshot_id) is None:
            raise LookupError(snapshot_id)
        items = await self._collections.list_snapshot_items(snapshot_id)
        records: list[NoteExtractionRecord] = []
        for item in items:
            if limit is not None and len(records) >= limit:
                break
            current = await self._extractions.get(snapshot_id, item.feed_id)
            if current and current.extraction_status is NoteExtractionStatus.SUCCEEDED:
                records.append(current)
                continue
            if (
                current
                and not retry_failed
                and current.extraction_status
                in {
                    NoteExtractionStatus.PARTIAL,
                    NoteExtractionStatus.FAILED,
                }
            ):
                records.append(current)
                continue
            records.append(await self._process_one(snapshot_id, item.feed_id, current))
        return records

    async def list_snapshot(self, snapshot_id: str) -> list[NoteExtractionRecord]:
        """只读抽取记录，不触发详情、下载或 OCR。

        Args:
            snapshot_id: 收藏快照标识。

        Returns:
            按收藏顺序排列的抽取记录。
        """
        if await self._collections.get_snapshot(snapshot_id) is None:
            raise LookupError(snapshot_id)
        return await self._extractions.list_snapshot(snapshot_id)

    async def get(self, snapshot_id: str, feed_id: str) -> NoteExtractionRecord | None:
        """Args: snapshot_id, feed_id. Returns: one canonical record or None."""
        if await self._collections.get_snapshot(snapshot_id) is None:
            raise LookupError(snapshot_id)
        return await self._extractions.get(snapshot_id, feed_id)

    async def _process_one(self, snapshot_id, feed_id, current):
        enrichment = await self._enrichments.get_enrichment(snapshot_id, feed_id)
        if (
            not enrichment
            or enrichment.status is not CollectionEnrichmentStatus.SUCCEEDED
            or not enrichment.detail
        ):
            record = current or NoteExtractionRecord(
                snapshot_id=snapshot_id, feed_id=feed_id
            )
            return await _save_partial(
                self._extractions,
                record,
                None,
                ["detail_not_ready"],
                ExtractionMediaType.UNKNOWN,
            )
        detail = enrichment.detail
        media_type = ExtractionMediaType(detail.note_type)
        record = _base_record(snapshot_id, feed_id, current, detail, media_type)
        if media_type is ExtractionMediaType.IMAGE:
            return await self._process_image(record)
        if media_type is ExtractionMediaType.VIDEO:
            return await self._process_video(record)
        return await self._extractions.save(
            record.model_copy(
                update={
                    "extraction_status": NoteExtractionStatus.PARTIAL,
                    "extraction_error_codes": ["unsupported_media_type"],
                }
            )
        )

    async def _process_image(self, record: NoteExtractionRecord):
        request_id = collection_media_request_id(record.snapshot_id, record.feed_id)
        batch = await self._media.get(request_id)
        if batch is None:
            return await _save_partial(
                self._extractions, record, [], ["media_artifact_not_ready"]
            )
        successful = [
            item
            for item in batch.items
            if item.status.value == "succeeded"
            and item.kind is MediaKind.IMAGE
            and item.artifact is not None
        ]
        failed_errors = _failed_image_errors(batch)
        if not successful:
            return await _save_partial(
                self._extractions,
                record,
                [],
                [
                    *failed_errors,
                    "image_artifact_missing",
                ],
            )
        ocr_records: list[ImageOcrRecord] = []
        errors: list[str] = list(failed_errors)
        for item in sorted(successful, key=lambda value: value.media_index):
            artifact = item.artifact
            assert artifact is not None
            extracted = ExtractionArtifact(
                feed_id=record.feed_id,
                media_index=item.media_index,
                path=artifact.path.replace("\\", "/"),
                artifact_ref=f"collection-media:{record.snapshot_id}:{record.feed_id}:{item.media_index}",
                sha256=artifact.sha256,
                size=artifact.size,
            )
            try:
                safe_path = _safe_media_path(self._media_root, artifact.path)
            except ValueError:
                ocr_records.append(
                    ImageOcrRecord(
                        media_index=item.media_index,
                        artifact=extracted,
                        status="FAILED",
                        error_code="artifact_path_invalid",
                    )
                )
                errors.append("artifact_path_invalid")
                continue
            if self._ocr is None:
                ocr_records.append(
                    ImageOcrRecord(
                        media_index=item.media_index,
                        artifact=extracted,
                        status="FAILED",
                        error_code="ocr_backend_unavailable",
                    )
                )
                errors.append("ocr_backend_unavailable")
                continue
            try:
                text = self._ocr.recognize(str(safe_path)).strip()
            except Exception:
                text = ""
                errors.append("image_ocr_failed")
                ocr_records.append(
                    ImageOcrRecord(
                        media_index=item.media_index,
                        artifact=extracted,
                        status="FAILED",
                        error_code="image_ocr_failed",
                    )
                )
            else:
                status = "SUCCESS" if text else "NO_TEXT"
                ocr_records.append(
                    ImageOcrRecord(
                        media_index=item.media_index,
                        artifact=extracted,
                        status=status,
                        text=text,
                    )
                )
        errors = sorted(set(errors))
        status = (
            NoteExtractionStatus.PARTIAL if errors else NoteExtractionStatus.SUCCEEDED
        )
        sources = list(record.text_provenance)
        sources.extend(
            TextProvenance(
                source=TextProvenanceSource.IMAGE_OCR,
                text=entry.text,
                media_index=entry.media_index,
            )
            for entry in ocr_records
            if entry.text
        )
        return await self._extractions.save(
            record.model_copy(
                update={
                    "extraction_status": status,
                    "extraction_error_codes": errors,
                    "text_provenance": sources,
                    "combined_text": _combined_text(sources),
                    "image_ocr": ocr_records,
                    "media_artifacts": [entry.artifact for entry in ocr_records],
                }
            )
        )

    async def _process_video(self, record: NoteExtractionRecord):
        video = await self._videos.get(record.snapshot_id, record.feed_id)
        if video is None:
            return await _save_partial(
                self._extractions, record, [], ["video_processing_not_ready"]
            )
        artifacts = []
        if video.artifact.relative_path and video.artifact.sha256:
            artifacts.append(
                ExtractionArtifact(
                    feed_id=record.feed_id,
                    media_index=1,
                    path=video.artifact.relative_path,
                    artifact_ref=f"collection-video:{record.snapshot_id}:{record.feed_id}",
                    sha256=video.artifact.sha256,
                    size=video.artifact.size,
                )
            )
        sources = _video_provenance(record.text_provenance, video)
        errors = [video.last_error_code] if video.last_error_code else []
        status = (
            NoteExtractionStatus.SUCCEEDED
            if video.status.value == "succeeded"
            else NoteExtractionStatus.PARTIAL
        )
        if not artifacts:
            errors.append("video_artifact_not_ready")
            status = NoteExtractionStatus.PARTIAL
        return await self._extractions.save(
            record.model_copy(
                update={
                    "extraction_status": status,
                    "extraction_error_codes": sorted(set(errors)),
                    "text_provenance": sources,
                    "combined_text": _combined_text(sources),
                    "media_artifacts": artifacts,
                }
            )
        )
