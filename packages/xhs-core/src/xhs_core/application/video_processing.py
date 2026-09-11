"""TC4 视频内容处理应用服务。"""

from xhs_core.domain import (
    AudioExtractor,
    CollectionEnrichmentStatus,
    CollectionRepository,
    CollectionVideoContent,
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

from .video_processing_stages import VideoProcessingStages


class VideoProcessingService(VideoProcessingStages):
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
        audio_extractor: AudioExtractor | None = None,
    ) -> None:
        self._collections = collections
        self._enrichments = enrichments
        self._videos = videos
        self._media = media
        self._artifacts = artifacts
        self._inspector = inspector
        self._transcriber = transcriber
        self._ocr = ocr
        self._audio_extractor = audio_extractor

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
        work_started = 0
        for membership in memberships:
            if limit is not None and work_started >= limit:
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
                if current.last_error_code is not None:
                    current = await self._persist(
                        current.model_copy(update={"last_error_code": None})
                    )
                processed.append(current)
                continue
            if current and current.status in {
                VideoProcessingStatus.RUNNING,
                VideoProcessingStatus.FAILED_TERMINAL,
            }:
                processed.append(current)
                continue
            work_started += 1
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
