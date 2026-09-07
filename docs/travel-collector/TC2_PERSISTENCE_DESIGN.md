# TC2A 收藏持久化设计

> 本文是 TC2B 的设计提案，不是已实现功能。所有代码路径均为计划，不代表当前存在。

## 设计目标与取舍

目标是把一次真实收藏夹扫描保存为不可变 observation snapshot，并支持历史比较、重启恢复和后续详情 enrichment。设计保持 `apps → xhs-adapters → xhs-core`，SQLite 是唯一 TC2 存储。

选择 append-only snapshot history，而不是覆盖当前状态：

- 首次导入表达 `0 → 50`。
- 相同内容再次主动扫描表达新的 `50 → 50` observation。
- 新增、删除和重排都由相邻 snapshot 比较得到。
- 历史 membership 不因当前收藏夹变化而删除。

被拒绝的 alternatives：只保存每个 board 的当前 feed 集合会丢失删除/重排历史；把 token 复制进每个 snapshot 会放大敏感数据留存；把 collection 直接塞进现有 `collected_post` 会混淆“已完成详情”和“仅捕获 membership”。

## Domain model

建议在 `xhs-core` 定义以下最小实体和端口：

- `CollectionBoard`：逻辑收藏夹身份，不保存完整 URL。
- `CollectionSnapshot`：一次导入的不可变元数据、计数和 fingerprint。
- `CollectionItem`：一个 snapshot 中的 membership 与 `source_order`。
- `CollectionFeedAccessContext`：feed 级最新详情执行上下文；可在内部模型中命名为 `CollectionFeed`。
- `CollectionRepository`：封装 import transaction、最新 snapshot、历史列表、snapshot detail 和最新 access context 读取。

不把 `CollectionBoard`、`CollectionSnapshot`、`CollectionSnapshotItem` 合成一个实体：board 是长期身份，snapshot 是观察事件，item 是多对多关系。一个 feed 可以出现在多个 board 和多个 snapshot。

```text
PROPOSED_DOMAIN_MODEL=Board identity + immutable Snapshot + SnapshotItem membership + feed-level latest secure access context
BOARD_IDENTITY_PERSISTED=YES: source_type + board_id
BOARD_TITLE_PERSISTED=NO by default: title is not required for identity and may contain user content
```

`source_type` 建议使用受限枚举值（TC2 当前至少为 `board`），`board_id` 只保存路由标识。禁止保存完整敏感 URL。若未来需要用户自定义 label，应单独评估隐私和 API/export 规则，而不是把平台标题隐式加入 board identity。

## Proposed tables

以下是逻辑 schema；TC2A 不创建表。时间统一采用带时区 ISO-8601 文本，ID 使用应用生成的 opaque 文本 ID，状态使用英文枚举值。

### `collection_board`

