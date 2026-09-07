# TC2A 收藏持久化架构审计

> 本文只记录当前仓库事实。建议方案见 `TC2_PERSISTENCE_DESIGN.md`。

## 审计边界与基线

- `BASELINE_COMMIT=b59263440c77a0a9db2f9e1ac7fb89d4fb051dbc`
- 本次没有修改 `packages/`、`apps/` 或 `tests/`。
- TC1 冻结契约：`feed_id + nonempty xsec_token + matching explore alias`。
- `XSEC_SOURCE_REQUIRED=NO`，`PROFILE_SOURCE_BORROWING=NO`。

## 分层与依赖

这是对源码 import 和 package 声明的事实审计：

```text
apps/api, apps/cli, apps/mcp
             ↓ import
      xhs-adapters
             ↓ import
        xhs-core
```

- `xhs-core` 的 `domain/`、`application/` 定义模型、用例和 `Protocol` 端口，例如 `xhs_core.domain.ports.PostRepository`、`DownloadRepository`，以及 `xhs_core.domain.browser_ports.BrowserTaskRepository`。
- `xhs-adapters` 从 `xhs_core` 导入这些端口并提供 SQLite、HTTP、文件和浏览器实现；`xhs_adapters.factory` 是适配器工厂。
- `apps/api/src/xhs_api/bootstrap.py:create_api_dependencies` 创建 `xhs-adapters` 实现，再将其注入 API 使用的 core service；`apps/api/src/xhs_api/app.py:create_api` 创建路由并管理生命周期。
- `packages/xhs-contracts` 是独立的 TypeScript 协议包，被扩展和 WebUI 使用；它不是 Python 运行时依赖。
- 当前仓库没有 `packages/xhs-contracts` 的 Python 包，也没有 `xhs-core` 导入 `xhs-adapters` 的生产 import。

```text
CORE_DEPENDENCY_DIRECTION=xhs-core defines ports; no adapter import
ADAPTER_DEPENDENCY_DIRECTION=xhs-adapters -> xhs-core
API_COMPOSITION_PATTERN=apps/api bootstrap creates adapters and injects core services
EXTENSION_TO_API_PATTERN=extension fetches localhost HTTP API with shared TypeScript contracts
CORE_IMPORTS_ADAPTER=NO
```

## SQLite 仓储现状

```text
EXISTING_SQLITE_REPOSITORIES=SqliteBrowserTaskRepository, SqliteClientRecordRepository, SqliteDownloadRepository, SqliteTaskRepository, SqliteExtensionCredentialRepository, SqlitePostRepository, SqlitePublicationDraftRepository, SqlitePublicationTaskRepository
```

公共连接入口是 `packages/xhs-adapters/src/xhs_adapters/sqlite/connection.py:connect`：每次打开连接设置 `PRAGMA busy_timeout=5000`，首次连接尝试 `PRAGMA journal_mode=WAL`，上下文退出关闭连接。仓储通常用 `_initialized` 布尔值做进程内懒初始化；初始化不是全局 schema registry。

下表是所有公开 SQLite 仓储的逐项事实。`payload` 型表的业务字段主要位于 Pydantic JSON，而不是 SQLite 列。

