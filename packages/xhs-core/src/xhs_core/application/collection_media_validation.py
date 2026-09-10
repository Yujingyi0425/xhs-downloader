"""收藏夹媒体输入的 URL 与扩展名安全校验。"""

from urllib.parse import urlsplit


def validate_media_url(value: str) -> None:
    """拒绝空值和非 HTTP(S) 媒体地址。

    Args:
        value: 待验证的媒体地址。
    """
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("media URL is invalid")


def safe_suffix(value: str) -> str:
    """把缺失扩展名退化为 auto，并拒绝路径片段。

    Args:
        value: 媒体元数据提供的扩展名。

    Returns:
        可安全用于文件名的扩展名。
    """
    candidate = value.strip().lower() or "auto"
    if not candidate.isalnum() or len(candidate) > 10:
        raise ValueError("media suffix is invalid")
    return candidate
