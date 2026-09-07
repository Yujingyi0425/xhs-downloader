"""浏览器详情任务的短期输入与结果内存通道。"""

import asyncio
import math
import weakref
from dataclasses import dataclass, field

from pydantic import JsonValue, SecretStr


class EphemeralSecretUnavailableError(RuntimeError):
    """临时 secret 无法注册或领取。"""


class EphemeralSecretConflictError(RuntimeError):
    """同一任务尝试替换已经登记的临时 secret。"""


@dataclass(slots=True)
class _PendingInput:
    secret: SecretStr = field(repr=False)
    expires_at: float


@dataclass(slots=True)
class _PendingResult:
    result: dict[str, JsonValue] = field(repr=False)
    expires_at: float


class BrowserTaskEphemeralInputChannel:
    """在 API 进程内传递详情任务的短期输入和结果。

    原始 secret 不进入仓储；输入领取后立即消费。成功详情结果也只在
    等待方读取期间保留，进程退出、超时或关闭都会丢弃内存状态。

    Args:
        ttl_seconds: 输入和 transient 结果的最大保留秒数。
        capacity: 同时保留的任务数量上限。
    """

    def __init__(self, *, ttl_seconds: float = 90, capacity: int = 3) -> None:
        if not math.isfinite(ttl_seconds) or ttl_seconds <= 0 or capacity <= 0:
            raise ValueError("详情临时通道参数无效")
        self._ttl_seconds = ttl_seconds
        self._capacity = capacity
        self._lock = asyncio.Lock()
        self._inputs: dict[str, _PendingInput] = {}
        self._results: dict[str, _PendingResult] = {}
        self._closed = False

    @property
    def ttl_seconds(self) -> float:
        """返回通道的有限 TTL。

        Returns:
            临时内容的最大保留秒数。
        """
        return self._ttl_seconds

    @property
    def capacity(self) -> int:
        """返回通道容量上限。

        Returns:
            同时保留的任务数量上限。
        """
        return self._capacity

    async def register(self, task_id: str, secret: str) -> bool:
        """登记一个尚未持久化任务的短期 secret。

        Args:
            task_id: 将要持久化的任务标识。
            secret: 仅存在于进程内的详情访问令牌。

        Returns:
            首次登记返回真；相同任务的相同 secret 重放返回假。

        Raises:
            EphemeralSecretConflictError: 已登记任务试图替换 secret。
            EphemeralSecretUnavailableError: 通道已关闭、过期或容量已满。
        """
        if not task_id or not secret:
            raise ValueError("详情临时输入不能为空")
        async with self._lock:
            now = asyncio.get_running_loop().time()
            self._cleanup_locked(now)
            current = self._inputs.get(task_id)
            if current is not None:
                if current.secret.get_secret_value() == secret:
                    return False
                raise EphemeralSecretConflictError("详情临时输入已经登记")
            if self._closed or len(self._inputs) + len(self._results) >= self._capacity:
                raise EphemeralSecretUnavailableError("详情临时输入通道不可用")
            self._inputs[task_id] = _PendingInput(
                secret=SecretStr(secret), expires_at=now + self._ttl_seconds
            )
            return True

    async def consume(self, task_id: str) -> str | None:
        """单次消费任务 secret。

        Args:
            task_id: 浏览器任务标识。

        Returns:
            仅首次消费得到的 secret，缺失时为空。
        """
        async with self._lock:
            self._cleanup_locked(asyncio.get_running_loop().time())
            pending = self._inputs.pop(task_id, None)
            return pending.secret.get_secret_value() if pending else None

    async def publish_result(self, task_id: str, result: dict[str, JsonValue]) -> None:
        """暂存成功详情，供唯一等待方取得。

        Args:
            task_id: 浏览器任务标识。
            result: 仅在进程内短暂传递的详情结果。
        """
        async with self._lock:
            now = asyncio.get_running_loop().time()
            self._cleanup_locked(now)
            if self._closed:
                raise EphemeralSecretUnavailableError("详情临时通道已经关闭")
            self._results[task_id] = _PendingResult(
                result=dict(result), expires_at=now + self._ttl_seconds
            )

    async def consume_result(self, task_id: str) -> dict[str, JsonValue] | None:
        """单次消费 transient 成功详情。

        Args:
            task_id: 浏览器任务标识。

        Returns:
            仅首次消费得到的详情结果，缺失时为空。
        """
        async with self._lock:
            self._cleanup_locked(asyncio.get_running_loop().time())
            pending = self._results.pop(task_id, None)
            return dict(pending.result) if pending else None

    async def discard(self, task_id: str) -> None:
        """撤销任务关联的 secret 和 transient 结果。

        Args:
            task_id: 浏览器任务标识。
        """
        async with self._lock:
            self._inputs.pop(task_id, None)
            self._results.pop(task_id, None)

    async def close(self) -> None:
        """关闭通道并清空所有短期内容。"""
        async with self._lock:
            self._closed = True
            self._inputs.clear()
            self._results.clear()

    def _cleanup_locked(self, now: float) -> None:
        self._inputs = {
            task_id: item
            for task_id, item in self._inputs.items()
            if item.expires_at > now
        }
        self._results = {
            task_id: item
            for task_id, item in self._results.items()
            if item.expires_at > now
        }


DEFAULT_BROWSER_TASK_EPHEMERAL_TTL_SECONDS = 90
DEFAULT_BROWSER_TASK_EPHEMERAL_CHANNEL = BrowserTaskEphemeralInputChannel(
    ttl_seconds=DEFAULT_BROWSER_TASK_EPHEMERAL_TTL_SECONDS,
)

_REPOSITORY_CHANNELS: weakref.WeakKeyDictionary[
    object, BrowserTaskEphemeralInputChannel
] = weakref.WeakKeyDictionary()


def ephemeral_channel_for_repository(
    repository: object,
) -> BrowserTaskEphemeralInputChannel:
    """为同一仓储实例提供共享且隔离的默认临时通道。

    Args:
        repository: 作为通道隔离边界的仓储实例。

    Returns:
        该仓储实例绑定的临时通道。
    """
    channel = _REPOSITORY_CHANNELS.get(repository)
    if channel is None:
        channel = BrowserTaskEphemeralInputChannel(
            ttl_seconds=DEFAULT_BROWSER_TASK_EPHEMERAL_TTL_SECONDS
        )
        _REPOSITORY_CHANNELS[repository] = channel
    return channel
