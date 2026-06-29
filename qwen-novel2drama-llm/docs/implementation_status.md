# 实现状态

当前项目长期定位：**可部署、可扩展、可观测、可审计、可路由、可控成本的 AI 大模型底座**。

AI 短剧/漫剧是长期特色能力方向，不是当前优先完成的完整应用平台。

## 已经能跑

### P0 文本生成基础运行时

- `inference/model_utils.py`：文本模型加载、一次性生成与 transformers TextIteratorStreamer 流式生成入口。
- `configs/model_registry.json`：基础模型运行时注册表。
- `scripts/inspect_model_registry.py`：查看模型运行时注册表。
- `scripts/plan_training_run.py`：生成训练运行 manifest。
- `scripts/register_model_version.py`：登记训练后的模型版本。
- `inference/api_server.py`：可从 active model version 启动 API。

### P0/P1 底座工程契约

- 统一 content block、错误码、response envelope schema。
- 模型能力注册表、模型实例注册表、模型路由策略契约。
- OpenAPI 规格已同步当前 `/v1/*` runtime endpoints。
- OpenAPI/runtime 合同检查脚本与默认 CI workflow。
- CI profiles 已覆盖 contracts、core、provider adapter、API server、Postgres run store optional profile、本地模型导入检查。

### P1 底座核心服务 v1

- router、token counter、cost estimator、usage ledger、provider usage reconciliation。
- model tool loop usage aggregation。
- memory store、rule engine、skills registry、MCP-style adapter。
- auth、audit、rate limit。
- file/SQLite quota backend。
- Agent events、run store、SQLiteRunStore、PostgresRunStore persistence v1、lifecycle、runtime、tool loop。
- `agent/run_store.py`：支持 file/sqlite/postgres store selection 和 worker lease contract。
- `agent/sqlite_run_store.py`：支持 `run_leases` 表与 SQLite 事务化 claim/renew/release。
- `agent/postgres_run_store.py`：支持 Postgres request/report/event/cancel/artifact/list/status/lease persistence、migration helper 和 optional pool profile。
- `migrations/postgres_run_store.sql`：Postgres run store schema v1。
- `scripts/apply_postgres_run_store_migration.py`：Postgres run store migration runner，支持 dry-run 和 DSN-gated apply。
- `configs/run_store/postgres.example.env`：Postgres run store/pool env 模板。
- `requirements/postgres-run-store.txt`：Postgres run store optional dependency profile，包含 pool 依赖。
- API server 可通过 run store env 选择 file/sqlite/postgres。

### 测试与文档

- Run store、SQLite run store、Postgres run store contract/migration runner、Agent events、Agent runtime、Agent lifecycle、API server、auth、audit/rate limit、workspace quota、quota store、skills、MCP 等测试已补充。
- `docs/p1_agent_run_store.md`
- `docs/p1_agent_runtime_run_store_writes.md`
- `docs/p1_api_server_integration.md`
- `docs/p1_workspace_quota.md`
- `docs/p1_auth_api_keys.md`
- `docs/codex_execution_plan.md`

## 已完成标记

```text
research_completed_v1 = true
requirements_ready_for_architecture = true
P0_contracts_implemented_v1 = true
P1_runtime_openapi_contract_synced_v1 = true
P1_openapi_contract_check_implemented_v1 = true
P1_ci_contract_check_implemented_v1 = true
P1_heavyweight_provider_model_ci_profiles_implemented_v1 = true
P1_auth_api_key_workspace_scope_implemented_v1 = true
P1_auth_audit_rate_limit_implemented_v1 = true
P1_workspace_budget_quota_implemented_v1 = true
P1_sqlite_quota_rate_limit_backend_implemented_v1 = true
P1_agent_worker_lease_implemented_v1 = true
P1_postgres_run_store_scaffold_implemented_v1 = true
P1_postgres_run_store_persistence_implemented_v1 = true
P1_postgres_run_store_migration_runner_implemented_v1 = true
P1_agent_lifecycle_resume_cancel_retry_implemented_v1 = true
P1_agent_lifecycle_api_endpoints_implemented_v1 = true
P1_agent_run_store_abstraction_implemented_v1 = true
P1_sqlite_run_store_implemented_v1 = true
P1_agent_lifecycle_run_store_selection_implemented_v1 = true
P1_agent_runtime_run_store_writes_implemented_v1 = true
P1_agent_run_listing_query_implemented_v1 = true
P1_db_backed_agent_events_implemented_v1 = true
P1_multi_round_model_tool_loop_usage_aggregation_implemented_v1 = true
P1_same_stream_tool_result_continuation_contract_implemented_v1 = true
P1_local_provider_adapter_implemented_v1 = true
P1_local_provider_cache_concurrency_controls_implemented_v1 = true
P1_local_provider_streaming_output_implemented_v1 = true
P1_openai_compatible_native_streaming_implemented_v1 = true
P1_streamed_tool_call_delta_reconstruction_implemented_v1 = true
P1_agent_stream_tool_call_bridge_implemented_v1 = true
P1_incremental_stream_tool_execution_implemented_v1 = true
P1_provider_usage_reconciliation_implemented_v1 = true
P1_agent_event_stream_implemented_v1 = true
P1_sse_live_agent_events_implemented_v1 = true
P1_model_decided_tool_loop_implemented_v1 = true
runtime_services_completed = partially
implementation_completed = false
```

## 当前最重要的未完成项

1. provider-native bidirectional continuation adapter。
2. secret-gated real provider smoke tests。
3. Postgres/distributed quota backend。
4. 完整 worker queue / dispatcher。
5. Postgres schema version tracking / migration history table。

## 后续开发顺序

1. P1：provider-native bidirectional continuation、secret-gated provider smoke profiles、Postgres/distributed quota backend、worker queue/dispatcher、Postgres migration history。
2. P2：多 provider、多模态生成/理解、MCP SDK 兼容层、评测、观测、审计、部署。
3. P3：AI 短剧/漫剧专项能力。

## 禁止误判

- Postgres migration runner/connection pool profile 完成，不等于完整生产部署、schema migration history 或数据库运维治理完成。
- PostgresRunStore persistence v1 完成，不等于完整生产数据库治理完成。
- Worker lease 完成，不等于完整任务队列、分布式调度器或自动 worker pool 完成。
- SQLite quota/rate limit backend 完成，不等于 Postgres/distributed quota、全局限流或完整账单系统完成。
- DB-backed Agent events 完成，不等于分布式事件总线、WebSocket 或生产级任务队列完成。
- same-stream continuation contract 完成，不等于所有 provider 都支持同一条流内回灌 tool result。
- 本地 provider adapter 完成，不等于所有 provider 已接入。
- 训练 runbook 不等于模型已经训练完成。
