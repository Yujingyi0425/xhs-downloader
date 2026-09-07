"""共享的断点流式下载与安全原子落盘 primitive。"""

import os
from asyncio import sleep, to_thread
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from aiofiles import open as async_open
from xhs_core.domain.errors import DownloadError, InvalidPartialContentError


@dataclass(frozen=True)
class StreamDownloadResult:
    """一次成功流式下载的安全结果。"""

    target: Path
    headers: Mapping[str, str]
    sha256: str
    size: int


async def stream_to_atomic_file(
    gateway,
    url: str,
    part: Path,
    marker: Path,
    target: Path | Callable[[Mapping[str, str]], Path],
    *,
    chunk_size: int = 1024 * 1024,
    on_chunk: Callable[[int], Awaitable[None]] | None = None,
    cleanup_on_error: bool = False,
) -> StreamDownloadResult:
    """断点流式写入并原子替换目标文件。

    Args:
        gateway: 提供带可选 Range 请求头的异步流端口。
        url: 短期媒体地址，仅在本次下载中使用。
        part: 可续传的临时文件路径。
        marker: 与临时文件配对的短期 URL 指纹路径。
        target: 固定目标路径或根据响应头生成目标路径的函数。
        chunk_size: 每次读取的最大字节数。
        on_chunk: 每写入一块后调用的异步进度回调。
        cleanup_on_error: 失败时是否清理临时文件和 marker。

    Returns:
        已原子完成文件的路径、响应头、SHA-256 和字节数。

    Raises:
        DownloadError: 响应为空或下载失败。
        InvalidPartialContentError: 远端拒绝续传位置。
    """
    await to_thread(part.parent.mkdir, parents=True, exist_ok=True)
    fingerprint = sha256(url.encode("utf-8")).hexdigest()
    part_exists = await to_thread(part.exists)
    marker_matches = await to_thread(_marker_matches, marker, fingerprint)
    if part_exists and not marker_matches:
        await to_thread(part.unlink, True)
        part_exists = False
    await to_thread(marker.write_text, fingerprint, encoding="utf-8")
    resume_at = await to_thread(_path_size, part) if part_exists else 0
    headers = {"Range": f"bytes={resume_at}-"} if resume_at else None
    try:
        async with gateway.stream(url, headers) as response:
            response_headers = response.headers
            destination = target(response_headers) if callable(target) else target
            mode = "ab" if resume_at and response.status_code == 206 else "wb"
            async with async_open(part, mode) as output:
                async for chunk in response.aiter_bytes(chunk_size):
                    await output.write(chunk)
                    if on_chunk is not None:
                        await on_chunk(len(chunk))
        if not await to_thread(part.exists) or await to_thread(_path_size, part) == 0:
            raise DownloadError("下载结果为空")
        await to_thread(destination.parent.mkdir, parents=True, exist_ok=True)
        await to_thread(os.replace, part, destination)
        await to_thread(marker.unlink, True)
        digest, size = await to_thread(_hash_and_size, destination)
        return StreamDownloadResult(destination, response_headers, digest, size)
    except InvalidPartialContentError:
        await to_thread(part.unlink, True)
        await to_thread(marker.unlink, True)
        raise
    except Exception:
        if cleanup_on_error:
            await to_thread(part.unlink, True)
            await to_thread(marker.unlink, True)
        raise


async def retry_stream_to_atomic_file(
    gateway,
    url: str,
    part: Path,
    marker: Path,
    target: Path | Callable[[Mapping[str, str]], Path],
    *,
    max_attempts: int,
    chunk_size: int = 1024 * 1024,
    on_chunk: Callable[[int], Awaitable[None]] | None = None,
    cleanup_on_exhaustion: bool = False,
) -> StreamDownloadResult:
    """以有限次数重试共享流式下载 primitive。

    Args:
        gateway: 提供带可选 Range 请求头的异步流端口。
        url: 短期媒体地址，仅在本次下载中使用。
        part: 可续传的临时文件路径。
        marker: 与临时文件配对的短期 URL 指纹路径。
        target: 固定目标路径或根据响应头生成目标路径的函数。
        max_attempts: 包含首次尝试在内的最大尝试次数。
        chunk_size: 每次读取的最大字节数。
        on_chunk: 每写入一块后调用的异步进度回调。
        cleanup_on_exhaustion: 耗尽后是否清理可续传状态。

    Returns:
        共享下载 primitive 的成功结果。

    Raises:
        DownloadError: 可重试错误耗尽。
        InvalidPartialContentError: 续传位置被远端拒绝，不重试。
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")
    for attempt in range(max_attempts):
        try:
            return await stream_to_atomic_file(
                gateway,
                url,
                part,
                marker,
                target,
                chunk_size=chunk_size,
                on_chunk=on_chunk,
            )
        except InvalidPartialContentError:
            raise
        except (DownloadError, OSError, TimeoutError):
            if attempt + 1 >= max_attempts:
                if cleanup_on_exhaustion:
                    await to_thread(part.unlink, True)
                    await to_thread(marker.unlink, True)
                raise
            await sleep(min(2**attempt, 4))


def _hash_and_size(path: Path) -> tuple[str, int]:
    digest = sha256()
    size = 0
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _marker_matches(marker: Path, fingerprint: str) -> bool:
    return marker.exists() and marker.read_text(encoding="utf-8") == fingerprint


def _path_size(path: Path) -> int:
    return path.stat().st_size
