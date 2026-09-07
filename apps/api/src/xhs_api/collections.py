"""本机扩展收藏夹快照导入与读取 API。"""

import logging

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import ValidationError
from xhs_core.application import CollectionImportService, ExtensionCredentialService
from xhs_core.domain import (
    CollectionIdempotencyConflictError,
    CollectionImportCommand,
    CollectionImportItem,
    CollectionRepository,
    CollectionSnapshot,
)

from .collection_models import (
    CollectionDiffResponse,
    CollectionImportItemRequest,
    CollectionImportRequest,
    CollectionSnapshotDetailResponse,
    CollectionSnapshotItemResponse,
    CollectionSnapshotListItem,
    CollectionSnapshotListResponse,
    CollectionSnapshotResponse,
)
from .extension_access import require_extension, require_extension_origin
from .settings import allow_loopback_settings

_LOGGER = logging.getLogger(__name__)


def create_collection_router(
    importer: CollectionImportService,
    repository: CollectionRepository,
    credentials: ExtensionCredentialService,
) -> APIRouter:
    """创建收藏夹快照 API。

    Args:
        importer: 收藏快照导入应用服务。
        repository: 收藏快照读取仓储。
        credentials: 扩展能力凭据服务。

    Returns:
        可挂载到主应用的收藏夹路由。
    """
    router = APIRouter(prefix="/collections", tags=["收藏夹"])

    @router.post(
        "/{source_type}/{board_id}/imports",
        response_model=CollectionSnapshotResponse,
        status_code=201,
    )
    async def import_collection(
        source_type: str,
        board_id: str,
        payload: CollectionImportRequest,
        request: Request,
    ) -> CollectionSnapshotResponse:
        await require_extension(request, credentials)
        require_extension_origin(request, request.headers.get("x-extension-id", ""))
        command = _command_from_request(source_type, board_id, payload)
        try:
            snapshot, diff = await importer.import_snapshot(command)
        except CollectionIdempotencyConflictError as error:
            raise HTTPException(
                status_code=409,
                detail="request_id 幂等冲突",
            ) from error
        except Exception as error:
            _LOGGER.error("collection import failed")
            raise HTTPException(status_code=500, detail="收藏夹导入失败") from error
        return _snapshot_response(snapshot, diff)

    @router.get(
        "/{source_type}/{board_id}/latest",
        response_model=CollectionSnapshotDetailResponse,
    )
    async def get_latest_collection(
        source_type: str, board_id: str, request: Request
    ) -> CollectionSnapshotDetailResponse:
        _require_management_read(request)
        snapshot = await repository.get_latest_snapshot(source_type, board_id)
        if not snapshot:
            raise HTTPException(status_code=404, detail="收藏夹快照不存在")
        return await _detail_response(repository, snapshot)

    @router.get(
        "/{source_type}/{board_id}/snapshots",
        response_model=CollectionSnapshotListResponse,
    )
    async def list_collection_snapshots(
        source_type: str,
        board_id: str,
        request: Request,
        limit: int = Query(default=100, ge=1, le=500),
    ) -> CollectionSnapshotListResponse:
        _require_management_read(request)
        snapshots = await repository.list_snapshots(source_type, board_id, limit)
        return CollectionSnapshotListResponse(
            items=[_snapshot_list_item(snapshot) for snapshot in snapshots]
        )

    @router.get(
        "/{source_type}/{board_id}/snapshots/{snapshot_id}",
        response_model=CollectionSnapshotDetailResponse,
    )
    async def get_collection_snapshot(
        source_type: str, board_id: str, snapshot_id: str, request: Request
    ) -> CollectionSnapshotDetailResponse:
        _require_management_read(request)
        snapshot = await repository.get_snapshot(snapshot_id)
        if not snapshot or (
            snapshot.source_type != source_type or snapshot.board_id != board_id
        ):
            raise HTTPException(status_code=404, detail="收藏夹快照不存在")
        return await _detail_response(repository, snapshot)

    @router.get(
        "/{source_type}/{board_id}/snapshots/{snapshot_id}/items",
        response_model=list[CollectionSnapshotItemResponse],
    )
    async def list_collection_snapshot_items(
        source_type: str, board_id: str, snapshot_id: str, request: Request
    ) -> list[CollectionSnapshotItemResponse]:
        _require_management_read(request)
        snapshot = await repository.get_snapshot(snapshot_id)
        if not snapshot or (
            snapshot.source_type != source_type or snapshot.board_id != board_id
        ):
            raise HTTPException(status_code=404, detail="收藏夹快照不存在")
        items = await repository.list_snapshot_items(snapshot_id)
        return [
            CollectionSnapshotItemResponse(
                feed_id=item.feed_id, source_order=item.source_order
            )
            for item in items
        ]

    return router


def _command_from_request(
    source_type: str,
    board_id: str,
    payload: CollectionImportRequest,
) -> CollectionImportCommand:
    """把敏感 HTTP 输入转换为领域命令，并统一脱敏验证失败。"""
    try:
        return CollectionImportCommand(
            request_id=payload.request_id,
            source_type=source_type,
            board_id=board_id,
            items=[_domain_item(item) for item in payload.items],
        )
    except ValidationError as error:
        raise HTTPException(status_code=422, detail="收藏夹输入无效") from error


def _domain_item(item: CollectionImportItemRequest) -> CollectionImportItem:
    return CollectionImportItem(
        feed_id=item.feed_id,
        xsec_token=item.xsec_token,
        source_order=item.source_order,
    )


async def _detail_response(
    repository: CollectionRepository, snapshot: CollectionSnapshot
) -> CollectionSnapshotDetailResponse:
    items = await repository.list_snapshot_items(snapshot.snapshot_id)
    diff = await repository.get_snapshot_diff(snapshot.snapshot_id)
    return CollectionSnapshotDetailResponse(
        **_snapshot_response(snapshot, diff).model_dump(),
        items=[
            CollectionSnapshotItemResponse(
                feed_id=item.feed_id, source_order=item.source_order
            )
            for item in items
        ],
    )


def _snapshot_response(
    snapshot: CollectionSnapshot, diff
) -> CollectionSnapshotResponse:
    return CollectionSnapshotResponse(
        snapshot_id=snapshot.snapshot_id,
        source_type=snapshot.source_type,
        board_id=snapshot.board_id,
        board_revision=snapshot.board_revision,
        request_id=snapshot.request_id,
        captured_at=snapshot.captured_at,
        item_count=snapshot.item_count,
        fingerprint=snapshot.fingerprint,
        status=snapshot.status,
        diff=CollectionDiffResponse(
            added=diff.added,
            removed=diff.removed,
            retained=diff.retained,
        ),
    )


def _snapshot_list_item(snapshot: CollectionSnapshot) -> CollectionSnapshotListItem:
    return CollectionSnapshotListItem(
        snapshot_id=snapshot.snapshot_id,
        board_revision=snapshot.board_revision,
        captured_at=snapshot.captured_at,
        item_count=snapshot.item_count,
        fingerprint=snapshot.fingerprint,
        status=snapshot.status,
    )


def _require_management_read(request: Request) -> None:
    if not allow_loopback_settings(request):
        raise HTTPException(status_code=403, detail="收藏夹读取仅允许从本机访问")