| FILE / CLASS | TABLES | INITIALIZATION_METHOD | TRANSACTION_STYLE | ROW_MAPPING_STYLE | DATETIME_STYLE | ENUM / ID STYLE |
|---|---|---|---|---|---|---|
| `sqlite/browser_tasks.py` / `SqliteBrowserTaskRepository` | `browser_task`；索引 `browser_task_queue`、`browser_task_driver_queue`、`browser_task_lease` | `_initialize()` 调 `initialize_browser_task_storage()` | 普通 save/读取各自 commit；claim/update 使用 `BEGIN IMMEDIATE`，冲突 rollback | `browser_task_storage.py` 读取显式列，payload 用 `BrowserTask.model_validate_json` | `datetime.fromisoformat` / `.isoformat()` | 状态和 driver 用 `.value`；任务 ID、request ID 是文本，租约只存 hash |
| `sqlite/client_records.py` / `SqliteClientRecordRepository` | `client_download_record` | `_initialize()` 内 `CREATE TABLE IF NOT EXISTS` | `executemany` 后 commit，无显式事务块 | payload 用 `ClientDownloadRecord.model_validate_json` | `created_at.isoformat()` | record ID 文本主键，冲突 upsert |
| `sqlite/download_records.py` / `SqliteDownloadRepository` | `download_record` | `_initialize()` | 单行 upsert 后 commit | payload 用 `DownloadRecord.model_validate_json` | `datetime.now(UTC).isoformat()` | `work_id` 文本主键 |
| `sqlite/download_tasks.py` / `SqliteTaskRepository` | `download_task` | `_initialize()` | 单行 upsert 后 commit | payload 用 `DownloadTask.model_validate_json`，由 `row[0]` 取 payload | 模型时间 `.isoformat()` | `task_id` 主键、`client_request_id` UNIQUE、状态另存文本 |
| `sqlite/extension_credentials.py` / `SqliteExtensionCredentialRepository` | `publication_extension` | `_initialize()` 内 `BEGIN IMMEDIATE`、建表及 `PRAGMA table_info` 兼容旧列 | register/revoke/touch commit；初始化显式 commit | `row[0..2]` 映射 `ExtensionPresence` | `datetime.fromisoformat` / `.isoformat()` | extension identity 文本主键；token 只存摘要 |
| `sqlite/posts.py` / `SqlitePostRepository` | `collected_post` | `_initialize()` | save/delete commit | payload 用 `WorkDetail.model_validate_json` | `datetime.now(UTC).isoformat()` | `work_id` 文本主键，冲突 upsert |
| `sqlite/publication_drafts.py` / `SqlitePublicationDraftRepository` | `publication_draft` | `_initialize()` | save/delete commit | payload 用 `PublicationDraft.model_validate_json` | 模型时间 `.isoformat()` | `draft_id` 文本主键 |
| `sqlite/publication_tasks.py` / `SqlitePublicationTaskRepository` | `publication_task`；索引 `publication_task_status`、`publication_task_driver_status` | `_initialize()` 调 `initialize_publication_task_storage()` | claim/recovery 使用 `BEGIN IMMEDIATE` 和 rollback；普通写入 commit | `publication_task_storage.py` 解析 JSON 为 `PublicationTask` | `datetime.fromisoformat` / `.isoformat()` | status/mode/driver 用 `.value`；task/draft ID 文本 |
| `sqlite/settings_repository.py` / `DotenvSettingsRepository` | 无 SQLite 表；dotenv 文件 | 文件读写，无数据库初始化 | 文件替换/写入，不属于 SQLite 事务 | Pydantic settings / dotenv 字符串 | 非 SQLite datetime | 配置键为字符串 |

`SqliteBrowserTaskRepository` 是当前最接近 TC2 的参考：它已有显式 claim/update CAS 条件、租约摘要、坏 payload 隔离和恢复测试；但它的 repository 端口是浏览器任务专用，不能直接承载 collection snapshot。

## Schema 与 migration

```text
EXISTING_SCHEMA_INIT_PATTERN=runtime CREATE TABLE IF NOT EXISTS plus CREATE INDEX IF NOT EXISTS; selected legacy columns use PRAGMA table_info and ALTER TABLE
EXISTING_MIGRATION_PATTERN=no standalone migration files or version table
```

现有演进方式是各仓储首次访问时自初始化，并对少数旧列做内联兼容。没有 Alembic 或其他 migration framework。风险是多仓储共享数据库时初始化顺序、跨表变更、失败恢复和长期 schema version 缺少统一编排；TC2A 不引入 Alembic，TC2B 应继续沿用仓库模式并明确升级策略。

## 事务与测试数据库

```text
EXISTING_TRANSACTION_PATTERN=每次操作打开独立 aiosqlite 连接；写成功后显式 commit；浏览器/发布任务的 claim、CAS update、recovery 用 BEGIN IMMEDIATE 与 rollback；普通写操作没有统一 async transaction helper
TRANSACTION_GAP=现有 helper 不能直接保证 collection import 的 board、snapshot、feed context、membership 多表全有或全无；TC2B 需要一个 collection 专用事务边界
```

连接生命周期由 `async with connect(...)` 管理。异常路径主要依赖上下文关闭和显式 rollback；`browser_task_storage.py:save_browser_task_if_snapshot`、`publication_task_storage.py:save_publication_task_if_snapshot` 展示了条件更新和失败回滚模式。

