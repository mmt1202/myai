# Codex 连续执行任务总控文档

本文档用于让 Codex 按顺序继续完成 `qwen-novel2drama-llm` 的剩余工程任务。

当前项目定位：**可部署、可扩展、可观测、可审计、可路由、可控成本的 AI 大模型底座**。

AI 短剧/漫剧是长期特色方向，不是当前优先完成的完整应用平台。

---

## 0. Codex 执行总规则

默认在当前仓库主项目目录执行：

```text
qwen-novel2drama-llm/
```

每个任务尽量独立提交，commit message 使用：

```text
Txxx: <short English summary>
```

每完成一个任务，必须同步：代码、单元测试、文档、`docs/implementation_status.md`、必要的 OpenAPI、必要的 CI profile。

先跑轻量测试：

```bash
python scripts/check_openapi_contract.py
python -m unittest tests.test_openapi_contract_check tests.test_foundation_contracts
python -m unittest tests.test_foundation_core_services tests.test_memory_store tests.test_rule_engine tests.test_auth_service tests.test_auth_audit_rate_limit tests.test_usage_reconciliation tests.test_model_tool_loop_usage tests.test_provider_continuation tests.test_run_store tests.test_sqlite_run_store tests.test_agent_lifecycle tests.test_agent_events tests.test_ci_profiles tests.test_workspace_quota tests.test_quota_store tests.test_skill_registry tests.test_mcp_adapter
```

Postgres run store optional profile：

```bash
python -m pip install -r requirements/postgres-run-store.txt
python -m unittest tests.test_postgres_run_store_contract
```

如果改到 API server，再跑：

```bash
python -m unittest tests.test_api_server_foundation
```

如果改到 Agent runtime/tool loop，再跑：

```bash
python -m unittest tests.test_agent_runtime tests.test_agent_lifecycle tests.test_agent_events tests.test_agent_tool_loop tests.test_run_store tests.test_sqlite_run_store
```

禁止误判：RunStore/SQLite/API/run listing/DB-backed events/SQLite quota backend/worker lease/Postgres persistence/migration runner 都是阶段性能力，不等于 schema migration history、完整分布式任务队列、分布式事件总线、WebSocket、全文搜索、全局限流或生产级调度已完成。

---

## 1. 当前已完成基线

```text
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
```

---

# Phase A：Run Store 与 Agent 状态生产化

## T001：SQLiteRunStore v1

状态：**已完成**。

---

## T002：Agent lifecycle 支持 run_store 配置选择

状态：**已完成**。

---

## T003：Agent runtime artifact 写入迁移到 RunStore

状态：**已完成**。

---

## T004：Run listing/query API v1

状态：**已完成**。

---

## T005：DB-backed Agent events v1

状态：**已完成**。

---

# Phase B：分布式控制与限流

## T006：Distributed quota/rate limit backend interface

状态：**已完成**。

---

## T007：Worker lease / claim run v1

状态：**已完成**。

---

## T008：PostgresRunStore interface scaffold v1

状态：**已完成**。

---

## T009：Real PostgresRunStore persistence v1

状态：**已完成**。

边界：真实 Postgres store 完成不等于 migration runner、连接池、完整 worker queue 或生产部署完成。

---

## T010：Postgres migration runner / connection pool profile v1

状态：**已完成**。

完成内容：`PostgresConnectionProfile`、lazy `psycopg_pool.ConnectionPool`、`close()`、SQL statement splitter、`init_db(sql_path=...)`、`scripts/apply_postgres_run_store_migration.py`、`configs/run_store/postgres.example.env`、pool dependency、测试、文档、状态同步。

状态标记：

```text
P1_postgres_run_store_migration_runner_implemented_v1 = true
```

边界：migration runner/connection config 完成不等于 schema migration history、完整生产运维平台或 worker queue。

---

# Phase C：Provider 原生能力

## T011：provider-native bidirectional continuation adapter v1

目标：实现真正 provider-native same-stream tool result continuation 的第一个 adapter。

建议策略：优先做 OpenAI-compatible 的可扩展接口；如果当前 API 不支持真正同一条流内回灌，则只做 provider-specific adapter scaffold 和测试 double。

建议文件：

```text
providers/base.py
providers/openai_compatible.py
providers/realtime_base.py
agent/tool_loop.py
tests/test_provider_continuation.py
tests/test_agent_tool_loop.py
docs/p1_provider_adapter.md
docs/p1_agent_runtime.md
```

状态标记：

```text
P1_provider_native_bidirectional_continuation_adapter_implemented_v1 = true
```

---

## T012：secret-gated real provider smoke tests v1

目标：增加真实 provider 的 smoke test profile，使用 secrets/env gate，默认 CI 不运行真实请求。

建议文件：

```text
requirements/provider-smoke.txt
scripts/provider_smoke_test.py
tests/test_provider_smoke_config.py
.github/workflows/foundation-provider-smoke.yml
docs/p1_provider_adapter.md
docs/implementation_status.md
```

状态标记：

```text
P1_secret_gated_provider_smoke_tests_implemented_v1 = true
```

### T013 — Postgres/distributed quota backend v1

Status: completed. Added optional Postgres quota persistence with schema migration, optional dependency profile, backend aliases (`postgres`, `postgresql`, `pg`), DSN environment variable `FOUNDATION_QUOTA_POSTGRES_DSN`, and DSN-gated tests. Core CI should continue using file/SQLite paths and must not require a live Postgres service.

Scope boundary: persistence v1 only; not full billing, global distributed limiter, or production billing.
