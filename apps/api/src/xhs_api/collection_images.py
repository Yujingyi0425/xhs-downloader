"""收藏夹图片生产 API。"""

from fastapi import APIRouter, HTTPException, Request
from xhs_core.application import (
    CollectionImageProductionService,
    CollectionMediaService,
    ExtensionCredentialService,
)

from .collection_models import (
    CollectionImageBatchResponse,
    CollectionImageItemResponse,
    CollectionImageProcessRequest,
)
from .extension_access import require_extension


def install_collection_image_service(app, dependencies, downloader) -> None:
    """在 API 生命周期中安装收藏图片生产服务。

    Args:
        app: FastAPI 应用实例。
        dependencies: API 组合根依赖。
        downloader: 已进入生命周期的共享下载服务。
    """
    repository = getattr(dependencies, "collection_repository", None)
    enrichment = getattr(dependencies, "collection_enrichment", None)
    media_repository = getattr(dependencies, "collection_media_repository", None)
    if repository is None or enrichment is None or media_repository is None:
        return
    app.state.collection_repository = repository
    app.state.collection_images = CollectionImageProductionService(
        repository,
        enrichment,
        CollectionMediaService(downloader, media_repository),
    )


def create_collection_image_router(
    credentials: ExtensionCredentialService,
) -> APIRouter:
    """创建受扩展凭据保护的收藏图片生产路由。

    Args:
        credentials: 用于验证扩展调用者的凭据服务。

    Returns:
        可挂载到主应用的图片生产路由。
    """
    router = APIRouter(prefix="/xhs/collections", tags=["收藏图片生产"])

    @router.post(
        "/snapshots/{snapshot_id}/process-images",
        response_model=CollectionImageBatchResponse,
    )
    async def process_images(
        snapshot_id: str,
        payload: CollectionImageProcessRequest,
        request: Request,
    ) -> CollectionImageBatchResponse:
        await require_extension(request, credentials)
        repository = request.app.state.collection_repository
        service = request.app.state.collection_images
        await _require_snapshot_board(repository, snapshot_id, payload.board_id)
        try:
            result = await service.process_snapshot(
                snapshot_id, retry_failed=payload.retry_failed
            )
        except LookupError as error:
            raise HTTPException(status_code=404, detail="收藏夹快照不存在") from error
        return _response(result)

    @router.get(
        "/snapshots/{snapshot_id}/image-media",
        response_model=CollectionImageBatchResponse,
    )
    async def read_images(snapshot_id: str, request: Request):
        await require_extension(request, credentials)
        service = request.app.state.collection_images
        try:
            return _response(await service.read_snapshot(snapshot_id))
        except LookupError as error:
            raise HTTPException(status_code=404, detail="收藏夹快照不存在") from error

    return router


async def _require_snapshot_board(
    repository, snapshot_id: str, board_id: str
) -> None:
    snapshot = await repository.get_snapshot(snapshot_id)
    if snapshot is None or snapshot.board_id != board_id:
        raise HTTPException(status_code=404, detail="收藏夹快照不存在")


def _response(result) -> CollectionImageBatchResponse:
    return CollectionImageBatchResponse(
        snapshot_id=result.snapshot_id,
        status=result.status,
        items=[CollectionImageItemResponse(**item.__dict__) for item in result.items],
    )
