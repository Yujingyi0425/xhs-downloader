"""收藏夹视频处理的本机管理 API。"""

from fastapi import APIRouter, HTTPException, Request
from xhs_core.application import (
    CollectionEnrichmentJobCoordinator,
    VideoProcessingService,
)

from .collection_models import (
    VideoContentResponse,
    VideoProcessAcceptedResponse,
    VideoProcessRequest,
)
from .settings import allow_loopback_settings


def create_video_router(
    service: VideoProcessingService,
    repository,
    coordinator: CollectionEnrichmentJobCoordinator,
) -> APIRouter:
    """创建只允许本机访问的视频处理路由。

    Args:
        service: 视频处理应用服务。
        repository: 收藏快照读取仓储。
        coordinator: 进程内任务协调器。

    Returns:
        可挂载的 FastAPI 路由。
    """
    router = APIRouter(prefix="/xhs/collections", tags=["收藏视频处理"])

    @router.post(
        "/snapshots/{snapshot_id}/videos/process",
        response_model=VideoProcessAcceptedResponse,
        status_code=202,
    )
    async def process_videos(
        snapshot_id: str,
        payload: VideoProcessRequest,
        request: Request,
    ) -> VideoProcessAcceptedResponse:
        _require_loopback(request)
        if await repository.get_snapshot(snapshot_id) is None:
            raise HTTPException(status_code=404, detail="收藏夹快照不存在")
        started = coordinator.start(
            f"video:{snapshot_id}",
            lambda: service.process_snapshot(
                snapshot_id, payload.limit, payload.keep_source
            ),
        )
        return VideoProcessAcceptedResponse(
            snapshot_id=snapshot_id,
            job_status="started" if started else "already_running",
        )

    @router.get(
        "/snapshots/{snapshot_id}/videos",
        response_model=list[VideoContentResponse],
    )
    async def read_videos(
        snapshot_id: str, request: Request
    ) -> list[VideoContentResponse]:
        _require_loopback(request)
        if await repository.get_snapshot(snapshot_id) is None:
            raise HTTPException(status_code=404, detail="收藏夹快照不存在")
        contents = {
            item.feed_id: item for item in await service.list_snapshot(snapshot_id)
        }
        return [
            VideoContentResponse(
                content=contents[item.feed_id], source_order=item.source_order
            )
            for item in await repository.list_snapshot_items(snapshot_id)
            if item.feed_id in contents
        ]

    return router


def _require_loopback(request: Request) -> None:
    """拒绝非本机管理请求。 Args: request: 当前 HTTP 请求。"""
    if not allow_loopback_settings(request):
        raise HTTPException(status_code=403, detail="视频处理仅允许从本机访问")
