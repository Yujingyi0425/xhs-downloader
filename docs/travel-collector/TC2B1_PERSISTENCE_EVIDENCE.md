# TC2B1 Core + SQLite Persistence Evidence

本文只记录 TC2B1 的 synthetic test facts，不包含真实 board、feed、token、收藏标题、用户路径或真实页面数据。

```text
PHASE=TC2B1-CORE-SQLITE-IMPLEMENTATION
BASELINE_COMMIT=a373ae02496531145f9292f668542fcf487b9773
```

R1 repair chain:

```text
TC2B1_R1_REPAIR_COMMIT=ba74e83913bb61d26f9def847b231dd2c26f3ee8
TC2B1_R1_TEST_COMMIT=57c79633dbe41e93bc0c91033f6e0b8f6ee609f1
TC2B1_R1_EVIDENCE_BASE=c4c5e0f845614373009330f94c9f59d920d2842c
```

## Implementation boundary

- `xhs-core` 定义 `CollectionBoard`、`CollectionSnapshot`、`CollectionSnapshotItem`、`CollectionFeedAccessContext`、`CollectionStatus`、导入命令、fingerprint 和 `CollectionRepository` port。
- `xhs-adapters` 提供 `SqliteCollectionRepository`，schema 初始化、FK 开启、读写和 atomic import 均在 SQLite adapter 内完成。
- 未修改 `apps/`、`packages/xhs-contracts/`、Extension、HTTP API、manifest、`pyproject.toml` 或 `uv.lock`。
- `CORE_IMPORTS_ADAPTER=NO`；`NEW_DEPENDENCIES=NO`。

## Synthetic behavior evidence

```text
TABLES_CREATED=collection_board, collection_snapshot, collection_feed, collection_snapshot_item
BOARD_REVISION=board-local monotonic 1..N; UNIQUE(source_type, board_id, board_revision)
REQUEST_IDEMPOTENCY=同 board + ordered membership fingerprint 返回原 snapshot，不增加 revision
IDEMPOTENCY_CONFLICT=不同 board 或 membership 返回 CollectionIdempotencyConflictError；token-only retry 不刷新 token
FINGERPRINT=SHA-256(source_type, board_id, ordered feed_id sequence)，独立于 token/time/request
SOURCE_ORDER_VALIDATION=必须恰好为 0..N-1，拒绝重复、负数和 gap；empty 合法
ATOMIC_IMPORT=single connection BEGIN IMMEDIATE/COMMIT
EXACT_ROLLBACK=POST_STATE == PRE_IMPORT_STATE；new/existing board 均覆盖
FOREIGN_KEY_ENFORCEMENT=每个 collection connection 验证 PRAGMA foreign_keys=1
RESTART_PERSISTENCE=新 repository instance 读取 board、latest/history、membership、revision、latest access context
TOKEN_AT_REST=仅 collection_feed 保存 latest raw synthetic token；snapshot/membership 不含 token
TOKEN_REFRESH=仅 new request observation 刷新 latest token
CORE_TOKEN_REDACTION=SecretStr repr 与 synthetic validation/error text 不泄露 token sentinel
IDEMPOTENT_RESULT_REPLAY=PASS
RESULT_PREPARED_BEFORE_COMMIT=PASS
POST_COMMIT_FAILURE_WINDOW_CLOSED=PASS
TOKEN_SENTINEL_ACTUALLY_EXERCISED=YES
LOG_REDACTION=PASS
EXCEPTION_REDACTION=PASS
```

覆盖的 synthetic tests 包括空集、1/50/500 条目、增删改序、重复 feed、request retry/conflict、token refresh、mid-import failure rollback、COMMIT 前结果准备失败、并发 revision、真实 FK constraint、重启恢复、历史/latest 读取及 token redaction。

关键 pytest nodeid 映射：

| Contract | pytest nodeid |
|---|---|
| P03 / P04 / P29–P31 | `tests/infrastructure/test_collection_repository.py::test_empty_and_large_imports_are_synthetic_and_fk_enabled` |
| P05 / P18 / P19 | `tests/infrastructure/test_collection_contracts.py::test_duplicate_feed_and_token_sentinel_are_redacted` |
| P06 / P37 | `tests/infrastructure/test_collection_repository.py::test_request_idempotency_conflict_and_token_only_retry` |
| P10 | `tests/infrastructure/test_collection_contracts.py::test_reorder_changes_fingerprint_but_not_set_diff` |
| P12 / P20 / P43 / P44 | `tests/infrastructure/test_collection_repository.py::test_exact_rollback_for_new_and_existing_board`、`test_fk_constraint_and_pre_commit_result_rollback` |
| P34 / P35 / P36 / P38 | `tests/infrastructure/test_collection_repository.py::test_concurrent_imports_get_distinct_revisions`、`test_request_idempotency_conflict_and_token_only_retry`、`test_new_request_refreshes_token_and_restart_reads_state` |
| P42 | `tests/infrastructure/test_collection_contracts.py::test_fk_constraint_and_pre_commit_result_rollback` |

```text
EMPTY_IMPORT=PASS
ONE_ITEM_IMPORT=PASS
FIFTY_ITEM_IMPORT=PASS
FIVE_HUNDRED_ITEM_IMPORT=PASS
DUPLICATE_FEED_REJECTED=PASS
REORDER_FINGERPRINT_CHANGED=PASS
REORDER_DIFF_CORRECT=PASS
IDEMPOTENT_RESULT_REPLAY=PASS
NEW_BOARD_EXACT_ROLLBACK=PASS
EXISTING_BOARD_EXACT_ROLLBACK=PASS
FOREIGN_KEY_CONSTRAINT_BEHAVIOR=PASS
```

## Toolchain result

```text
TC2B1_TARGETED_TESTS=PASS (10 collection tests; 15 including architecture validation)
RUFF_CHECK=PASS
RUFF_FORMAT=PASS
PYTEST=PASS
PYTEST_TOTAL=645
PYTEST_FAILED=0
COVERAGE=91.23%
COVERAGE_GATE=PASS (>=85%)
```

P16/P17/P21/P27/P28/P39/P40/P41 属于 API 或 localhost boundary，留给 TC2B2；本阶段没有实现或测试这些接口。