- `source_type TEXT NOT NULL`
- `board_id TEXT NOT NULL`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`
- `PRIMARY KEY (source_type, board_id)`
- `UNIQUE`：主键即唯一 board identity
- `INDEXES`：`(updated_at DESC)`；如 SQLite 版本/查询习惯不需要 DESC，可使用普通 `updated_at`
- `SENSITIVE_FIELDS`：无 token；`board_id` 属于用户收藏结构的本地数据

### `collection_snapshot`

- `snapshot_id TEXT PRIMARY KEY`
- `source_type TEXT NOT NULL`
- `board_id TEXT NOT NULL`
- `board_revision INTEGER NOT NULL`
- `request_id TEXT NOT NULL UNIQUE`
- `captured_at TEXT NOT NULL`
- `item_count INTEGER NOT NULL`
- `fingerprint TEXT NOT NULL`
- `status TEXT NOT NULL`，TC2 只允许 `captured`
- `FOREIGN KEYS`：`(source_type, board_id) REFERENCES collection_board(source_type, board_id)`
- `UNIQUE`：`request_id`；`(source_type, board_id, board_revision)`
- `INDEXES`：`(source_type, board_id, board_revision DESC)`、`(source_type, board_id, status, board_revision DESC)`；`captured_at` 仅为 observation timestamp，不作为 latest 的唯一排序依据
- `SENSITIVE_FIELDS`：无 token；fingerprint 只由稳定非敏感字段构成

### `collection_feed`

- `feed_id TEXT PRIMARY KEY`
- `latest_xsec_token TEXT NOT NULL`
- `token_updated_at TEXT NOT NULL`
- `last_seen_at TEXT NOT NULL`
- `FOREIGN KEYS`：无；feed 是可跨 board 复用的全局 feed identity
- `UNIQUE`：`feed_id`
- `INDEXES`：`(last_seen_at DESC)`；必要时 `token_updated_at`
- `SENSITIVE_FIELDS`：`latest_xsec_token` 是高敏感本地运行时上下文

### `collection_snapshot_item`

- `snapshot_id TEXT NOT NULL`
- `feed_id TEXT NOT NULL`
- `source_order INTEGER NOT NULL`
- `PRIMARY KEY (snapshot_id, feed_id)`
- `FOREIGN KEYS`：`snapshot_id REFERENCES collection_snapshot(snapshot_id)`；`feed_id REFERENCES collection_feed(feed_id)`
- `UNIQUE`：`(snapshot_id, source_order)`，同时主键保证 `(snapshot_id, feed_id)` 唯一
- `INDEXES`：`(snapshot_id, source_order)`、`(feed_id)`、`(feed_id, snapshot_id)`
- `SENSITIVE_FIELDS`：无 token；source order 是用户收藏顺序信息

```text
PROPOSED_TABLES=collection_board, collection_snapshot, collection_feed, collection_snapshot_item
```

外键约束、唯一约束和 count validation 必须在同一 import 事务中生效。SQLite 的外键启用方式是 TC2B 的实现决策，不能在 TC2A 假设默认已开启。

## Snapshot diff、fingerprint 与 order

```text
SNAPSHOT_HISTORY_MODEL=append-only immutable collection_snapshot plus collection_snapshot_item rows
SNAPSHOT_ORDER_MODEL=BOARD_LOCAL_MONOTONIC_REVISION
BOARD_REVISION_UNIQUE=UNIQUE(source_type, board_id, board_revision)
DIFF_MODEL=previous feed_id set vs current feed_id set: added=current-previous, removed=previous-current, retained=intersection; source_order comparison separately reports reorder
ITEM_IDENTITY=feed_id globally, membership scoped by snapshot_id
ITEM_UNIQUE_CONSTRAINT=(snapshot_id, feed_id) and (snapshot_id, source_order)
SNAPSHOT_FINGERPRINT_POLICY=SHA-256 of canonical source_type, board_id, and ordered feed_id list; excludes xsec_token, Cookie, capability token, title, author, and URLs
```

每个 `(source_type, board_id)` 的 `board_revision` 从 1 开始单调递增。一次新 observation import 在同一个 `BEGIN IMMEDIATE` 事务中读取当前最大 revision 并分配 `+1`；同 `request_id` 的成功 retry 返回原 snapshot，不创建新 revision。latest 按最大 `board_revision` 确定，diff 比较相邻的 `N` 与 `N-1`，不依赖 `captured_at` 的唯一性。fingerprint 用于识别内容等价，不作为唯一约束。`source_order` 使用 `0..N-1`，保证稳定导出与可重现 diff。输入中重复 feed 必须在 application boundary 被拒绝，避免悄悄改变用户顺序。

```text
REQUEST_IDEMPOTENCY_POLICY=同 request_id + 同 board identity + 同 ordered membership fingerprint 返回原 snapshot；不得创建 snapshot 或增加 board_revision
IDEMPOTENCY_CONFLICT_POLICY=同 request_id 若 board identity 或 ordered membership fingerprint 不同，HTTP 409 IDEMPOTENCY_CONFLICT；仅 token 不同按 retry 处理且不得静默刷新 token
```

## Token threat model

TC1 的 `xsec_token` 是详情执行上下文，不是可展示的收藏夹属性。为支持 API 重启后继续 TC3，建议保留每个 feed 的最新 token，但不把 token 放到 snapshot history。

```text
TOKEN_AT_REST_POLICY=仅在本机 SQLite collection_feed.latest_xsec_token 保存最新 raw token；限制工作目录权限；不新增自制加密或密钥系统
TOKEN_HISTORY_MODEL=membership snapshot 不保存 token；collection_feed 只保留 feed-level latest token
TOKEN_REFRESH_MODEL=同一 feed 后续出现 nonempty token 时 latest token wins，并更新 token_updated_at；空 token 拒绝覆盖有效 token
TOKEN_VALIDATION_ERROR_POLICY=REDACTED
TOKEN_SENTINEL_REGRESSION_REQUIRED=YES
```

风险和边界：

1. persistence 是“必须/可选”的取舍：若不落盘，API 重启后 detail workflow 必须回到 Extension 重新导入/刷新 token，故本设计在 local single-user threat model 下选择受控落盘。
2. 只有 core application service 和 repository 内部方法允许读取 raw token；board/snapshot list/detail API 不返回 token。
3. 内部 command DTO 可以携带 token，但 token-bearing model 必须使用 `repr=False` 字段或专用 wrapper；不依赖普通 dataclass/Pydantic repr 的默认行为。
4. logger 参数、异常 message、trace、HTTP error detail、导出和诊断都不得包含 token；测试只使用 `synthetic-token`。
5. 当前项目没有可信 key-management；不在 TC2A 发明 AES key、系统密钥链或自制加密。SQLite 文件被复制、备份或同机恶意进程读取仍是已知风险。

```text
XSEC_TOKEN_LIST_API=NO
XSEC_TOKEN_DETAIL_PUBLIC_API=NO
XSEC_TOKEN_LOG=NO
XSEC_TOKEN_ERROR=NO
XSEC_TOKEN_EXPORT=NO
```

## Atomic import

逻辑顺序：

```text
BEGIN IMMEDIATE
  create-or-touch board
  check request_id and compare board identity + membership fingerprint
  return original snapshot on an identical retry; otherwise reject conflict
  allocate board_revision=max(board_revision)+1 for this board
  create snapshot with request_id and board_revision
  upsert each feed and latest nonempty token
  insert N snapshot membership rows with source_order
  validate inserted count == input unique count
  validate source_order and feed uniqueness
  validate fingerprint
