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
- CI profiles 已覆盖 contracts、core、provider adapter、API server、本地模型导入检查。

### P1 底座核心服务 v1

- router、token counter、cost estimator、usage ledger、provider usage reconciliation。
- model tool loop usage aggregation。
- memory store、rule engine、skills registry、MCP-style adapter。
- auth、audit、rate limit。
- `services/quota_store.py`：file/SQLite quota backend 抽象，覆盖 rate limit bucket、workspace usage 和 quota events。
- `services/rate_limiter.py`：支持 file/SQLite backend，默认 file。
- `services/workspace_quota.py`：支持 file/SQLite backend，默认 file。
- Agent events、run store、SQLiteRunStore、lifecycle、runtime、tool loop。
- provider base、OpenAI-compatible provider、本地 text provider、provider factory。
- API server 已接入 auth/audit/rate limit、Agent lifecycle、Agent run listing、selected store events、provider SSE streaming。

### 测试与文档

- Run store、SQLite run store、Agent events、Agent runtime、Agent lifecycle、API server、auth、audit/rate limit、workspace quota、quota store、skills、MCP 等测试已补充。
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
P1_router_token_cost_usage_memory_rules_agent_runtime_provider_adapter_skills_mcp_adapter_api_server_agent_provider_execution_agent_skill_loop_implemented_v1 = true
runtime_services_completed = partially
implementation_completed = false
```

## 当前最重要的未完成项

1. Postgres run store。
2. Worker lease / claim run。
3. provider-native bidirectional continuation adapter。
4. secret-gated real provider smoke tests。
5. Postgres/distributed quota backend。

## 后续开发顺序

1. P1：Postgres run store、worker lease、provider-native bidirectional continuation、secret-gated provider smoke profiles、Postgres/distributed quota backend。
2. P2：多 provider、多模态生成/理解、MCP SDK 兼容层、评测、观测、审计、部署。
3. P3：AI 短剧/漫剧专项能力，包括故事理解、集数规划、角色一致性、分镜规划、视觉提示词生成、短剧质检评测。

## 禁止误判

- SQLite quota/rate limit backend 完成，不等于 Postgres/distributed quota、全局限流或完整账单系统完成。
- DB-backed Agent events 完成，不等于分布式事件总线、WebSocket、Postgres run store 或生产级任务队列完成。
- Agent run listing/query 完成，不等于 Postgres run store、全文搜索系统或分布式任务队列完成。
- SQLiteRunStore 完成，不等于 Postgres/distributed run store 完成。
- Agent lifecycle API 完成，不等于数据库 run store、分布式任务队列或强制中断 provider 进程完成。
- same-stream continuation contract 完成，不等于所有 provider 都支持同一条流内回灌 tool result。
- 本地 provider adapter 完成，不等于所有 provider 已接入。
- AI 短剧能力矩阵不等于 AI 短剧平台完成。
- 训练 runbook 不等于模型已经训练完成。
