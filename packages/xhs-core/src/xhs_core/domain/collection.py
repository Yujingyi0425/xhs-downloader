"""收藏夹快照领域模型与纯校验规则。"""

from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from json import dumps

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class CollectionStatus(StrEnum):
    """TC2 支持的收藏快照状态。"""

    CAPTURED = "captured"


class CollectionImportItem(BaseModel):
    """一次导入中的敏感条目。"""

    model_config = ConfigDict(extra="forbid")

    feed_id: str = Field(min_length=1, max_length=256)
    xsec_token: SecretStr = Field(min_length=1, repr=False)
    source_order: int = Field(ge=0)

    @field_validator("xsec_token")
    @classmethod
    def validate_token(cls, value: SecretStr) -> SecretStr:
        """拒绝空白 token，并保留原始 token 供内部详情请求使用。

        Args:
            value: 待校验的敏感 token。

        Returns:
            通过校验的 token。
        """
        if not value.get_secret_value().strip():
            raise ValueError("xsec_token must not be empty or whitespace")
        return value


class CollectionImportCommand(BaseModel):
    """应用层收藏快照导入命令；board 身份由上层 path 传入。"""

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1, max_length=128)
    source_type: str = Field(min_length=1, max_length=64)
    board_id: str = Field(min_length=1, max_length=256)
    items: list[CollectionImportItem] = Field(default_factory=list, max_length=500)

    @field_validator("items")
    @classmethod
    def validate_orders(
        cls, items: list[CollectionImportItem]
    ) -> list[CollectionImportItem]:
        """要求 source_order 恰好覆盖 0 到 N-1，且 feed 不重复。

        Args:
            items: 待校验的收藏条目。

        Returns:
            原顺序的合法条目列表。
        """
        orders = [item.source_order for item in items]
        feeds = [item.feed_id for item in items]
        expected = list(range(len(items)))
        if orders != expected or len(set(orders)) != len(orders):
            raise ValueError("source_order must be exactly 0..N-1")
        if len(set(feeds)) != len(feeds):
            raise ValueError("feed_id must be unique")
        return items


class CollectionBoard(BaseModel):
    """收藏夹的持久化身份。"""

    source_type: str
    board_id: str
    created_at: datetime
    updated_at: datetime


class CollectionSnapshot(BaseModel):
    """一次不可变的收藏夹观察。"""

    snapshot_id: str
    source_type: str
    board_id: str
    board_revision: int = Field(ge=1)
    request_id: str
    captured_at: datetime
    item_count: int = Field(ge=0)
    fingerprint: str
    status: CollectionStatus = CollectionStatus.CAPTURED


class CollectionSnapshotItem(BaseModel):
    """快照中的 feed membership，不携带 token。"""

    snapshot_id: str
    feed_id: str
    source_order: int = Field(ge=0)


class CollectionFeedAccessContext(BaseModel):
    """feed 最新详情访问上下文，仅供内部读取。"""

    model_config = ConfigDict(extra="forbid")

    feed_id: str
    latest_xsec_token: SecretStr = Field(repr=False)
    token_updated_at: datetime
    last_seen_at: datetime


class CollectionDiff(BaseModel):
    """相邻收藏快照的集合差异。"""

    added: list[str]
    removed: list[str]
    retained: list[str]


def collection_fingerprint(command: CollectionImportCommand) -> str:
    """计算与 token、时间和 request 无关的有序 membership 指纹。

    Args:
        command: 收藏导入命令。

    Returns:
        有序 membership 的 SHA-256 十六进制摘要。
    """
    payload = {
        "source_type": command.source_type,
        "board_id": command.board_id,
        "feed_ids": [item.feed_id for item in command.items],
    }
    canonical = dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return sha256(canonical.encode("utf-8")).hexdigest()
