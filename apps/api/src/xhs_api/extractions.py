"""原始笔记抽取的本机管理 API。"""

from fastapi import APIRouter, HTTPException, Request
from xhs_core.domain import NoteExtractionRecord

from .collection_models import (
    NoteExtractionProcessAcceptedResponse,
    NoteExtractionProcessRequest,
)
from .settings import allow_loopback_settings


def create_extraction_router(service, repository, coordinator) -> APIRouter:
    """创建抽取触发和读回路由。

    Args:
        service: 原始笔记抽取服务。
        repository: 收藏快照仓储。
        coordinator: 后台任务协调器。

    Returns:
        配置完成的 FastAPI 路由。
    """
    router = APIRouter(prefix="/xhs/collections", tags=["原始笔记抽取"])

    @router.post(
        "/snapshots/{snapshot_id}/extractions/process",
        response_model=NoteExtractionProcessAcceptedResponse,
        status_code=202,
    )
    async def process_extractions(
        snapshot_id: str,
        payload: NoteExtractionProcessRequest,
        request: Request,
    ) -> NoteExtractionProcessAcceptedResponse:
        """启动一个有界的快照抽取任务。

        Args:
            snapshot_id: 收藏快照标识。
            payload: 抽取选项。
            request: 当前 HTTP 请求。

        Returns:
            后台任务接收状态。
        """
        _require_loopback(request)
        if await repository.get_snapshot(snapshot_id) is None:
            raise HTTPException(status_code=404, detail="收藏夹快照不存在")
        started = coordinator.start(
            f"extraction:{snapshot_id}",
            lambda: service.process_snapshot(
                snapshot_id, payload.limit, payload.retry_failed
            ),
        )
        return NoteExtractionProcessAcceptedResponse(
            snapshot_id=snapshot_id,
            job_status="started" if started else "already_running",
        )

    @router.get(
        "/snapshots/{snapshot_id}/extractions",
        response_model=list[NoteExtractionRecord],
    )
    async def read_extractions(snapshot_id: str, request: Request):
        """读取快照的完整抽取记录。

        Args:
            snapshot_id: 收藏快照标识。
            request: 当前 HTTP 请求。

        Returns:
            按收藏顺序排列的抽取记录。
        """
        _require_loopback(request)
        if await repository.get_snapshot(snapshot_id) is None:
            raise HTTPException(status_code=404, detail="收藏夹快照不存在")
        return await service.list_snapshot(snapshot_id)

    return router


def _require_loopback(request: Request) -> None:
    """只允许本机管理请求。"""
    if not allow_loopback_settings(request):
        raise HTTPException(status_code=403, detail="原始笔记抽取仅允许从本机访问")