测试证据全部是本地合成数据库：

- `tests/infrastructure/test_browser_task_repository.py` 使用 `tmp_path/state.db`，覆盖初始化、读取、领取、过期和旧列迁移。
- `tests/infrastructure/test_browser_task_storage_consistency.py`、`test_browser_recovery_cas.py` 覆盖存储一致性、CAS 和重启/恢复语义。
- `tests/application/test_browser_tasks.py`、`test_browser_read_provider_failures.py` 使用 `tmp_path` 和 SQLite repository 验证任务生命周期。
- `tests/infrastructure/test_sqlite_connection.py` 验证 WAL/连接行为；当前未发现以 `:memory:` 为主的 TC2 模式。

```text
EXISTING_TEST_DB_PATTERN=pytest tmp_path + state.db + repository fixtures; synthetic payloads; no Docker dependency
```

## API、组合根与安全边界

`packages/xhs-adapters/src/xhs_adapters/config.py:AppSettings` 的 `server_host` 默认值是 `127.0.0.1`，`apps/api/src/xhs_api/app.py:run_api` 将它传给 Uvicorn。CLI `apps/api/src/xhs_api/main.py:main` 允许 `--host` 覆盖配置，因此默认是回环绑定，但配置层并未绝对禁止非回环地址。

```text
API_BIND_ADDRESS=127.0.0.1 by default
API_LOOPBACK_ONLY=default YES; configurable host override means not an unconditional invariant
LOOPBACK_RISK=--host or server_host can expose the service beyond loopback if deliberately configured; extension_access still rejects non-loopback request clients
```

扩展访问实现位于 `apps/api/src/xhs_api/extension_access.py`：

- `require_extension_origin` 要求 loopback client，并校验 `Origin` scheme 和 extension ID。
- `require_extension` 再要求 loopback client、`X-Extension-Id`、可选 installation identity、`Authorization: Bearer ...`。
- `xhs_core.application.ExtensionCredentialService` 生成随机 token 并计算 SHA-256；`SqliteExtensionCredentialRepository` 的 `publication_extension.token_hash` 只保存摘要，验证用 `secrets.compare_digest`。
- `apps/api/src/xhs_api/bootstrap.py:create_api_dependencies` 是 composition root，创建 `SqliteClientRecordRepository`、`SqliteTaskRepository`、`SqlitePostRepository` 以及浏览器/发布 runtime，再交给 `create_api` 挂路由。

```text
CAPABILITY_AUTH_IMPLEMENTATION=loopback client + extension Origin/ID + Bearer token + registered installation identity
CAPABILITY_TOKEN_STORAGE=SQLite publication_extension.token_hash; raw registration token returned once and held by extension credential storage
CAPABILITY_TOKEN_HASHING=SHA-256 digest with compare_digest verification
CAPABILITY_REQUEST_VALIDATION=FastAPI/Pydantic request models, query bounds, loopback/origin checks, capability credential dependency
```

现有 API 风格是 `create_*_router(...) -> APIRouter`，请求/响应使用独立 Pydantic models，领域异常通过 `register_exception_handlers` 注册，仓储由 bootstrap 注入，生命周期由 `create_api` 的 async lifespan 管理。TC2 后续应复用这些模式。

## 当前事实结论

```text
EXISTING_REPOSITORY_PATTERN=每个 SQLite repository 自持 Path 与懒初始化状态；按领域模型提供 async CRUD/list/claim 方法
EXISTING_SQLITE_PATTERN=aiosqlite + shared connect helper + WAL attempt + busy_timeout + JSON payload snapshots
EXISTING_SCHEMA_INIT_PATTERN=runtime CREATE IF NOT EXISTS with limited inline ALTER compatibility
EXISTING_MIGRATION_PATTERN=none
EXISTING_TRANSACTION_PATTERN=per-operation commit; explicit immediate transactions only for selected CAS/claim/recovery flows
EXISTING_TEST_DB_PATTERN=tmp_path/state.db repository fixtures with synthetic data
```

TC1 的 Extension 当前只在页面内存中保留捕获结果，不访问 SQLite、不发送 collection item 到 API；持久化边界必须在 TC2B 通过 localhost API 进入 core application service，再由 adapter 写 SQLite。
