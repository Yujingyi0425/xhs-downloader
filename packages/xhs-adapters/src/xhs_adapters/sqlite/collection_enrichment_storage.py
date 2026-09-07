"""收藏详情 enrichment 的 SQLite 行转换。"""

import json
from datetime import datetime

from xhs_core.domain.collection_enrichment import (
    CollectionEnrichmentStatus,
    CollectionFeedDetail,
    CollectionFeedEnrichment,
)


def enrichment_from_row(row: tuple[object, ...]) -> CollectionFeedEnrichment:
    """把 enrichment 行转换为领域模型。

    Args:
        row: SQLite 查询返回的 enrichment 行。

    Returns:
        通过状态不变量校验的 enrichment 记录。
    """
    detail = (
        CollectionFeedDetail.model_validate(json.loads(str(row[4])))
        if row[4] is not None
        else None
    )
    record = CollectionFeedEnrichment(
        snapshot_id=str(row[0]),
        feed_id=str(row[1]),
        enrichment_version=int(row[2]),
        status=CollectionEnrichmentStatus(str(row[3])),
        detail=detail,
        attempt_count=int(row[5]),
        last_error_code=str(row[6]) if row[6] is not None else None,
        created_at=datetime.fromisoformat(str(row[7])),
        updated_at=datetime.fromisoformat(str(row[8])),
        enriched_at=(
            datetime.fromisoformat(str(row[9])) if row[9] is not None else None
        ),
    )
    record.validate_invariants()
    return record
