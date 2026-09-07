"""TC4 视频内容处理应用服务。"""

from hashlib import sha256

from xhs_core.domain import (
    CollectionEnrichmentStatus,
    CollectionRepository,
    CollectionVideoContent,
    VideoArtifact,
    VideoArtifactStore,
    VideoContentRepository,
    VideoInspector,
    VideoMediaAcquirer,
    VideoOcr,
    VideoProcessingStatus,
    VideoStageStatus,
    VideoTranscriber,
    overall_video_status,
)
from xhs_core.domain.collection_enrichment_ports import CollectionEnrichmentRepository


class VideoProcessingService:
    """按收藏顺序串行处理已成功的 video detail。"""

    def __init__(
        self,
        collections: CollectionRepository,
        enrichments: CollectionEnrichmentRepository,
        videos: VideoContentRepository,
        media: VideoMediaAcquirer,
        artifacts: VideoArtifactStore,
        inspector: VideoInspector | None = None,
        transcriber: VideoTranscriber | None = None,
        ocr: VideoOcr | None = None,
    ) -> None:
        self._collections = collections
        self._enrichments = enrichments
        self._videos = videos
        self._media = media
        self._artifacts = artifacts
        self._inspector = inspector
        self._transcriber = transcriber
        self._ocr = ocr

    async def process_snapshot(
        self, snapshot_id: str, limit: int | None = None, keep_source: bool = True
    ) -> list[CollectionVideoContent]:
        """处理 eligible video，单条失败不终止后续条目。

        Args:
            snapshot_id: 收藏快照标识。
            limit: 本轮最多处理的 eligible video 数量。
            keep_source: 是否保留本地 source.mp4。

        Returns:
            按快照顺序返回本轮处理结果。
        """
        recover_running = getattr(self._videos, "recover_running", None)
        if recover_running is not None:
            await recover_running(snapshot_id)
        memberships = await self._collections.list_snapshot_items(snapshot_id)
        processed: list[CollectionVideoContent] = []
        for membership in memberships:
            if limit is not None and len(processed) >= limit:
                break
            enrichment = await self._enrichments.get_enrichment(
                snapshot_id, membership.feed_id
            )
            if (
                not enrichment
                or enrichment.status is not CollectionEnrichmentStatus.SUCCEEDED
            ):
                continue
            if not enrichment.detail or enrichment.detail.note_type != "video":
                continue
            current = await self._videos.get(snapshot_id, membership.feed_id)
            if current and current.status is VideoProcessingStatus.SUCCEEDED:
                processed.append(current)
                continue
            if current and current.status in {
                VideoProcessingStatus.RUNNING,
                VideoProcessingStatus.FAILED_TERMINAL,
            }:
                processed.append(current)
                continue
            result = await self._process_one(
                snapshot_id, membership.feed_id, current, keep_source
            )
            processed.append(result)
        return processed

    async def list_snapshot(self, snapshot_id: str) -> list[CollectionVideoContent]:
        """读取一个快照的视频处理结果。

        Args:
            snapshot_id: 收藏快照标识。

        Returns:
            按仓储顺序排列的视频结果。
        """
        return await self._videos.list_snapshot(snapshot_id)

    async def _process_one(
        self,
        snapshot_id: str,
        feed_id: str,
        current: CollectionVideoContent | None,
        keep_source: bool,
    ):
        content = current or CollectionVideoContent(
            snapshot_id=snapshot_id, feed_id=feed_id
        )
        content = content.model_copy(
            update={
                "status": VideoProcessingStatus.RUNNING,
                "attempt_count": content.attempt_count + 1,
            }
        )
        save_if_status = getattr(self._videos, "save_if_status", None)
        if save_if_status is not None:
            claimed = await save_if_status(content, current.status if current else None)
            if not claimed:
                return current or content
        else:
            await self._videos.save(content)
        request_id = sha256(
            f"{snapshot_id}\0{feed_id}\01\0{content.attempt_count}".encode()
        ).hexdigest()
        try:
            access = await self._collections.get_feed_access_context(feed_id)
            if access is None:
                return await self._fail_stage(
                    content, "acquisition_status", "access_context_missing"
                )
            locator = await self._media.acquire(
                feed_id, access.latest_xsec_token.get_secret_value(), request_id
            )
            if locator.feed_id != feed_id:
                return await self._fail_stage(
                    content, "acquisition_status", "media_identity_mismatch"
                )
            relative_path, digest, size = await self._artifacts.save(
                snapshot_id, feed_id, locator
            )
            content = content.model_copy(
                update={
                    "acquisition_status": VideoStageStatus.SUCCEEDED,
                    "artifact": VideoArtifact(
                        local_video_available=True,
                        relative_path=relative_path,
                        sha256=digest,
                        size=size,
                    ),
                }
            )
        except LookupError:
            return await self._fail_stage(
                content, "acquisition_status", "media_unavailable"
            )
        except ValueError:
            return await self._fail_stage(
                content, "acquisition_status", "media_decode_failed"
            )
        except Exception:
            return await self._fail_stage(
                content, "acquisition_status", "media_download_failed"
            )
        if not keep_source and hasattr(self._artifacts, "discard"):
            await self._artifacts.discard(relative_path)
            content = content.model_copy(
                update={
                    "artifact": content.artifact.model_copy(
                        update={
                            "local_video_available": False,
                            "relative_path": None,
                        }
                    )
                }
            )
        return await self._persist(
            content.model_copy(
                update={
                    "status": VideoProcessingStatus.SUCCEEDED,
                    "stt_status": VideoStageStatus.SKIPPED,
                    "ocr_status": VideoStageStatus.SKIPPED,
                }
            )
        )

    async def _fail_stage(self, content: CollectionVideoContent, stage: str, code: str):
        """记录可重试阶段失败并保留已完成的部分结果。"""
        content = content.model_copy(update={stage: VideoStageStatus.FAILED_RETRYABLE})
        status = overall_video_status(
            content.acquisition_status, content.stt_status, content.ocr_status
        )
        return await self._persist(
            content.model_copy(update={"status": status, "last_error_code": code})
        )

    async def _persist(self, content: CollectionVideoContent):
        """以 attempt CAS 保存结果，兼容合成用的旧式 fake repository。"""
        save_if_attempt = getattr(self._videos, "save_if_attempt", None)
        if save_if_attempt is not None:
            accepted = await save_if_attempt(content, content.attempt_count)
            if not accepted:
                current = await self._videos.get(
                    content.snapshot_id, content.feed_id, content.processing_version
                )
                return current or content.model_copy(
                    update={"status": VideoProcessingStatus.FAILED_RETRYABLE}
                )
        else:
            await self._videos.save(content)
        return content
