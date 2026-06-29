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
python -m unittest tests.test_foundation_core_services tests.test_memory_store tests.test_rule_engine tests.test_auth_service tests.test_auth_audit_rate_limit tests.test_usage_reconciliation tests.test_model_tool_loop_usage tests.test_provider_continuation tests.test_run_store tests.test_sqlite_run_store tests.test_ci_profiles tests.test_workspace_quota tests.test_skill_registry tests.test_mcp_adapter
```

如果改到 API server，再跑：

```bash
python -m unittest tests.test_api_server_foundation
```

如果改到 Agent runtime/tool loop，再跑：

```bash
python -m unittest tests.test_agent_runtime tests.test_agent_lifecycle tests.test_agent_events tests.test_agent_tool_loop tests.test_run_store tests.test_sqlite_run_store
```

禁止误判：RunStore/SQLite/API/run listing 都是阶段性能力，不等于 Postgres、分布式任务队列、DB-backed SSE、全文搜索或生产级调度已完成。

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
P1_agent_lifecycle_resume_cancel_retry_implemented_v1 = true
P1_agent_lifecycle_api_endpoints_implemented_v1 = true
P1_agent_run_store_abstraction_implemented_v1 = true
P1_sqlite_run_store_implemented_v1 = true
P1_agent_lifecycle_run_store_selection_implemented_v1 = true
P1_agent_runtime_run_store_writes_implemented_v1 = true
P1_agent_run_listing_query_implemented_v1 = true
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

支持 filters：

```text
status
owner_id
project_id
workspace_id
parent_run_id
query
limit
offset
order
```

状态标记：

```text
P1_agent_run_listing_query_implemented_v1 = true
```

边界：run listing/query 完成不等于 DB-backed events、Postgres、全文搜索系统或分布式任务队列完成。

---

## T005：DB-backed Agent events v1

### 目标

让 Agent events API 可从 selected run store 读取；SQLite 下优先读取 `run_events` 表，SSE 也能轮询 DB events。

### 新增/修改文件

```text
agent/run_store.py
agent/sqlite_run_store.py
agent/events.py
inference/api_server.py
tests/test_sqlite_run_store.py
tests/test_agent_events.py
tests/test_api_server_foundation.py
docs/p1_agent_run_store.md
docs/p1_agent_runtime.md
docs/p1_api_server_integration.md
docs/implementation_status.md
```

### 验收标准

- SQLite store 下 event 写入 `run_events` 表。
- `GET /v1/agent/events` 能读取 selected store events。
- SSE 能轮询 DB events，并保持 file store 行为不破坏。
- OpenAPI 如有字段变化需要同步。

### 状态更新

```text
P1_db_backed_agent_events_implemented_v1 = true
```

### 边界

完成后仍不是生产级分布式事件总线，也不是 WebSocket 系统。

---

# Phase B：分布式控制与限流

## T006：Distributed quota/rate limit backend interface

目标：为 quota/rate limit 增加 backend 抽象，先支持 file 和 sqlite。

建议文件：

```text
services/rate_limiter.py
services/workspace_quota.py
services/quota_store.py
tests/test_workspace_quota.py
tests/test_auth_audit_rate_limit.py
docs/p1_workspace_quota.md
docs/p1_auth_api_keys.md
```

状态标记：

```text
P1_sqlite_quota_rate_limit_backend_implemented_v1 = true
```

---

## T007：Worker lease / claim run v1

目标：为分布式 Agent worker 打基础，支持 run claim 和 lease。

功能：

```text
claim_run(run_id, worker_id, lease_seconds)
renew_lease(run_id, worker_id)
release_run(run_id, worker_id)
find_expired_leases()
```

状态标记：

```text
P1_agent_worker_lease_implemented_v1 = true
```

边界：完成后仍不是完整任务队列，只是 worker lease 基础。

---

# Phase C：Provider 原生能力

## T008：provider-native bidirectional continuation adapter v1

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
