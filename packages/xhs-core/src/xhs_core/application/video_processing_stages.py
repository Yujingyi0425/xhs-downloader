"""视频媒体获取、分析与产物落库阶段。"""

import re
from hashlib import sha256

from loguru import logger

from xhs_core.domain import (
    CollectionVideoContent,
    VideoArtifact,
    VideoProcessingStatus,
    VideoStageStatus,
    overall_video_status,
)
from xhs_core.domain.errors import DownloadError


class VideoProcessingStages:
    """执行视频获取、分析和产物持久化阶段。"""

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
        except LookupError:
            return await self._fail_stage(
                content, "acquisition_status", "media_unavailable"
            )
        except ValueError:
            return await self._fail_stage(
                content, "acquisition_status", "media_decode_failed"
            )
        except DownloadError as error:
            error_code = _video_locator_error_code(error)
            logger.warning(
                "video media locator failed: feed_id={} error_code={}",
                feed_id,
                error_code,
            )
            return await self._fail_stage(content, "acquisition_status", error_code)
        except Exception as error:
            logger.warning(
                "video media locator failed: feed_id={} error_type={}",
                feed_id,
                type(error).__name__,
            )
            return await self._fail_stage(
                content, "acquisition_status", "media_locator_failed"
            )
        try:
            relative_path, digest, size = await self._artifacts.save(
                snapshot_id, feed_id, locator
            )
        except DownloadError as error:
            error_code = _video_download_error_code(error)
            logger.warning(
                "video media download failed: feed_id={} error_code={}",
                feed_id,
                error_code,
            )
            return await self._fail_stage(content, "acquisition_status", error_code)
        except Exception as error:
            logger.warning(
                "video media download failed: feed_id={} error_type={}",
                feed_id,
                type(error).__name__,
            )
            return await self._fail_stage(
                content, "acquisition_status", "media_download_failed"
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
        if self._inspector is not None:
            resolve_path = getattr(self._artifacts, "resolve_path", lambda value: value)
            local_path = resolve_path(relative_path)
            try:
                duration, frames = self._inspector.inspect(local_path)
                content = content.model_copy(update={"duration_seconds": duration})
            except Exception:
                return await self._fail_stage(
                    content, "acquisition_status", "media_inspection_failed"
                )
            audio_path = None
            try:
                if self._audio_extractor is not None and self._transcriber is not None:
                    audio_path = self._audio_extractor.extract(local_path)
                    transcript = self._transcriber.transcribe(audio_path)
                    content = content.model_copy(
                        update={
                            "stt_status": VideoStageStatus.SUCCEEDED,
                            "transcript": transcript,
                        }
                    )
                else:
                    content = content.model_copy(
                        update={"stt_status": VideoStageStatus.SKIPPED}
                    )
            except Exception:
                content = content.model_copy(
                    update={
                        "stt_status": VideoStageStatus.FAILED_RETRYABLE,
                        "last_error_code": "video_asr_failed",
                    }
                )
                content = await self._persist(
                    content.model_copy(
                        update={"status": VideoProcessingStatus.FAILED_RETRYABLE}
                    )
                )
            finally:
                if audio_path and self._audio_extractor is not None:
                    self._audio_extractor.cleanup(audio_path)
            try:
                if self._audio_extractor is not None and self._ocr is not None:
                    content = content.model_copy(
                        update={
                            "ocr_status": VideoStageStatus.SUCCEEDED,
                            "ocr": self._ocr.recognize(frames),
                        }
                    )
                else:
                    content = content.model_copy(
                        update={"ocr_status": VideoStageStatus.SKIPPED}
                    )
            except Exception:
                content = content.model_copy(
                    update={
                        "ocr_status": VideoStageStatus.FAILED_RETRYABLE,
                        "last_error_code": "video_keyframe_ocr_failed",
                    }
                )
                content = await self._persist(
                    content.model_copy(
                        update={"status": VideoProcessingStatus.FAILED_RETRYABLE}
                    )
                )
        else:
            content = content.model_copy(
                update={
                    "stt_status": VideoStageStatus.SKIPPED,
                    "ocr_status": VideoStageStatus.SKIPPED,
                }
            )
        if not keep_source and hasattr(self._artifacts, "discard"):
            await self._artifacts.discard(relative_path)
            content = content.model_copy(
                update={
                    "artifact": content.artifact.model_copy(
                        update={"local_video_available": False, "relative_path": None}
                    )
                }
            )
        return await self._persist(
            content.model_copy(
                update={
                    "status": overall_video_status(
                        content.acquisition_status,
                        content.stt_status,
                        content.ocr_status,
                    ),
                    "last_error_code": None,
                }
            )
        )


def _video_download_error_code(error: DownloadError) -> str:
    match = re.search(r"HTTP (\d{3})", str(error))
    return f"video_download_http_{match.group(1)}" if match else "media_download_failed"


def _video_locator_error_code(error: DownloadError) -> str:
    match = re.search(r"HTTP (\d{3})", str(error))
    return f"video_locator_http_{match.group(1)}" if match else "media_locator_failed"
