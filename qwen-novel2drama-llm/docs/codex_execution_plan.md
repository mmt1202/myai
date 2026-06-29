# Codex 连续执行任务总控文档

本文档用于让 Codex 按顺序继续完成 `qwen-novel2drama-llm` 的剩余工程任务。

当前项目定位：**可部署、可扩展、可观测、可审计、可路由、可控成本的 AI 大模型底座**。

AI 短剧/漫剧是长期特色方向，不是当前优先完成的完整应用平台。当前优先级是继续补齐底座的运行时、存储、Provider、CI、观测、部署和评测能力。

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

如果改到 API server，再跑：

```bash
python -m unittest tests.test_api_server_foundation
```

如果改到 Agent runtime/tool loop，再跑：

```bash
python -m unittest tests.test_agent_runtime tests.test_agent_lifecycle tests.test_agent_events tests.test_agent_tool_loop tests.test_run_store tests.test_sqlite_run_store
```

禁止误判：RunStore/SQLite/API/run listing/DB-backed events/SQLite quota backend/worker lease/Postgres scaffold 都是阶段性能力，不等于真实 Postgres persistence、分布式任务队列、分布式事件总线、WebSocket、全文搜索、全局限流或生产级调度已完成。

---

## 1. 当前已完成基线

以下状态已经完成，后续任务不要重复实现，只能在其基础上扩展：

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

完成内容：`SQLiteRunStore`、SQLite schema、request/report/event/cancel/artifact index、测试、文档、状态同步。

边界：SQLiteRunStore 完成不等于 Postgres/distributed run store 完成。

---

## T002：Agent lifecycle 支持 run_store 配置选择

状态：**已完成**。

完成内容：`build_run_store()`、CLI `--run-store file|sqlite`、API 环境变量 `FOUNDATION_AGENT_RUN_STORE` / `FOUNDATION_AGENT_RUN_DB`、测试、文档、状态同步。

边界：run store selection 完成不等于 runtime artifact 全量 DB 写入、Postgres 或分布式任务队列完成。

---

## T003：Agent runtime artifact 写入迁移到 RunStore

状态：**已完成**。

完成内容：`run_agent_once(..., store=...)`、request/report/created_run/artifact index/event index 写入、store cancel marker 读取、retry/resume 子 run 传入同一 store、测试、文档、状态同步。

边界：runtime run store writes 完成不等于 DB-backed events、Postgres run store 或分布式任务队列完成。

---

## T004：Run listing/query API v1

状态：**已完成**。

完成内容：`RunStore.list_runs(...)`、`FileRunStore.list_runs(...)`、`SQLiteRunStore.list_runs(...)`、`GET /v1/agent/runs`、OpenAPI、auth scope、测试、文档、状态同步。

状态标记：

```text
P1_agent_run_listing_query_implemented_v1 = true
```

边界：run listing/query 完成不等于 DB-backed events、Postgres、全文搜索系统或分布式任务队列完成。

---

## T005：DB-backed Agent events v1

状态：**已完成**。

完成内容：`AgentEventWriter(..., store=...)` 在 SQLite 模式下实时 append 到 `run_events` 表；`GET /v1/agent/events` 和 SSE 轮询都从 selected run store 读取；file store 仍读取 JSONL；测试、文档、状态同步。

状态标记：

```text
P1_db_backed_agent_events_implemented_v1 = true
```

边界：DB-backed Agent events 完成不等于生产级分布式事件总线、WebSocket、Postgres 或任务队列完成。

---

# Phase B：分布式控制与限流

## T006：Distributed quota/rate limit backend interface

状态：**已完成**。

完成内容：`services/quota_store.py`、`FileQuotaStore`、`SQLiteQuotaStore`、rate limit backend 接入、workspace quota backend 接入、`FOUNDATION_QUOTA_BACKEND=file|sqlite`、`FOUNDATION_QUOTA_DB=...`、测试、文档、状态同步。

状态标记：

```text
P1_sqlite_quota_rate_limit_backend_implemented_v1 = true
```

边界：SQLite quota/rate limit backend 完成不等于 Postgres/distributed quota、全局限流或完整账单系统完成。

---

## T007：Worker lease / claim run v1

状态：**已完成**。

完成内容：`RunStore.claim_run(...)`、`renew_lease(...)`、`release_run(...)`、`find_expired_leases(...)`、FileRunStore `worker_lease.json` 兼容实现、SQLiteRunStore `run_leases` 表、lifecycle CLI `claim/renew-lease/release/expired-leases`、测试、文档、状态同步。

状态标记：

```text
P1_agent_worker_lease_implemented_v1 = true
```

边界：Worker lease 完成不等于完整任务队列、分布式调度器或自动 worker pool 完成。

---

## T008：PostgresRunStore interface scaffold v1

状态：**已完成**。

完成内容：`agent/postgres_run_store.py`、`PostgresRunStore` scaffold、`build_run_store("postgres")`、`--run-store postgres`、`FOUNDATION_AGENT_RUN_POSTGRES_DSN` 配置入口、dependency-free scaffold 测试、文档、状态同步。

状态标记：

```text
P1_postgres_run_store_scaffold_implemented_v1 = true
```

边界：scaffold 完成不等于真实 Postgres persistence、migration、连接池或生产部署完成。

---

## T009：Real PostgresRunStore persistence v1

目标：把 T008 scaffold 变成真实 Postgres 持久化实现。

建议文件：

```text
agent/postgres_run_store.py
requirements/postgres-run-store.txt
.github/workflows/foundation-optional-profiles.yml
scripts/ci_profiles.py
tests/test_postgres_run_store_contract.py
docs/p1_agent_run_store.md
docs/implementation_status.md
```

验收标准：

- 使用可选依赖 profile，不进入 core CI。
- 支持 requests/reports/events/cancel/artifact/lease 读写。
- 支持 list_runs filters/pagination。
- 支持 claim/renew/release 的数据库级原子语义。
- 没有 DSN 时测试自动 skip 或只跑 contract double。

状态标记：

```text
P1_postgres_run_store_persistence_implemented_v1 = true
```

边界：真实 Postgres store 完成不等于完整 worker queue 或全生产部署完成。

---

# Phase C：Provider 原生能力

## T010：provider-native bidirectional continuation adapter v1

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
