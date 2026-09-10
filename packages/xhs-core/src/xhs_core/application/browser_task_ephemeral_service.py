"""浏览器详情任务的临时 secret 提交与取消行为。"""

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import JsonValue

from xhs_core.domain import (
    XSEC_TOKEN_TASK_KINDS,
    BrowserDriver,
    BrowserTask,
    BrowserTaskError,
    BrowserTaskKind,
    BrowserTaskStatus,
    browser_driver_supports,
)
from xhs_core.domain.browser_requests import validate_browser_task_payload

from .browser_task_ephemeral import (
    EphemeralSecretConflictError,
    EphemeralSecretUnavailableError,
)


class BrowserTaskEphemeralServiceMixin:
    """为 BrowserTaskService 提供不落盘的详情 secret 交接。"""

    async def submit_ephemeral_feed_detail(
        self,
        payload: dict[str, JsonValue],
        request_id: str | None = None,
        target_driver: BrowserDriver = BrowserDriver.EXTENSION,
        _kind: BrowserTaskKind = BrowserTaskKind.GET_FEED_DETAIL,
    ) -> BrowserTask:
        """提交 token 不落盘的详情任务。

        Args:
            payload: 包含完整详情输入的结构化 payload。
            request_id: 可选的调用方幂等请求标识。
            target_driver: 提交时固定的浏览器执行驱动。
            _kind: 详情或媒体任务类型。

        Returns:
            持久化 payload 不含 token 的浏览器任务。
        """
        return await self._submit_ephemeral_xsec_task(
            payload, request_id, target_driver, _kind
        )

    async def _submit_ephemeral_xsec_task(
        self,
        payload: dict[str, JsonValue],
        request_id: str | None,
        target_driver: BrowserDriver,
        _kind: BrowserTaskKind,
    ) -> BrowserTask:
        """提交任意含 xsec token 的任务并隔离其输入。

        Args:
            payload: 包含完整详情输入的结构化 payload。
            request_id: 可选的调用方幂等请求标识。
            target_driver: 提交时固定的浏览器执行驱动。

        Returns:
            持久化 payload 不含 token 的浏览器任务。

        Raises:
            BrowserTaskError: 输入、驱动或幂等请求不合法。
        """
        if not browser_driver_supports(target_driver, _kind):
            raise BrowserTaskError("当前浏览器执行器尚未支持该任务")
        full_payload = validate_browser_task_payload(_kind, payload)
        token = full_payload.get("xsec_token")
        if not isinstance(token, str) or not token:
            raise BrowserTaskError("任务缺少临时访问令牌")
        persisted_payload = dict(full_payload)
        persisted_payload.pop("xsec_token", None)
        async with self._submit_lock:
            if request_id:
                existing = await self._repository.get_by_request_id(request_id)
                if existing:
                    if (
                        existing.kind is not _kind
                        or existing.payload != persisted_payload
                        or existing.target_driver is not target_driver
                    ):
                        raise BrowserTaskError("请求标识已被另一项浏览器任务使用")
                    if existing.status is BrowserTaskStatus.QUEUED:
                        try:
                            await self._ephemeral_channel.register(
                                existing.task_id, token
                            )
                        except EphemeralSecretConflictError as error:
                            raise BrowserTaskError(
                                "请求标识对应的详情 secret 不可替换"
                            ) from error
                        except EphemeralSecretUnavailableError as error:
                            raise BrowserTaskError(
                                "详情任务临时访问上下文不可用"
                            ) from error
                    return existing
            now = datetime.now(UTC)
            task = BrowserTask(
                task_id=uuid4().hex,
                request_id=request_id,
                kind=_kind,
                payload=persisted_payload,
                target_driver=target_driver,
                created_at=now,
                updated_at=now,
            )
            try:
                await self._ephemeral_channel.register(task.task_id, token)
                await self._repository.save(task)
            except (
                EphemeralSecretConflictError,
                EphemeralSecretUnavailableError,
            ) as error:
                await self._ephemeral_channel.discard(task.task_id)
                raise BrowserTaskError("详情任务临时访问上下文不可用") from error
            except Exception:
                await self._ephemeral_channel.discard(task.task_id)
                raise
            if target_driver is BrowserDriver.EXTENSION:
                self._claim_waiter.notify()
            return task

    async def cancel_before_running(
        self,
        task_id: str,
        message: str = "等待浏览器执行超时，任务已取消",
    ) -> BrowserTask:
        """在页面执行前原子取消任务并清理临时详情 secret。

        Args:
            task_id: 任务唯一标识。
            message: 不包含敏感数据的取消原因。

        Returns:
            取消后的任务，或已经开始、完成的最新任务。

        Raises:
            BrowserTaskError: 任务不存在。
        """
        while True:
            task = await self.require(task_id)
            if task.status not in {
                BrowserTaskStatus.QUEUED,
                BrowserTaskStatus.CLAIMED,
            }:
                return task
            canceled = task.model_copy(
                update={
                    "status": BrowserTaskStatus.FAILED,
                    "executor_id": None,
                    "extension_id": None,
                    "lease_expires_at": None,
                    "message": message[:1000],
                    "updated_at": datetime.now(UTC),
                }
            )
            if await self._repository.save_if_status(
                canceled,
                task.status,
                clear_lease=True,
            ):
                if (
                    task.kind in XSEC_TOKEN_TASK_KINDS
                ):
                    await self._ephemeral_channel.discard(task.task_id)
                return canceled

    async def submit_ephemeral_feed_media(
        self,
        payload: dict[str, JsonValue],
        request_id: str | None = None,
        target_driver: BrowserDriver = BrowserDriver.EXTENSION,
    ) -> BrowserTask:
        """提交 token 不落盘的媒体读取任务。

        Args:
            payload: 含临时令牌的媒体输入。
            request_id: 可选幂等标识。
            target_driver: 目标浏览器驱动。

        Returns:
            持久化 payload 不含 token 的浏览器任务。
        """
        return await self.submit_ephemeral_feed_detail(
            payload, request_id, target_driver, BrowserTaskKind.GET_FEED_MEDIA
        )