COMMIT
```

失败不得留下 snapshot 37/50 或孤立 feed context。事务失败后的状态必须满足 `POST_STATE == PRE_IMPORT_STATE`：若 board 原来不存在，不得留下 board；若 board 原来存在，其 `updated_at` 和 revision 不得改变；snapshot、membership、本次新增 feed 和本次 token refresh 均不得留下或生效。未来必须有 `TRANSACTION_ROLLBACK_MID_IMPORT`：在第 N 条 synthetic item 强制 repository failure，然后精确比较失败前后的可见状态。

```text
IMPORT_TRANSACTION_BOUNDARY=一次 import request 从 idempotency check、board revision 分配、snapshot metadata、feed upsert、membership insert、count/fingerprint validation 全部位于一个 BEGIN IMMEDIATE/COMMIT；任何失败 ROLLBACK
FAILED_IMPORT_STATE_POLICY=EXACT_PRE_IMPORT_STATE
```

## Idempotency and restart

```text
REQUEST_IDEMPOTENCY=required client request_id persisted UNIQUE on collection_snapshot; identical retry returns the original snapshot/result and never creates a second snapshot or revision
REQUEST_IDEMPOTENCY_CONFLICT_POLICY=不同 board identity 或不同 ordered membership fingerprint 返回 HTTP 409 IDEMPOTENCY_CONFLICT；仅 token 不同按 retry 处理且不得刷新 token
CONTENT_EQUIVALENCE=ordered feed list fingerprint is comparable but not a uniqueness constraint; separate user scan gets a new request_id and a new observation snapshot even when equivalent
PERSISTED_STATE=boards, immutable snapshots, snapshot memberships, feed latest access context, request id, source order, captured timestamps, captured status
EPHEMERAL_STATE=current HTTP request object, in-memory worker/future, temporary locks, active browser panel/session, progress callbacks
TC2_PERSISTED_STATES=CAPTURED
TC3_RESERVED_STATES=DETAIL_QUEUED, DETAIL_RUNNING, DETAIL_READY, DETAIL_FAILED, NEEDS_REIMPORT
```

API process restart 后，latest snapshot、历史 snapshots、membership 和 latest feed access context 均可由 repository 读取；当前 request 和 worker 不假设可恢复。若 token 已过期，TC3 应转为 `NEEDS_REIMPORT`，而不是把旧 token 复制为新的历史版本。

## Extension/API boundary

Extension 继续只负责当前 board 页面捕获。它通过 localhost API 提交 command；不得直接导入 SQLite、访问 `state_dir` 或传递完整 URL。

```text
EXTENSION_DIRECT_SQLITE=NO
```

内部 import command 的最小字段：`request_id`、`items[]`；每项必需 `feed_id`、nonempty `xsec_token`、`source_order`。`source_type` 和 `board_id` 只来自 URL path，body 不重复这些字段；TC2 不接收 title、author、cover 或完整 URL。公共 response 只返回 IDs、counts、timestamps、status、fingerprint 和 diff summary，不返回任何 token。

```text
IMPORT_BOARD_IDENTITY_SOURCE=PATH_ONLY
TC2_IMPORT_OPTIONAL_UI_METADATA=NO
COLLECTION_API_CAPABILITY_REQUIRED=YES
```

建议最小 API（只设计）：

- `POST /collections/{source_type}/{board_id}/imports`
  - `IMPORT_REQUEST={request_id, items[{feed_id,xsec_token,source_order}]}`；path parameters 是唯一 board identity authority。
  - `IMPORT_RESPONSE={snapshot_id, source_type, board_id, captured_at, item_count, fingerprint, status, added_count, retained_count, removed_count}`。
- `GET /collections/{source_type}/{board_id}/snapshots?limit=...`
  - `LIST_RESPONSE={items[{snapshot_id,board_revision,captured_at,item_count,fingerprint,status}], next_cursor?}`；按 `board_revision DESC` 查询。
- `GET /collections/{source_type}/{board_id}/snapshots/{snapshot_id}`
  - `DETAIL_RESPONSE={snapshot_id,board_revision,board identity,captured_at,item_count,status,fingerprint,items[{feed_id,source_order}],diff?}`；diff 只比较相邻 revision。

这些路径只是草案，实际 route naming 应在 TC2B 复用现有 `create_*_router`、Pydantic model 和 capability dependency。POST import、GET snapshot list、GET snapshot detail 全部必须复用现有 extension capability authentication；response 不含 token 也不能放宽读取鉴权。内部 sensitive input model 与公共 output model 必须结构分离：

```text
SENSITIVE_INPUT_MODEL=CollectionImportCommand，独立 Pydantic model，含 nonempty xsec_token，字段 repr/日志脱敏
PUBLIC_OUTPUT_MODEL=CollectionSnapshotResponse / CollectionSnapshotListItem / CollectionSnapshotDetail，类型中根本不存在 xsec_token 字段
TOKEN_REPR_POLICY=token-bearing input/domain wrapper 默认 repr 不显示 token
TOKEN_LOG_POLICY=logger 参数和异常/HTTP detail 不接受 raw token；只记录安全分类和 snapshot/feed opaque ID
TOKEN_SENTINEL=synthetic-secret-token-never-leak
TOKEN_ERROR_REDACTION_SCOPE=missing/empty/invalid token、Pydantic 422、FastAPI error detail、exception str/repr、logger、repository/application failure、public response 均不得出现 sentinel
FOREIGN_KEY_ENFORCEMENT_REQUIRED=YES
```

TC2B 必须使用上面的 synthetic sentinel 做回归测试；`repr=False` 只是辅助措施，不是错误响应、异常或日志脱敏的充分保证。

SQLite 外键不能假设默认开启。每个执行 collection relational operation 的 connection 必须确认 `PRAGMA foreign_keys = ON`；TC2B 可安全增强 shared connection helper，或在 collection repository 的连接 setup 中完成，但必须由测试证明。

## Capacity and test matrix

设计不针对 Japan=50 硬编码，输入上限由 request validation 设置一个明确的有限值并覆盖 0、1、50、500。上述索引足以支持 latest snapshot、board history、snapshot membership 和 feed lookup；在 500 条规模下不需要提前引入新数据库基础设施。

TC2B synthetic test matrix：

| IDs | 覆盖 |
|---|---|
| P01–P04 | empty、1、50、500 import |
| P05–P07 | 单请求重复 feed、同 request retry、独立 identical scan |
| P08–P10 | add、remove、reorder diff |
| P11–P15 | token refresh、rollback mid-import、restart、latest/history snapshot |
| P16–P21 | list/detail/repr/log/exception/export token redaction |
| P22–P26 | invalid board/feed、missing/empty token、oversized item count |
| P27–P28 | capability auth、localhost boundary |
| P29–P31 | empty/repeatable init、existing DB restart |
| P32–P33 | source_order/feed uniqueness |
| P34–P35 | concurrent/sequential board revision；request retry 不增加 revision |
| P36–P39 | reused request conflict、token-only retry、new request token refresh、path/body identity |
| P40–P41 | token sentinel 全链路脱敏；所有 collection GET/POST capability auth |
| P42–P45 | FK enforcement；new/existing board exact rollback；same captured_at 仍按 revision 排序 |

全部 fixture 使用 synthetic IDs/token/title/author；不使用真实 Japan 数据。P34–P45 必须全部为 synthetic regression。

## TC2B implementation file plan（计划，不在 TC2A 创建）

- `packages/xhs-core/src/xhs_core/domain/collection.py`：board/snapshot/item/status/value objects。
- `packages/xhs-core/src/xhs_core/domain/collection_ports.py`：`CollectionRepository`、事务结果和安全上下文端口。
- `packages/xhs-core/src/xhs_core/application/collection_import.py`：校验、fingerprint、diff、request idempotency 和应用事务编排。
- `packages/xhs-adapters/src/xhs_adapters/sqlite/collection_storage.py`：runtime schema initialization、indexes、row mapping、rollback helper。
- `packages/xhs-adapters/src/xhs_adapters/sqlite/collections.py`：SQLite repository implementation；按现有 `SqliteBrowserTaskRepository` 风格拆分 storage/helper。
- `apps/api/src/xhs_api/collection_models.py`：敏感 request 与 public response 的独立 DTO。
- `apps/api/src/xhs_api/collections.py`：router factory、extension capability dependency、public redaction boundary。
- `apps/api/src/xhs_api/bootstrap.py`：composition root 注入新 adapter/application service。
- `packages/xhs-contracts/src/index.ts`：仅在 HTTP/Extension 共享字段确实需要时增加不含 token 的公共类型；不把 raw token 放进 public response type。
- `apps/extension/src/`：仅在 TC2B 需要把现有内存扫描结果提交 import endpoint 时修改；不得出现 SQLite 依赖。
- `tests/domain/`、`tests/application/`、`tests/infrastructure/`、`tests/interfaces/`：覆盖 P01–P45 的 synthetic regression，包括 revision、冲突、脱敏、鉴权、FK 和精确回滚。

## Known risks

### KNOWN_RISKS

- raw `xsec_token` 的 local-at-rest risk；本设计只做最小暴露和访问边界。
- snapshot history 长期增长，需要未来 retention/export policy，但不能破坏历史 diff 语义。
- 无统一 schema version/migration framework，inline initialization 的演进风险仍在。
- board 删除或改名：board id 是身份，title 默认不持久化；产品层需要另行决定展示 label。
- token expiration/invalidity 可能要求 `NEEDS_REIMPORT`，不能静默沿用旧 token。
- request replay 与客户端生成 request_id 的质量；服务端必须保存并校验 request idempotency。
- 中途崩溃、磁盘损坏、外键未启用或部分备份导致数据一致性风险。
- API、repr、日志、exception、export 的任一新路径都可能造成 accidental disclosure。

### OPEN_DECISIONS

- raw token 的本机文件权限/备份排除策略由 TC2B 结合现有 `AppSettings.state_dir` 和平台能力最终确定。
- import retry 的重复 request 是返回原 response，还是返回明确的 `409` 加原 snapshot reference，需要统一 API 语义。
- identical scan 是否在 UI 标记为 duplicate observation，当前只决定“仍保留 snapshot”，未决定 UI 文案。
- board title/用户 label 是否进入后续产品层；当前安全默认是不持久化。
- SQLite 外键启用、数据库 busy timeout 与 collection import transaction helper 的具体实现接口。
- snapshot retention、删除 board 的级联/保留策略，以及未来 export 对历史 snapshot 的选择。
