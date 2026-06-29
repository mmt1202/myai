# 实现状态

这个文件用于区分项目已经能跑的部分、已经完成研究但尚未工程化的部分，以及还需要继续开发的部分。

当前项目长期定位是：**可部署、可扩展、可观测、可审计、可路由、可控成本的 AI 大模型底座**。

AI 短剧/漫剧不是当前要先做的应用平台，而是这个大模型底座的长期特色能力方向之一。未来短剧/漫剧平台、代码工具、桌面端或其他产品可以使用这个底座，但底座本身必须先解决模型能力、推理、多模态、token、成本、记忆、规则、Skills、MCP、Agent、API、评测和部署问题。

## 已经能跑

### P0 文本生成基础运行时

- `inference/model_utils.py`：文本模型加载、一次性生成与 transformers TextIteratorStreamer 流式生成入口。
- `configs/model_registry.json`：基础模型运行时注册表。
- `scripts/inspect_model_registry.py`：查看模型运行时注册表。
- `scripts/plan_training_run.py`：生成训练运行 manifest。
- `scripts/register_model_version.py`：登记训练后的模型版本。
- `inference/api_server.py`：可从 active model version 启动 API。

### P0/P1 底座工程契约

- `configs/schemas/content_block_schema.json`：统一多模态 content block schema。
- `configs/schemas/error_code_schema.json`：统一错误码 schema。
- `configs/schemas/response_envelope_schema.json`：统一响应 envelope schema。
- `configs/model_capability_registry.json`：模型能力注册表。
- `configs/model_instance_registry.json`：模型实例注册表。
- `configs/model_router.yaml`：模型路由策略契约。
- `openapi/foundation_api.openapi.yaml`：Foundation API OpenAPI 规格，已同步当前运行时 `/v1/*` endpoints、API key security scheme、ProviderStreamEvent、ProviderToolCall、Agent lifecycle schema、Agent event schema、Agent run listing schema、model tool loop、stream provider tool bridge、incremental stream tool execution、same-stream continuation fallback events 和 workspace quota 字段。
- `scripts/check_openapi_contract.py`：OpenAPI/runtime 合同一致性检查脚本，已覆盖 `GET /v1/agent/runs`。
- `scripts/ci_profiles.py`：CI dependency/test profile 映射脚本。
- `.github/workflows/foundation-contract-check.yml`：默认 OpenAPI/runtime 合同检查与轻量核心测试 CI workflow。
- `.github/workflows/foundation-optional-profiles.yml`：可手动触发的 provider/API/local-model optional/heavyweight profile workflow。
- `requirements/ci-core.txt`：无三方依赖核心 CI profile。
- `requirements/provider-adapter.txt`：Provider adapter CI profile。
- `requirements/api-server.txt`：API server CI profile。
- `requirements/local-model.txt`：torch/transformers/peft 本地模型重依赖 profile。
- `requirements/dev.txt`：开发依赖 profile。

### P1 底座核心服务 v1

- `inference/model_router.py`：基于能力、模态、隐私、上下文窗口和 route mode 的模型路由器。
- `services/token_counter.py`：统一 request token 与多模态 billable unit 估算。
- `services/cost_estimator.py`：基于模型实例价格元数据的成本估算。
- `services/usage_ledger.py`：JSONL usage ledger 与汇总。
- `services/usage_reconciliation.py`：provider 实际 usage/cost 与路由预估 usage/cost 的对账服务。
- `services/model_tool_loop_usage.py`：model tool loop 多轮 provider 调用 usage/cost 聚合服务。
- `services/workspace_quota.py`：workspace daily/monthly requests、token、cost 配额检查与文件状态入账服务。
- `services/memory_store.py`：分层记忆服务。
- `services/rule_engine.py`：确定性规则评估服务。
- `services/auth.py`：API key、scope、workspace 校验服务，已覆盖 Agent lifecycle API 与 Agent run listing API scope。
- `services/auth_audit.py`：auth/API 请求审计事件 JSONL 写入与汇总。
- `services/rate_limiter.py`：文件状态版 API key/scope/workspace 限流服务。
- `agent/events.py`：Agent run JSONL 事件流写入、读取与汇总；已支持在 SQLite run store 选中时同步 append 到 `run_events` 表。
- `agent/run_store.py`：Agent run store 抽象、`FileRunStore`、`build_run_store()`、artifact index 接口与 `list_runs(...)`，支持 file/sqlite 选择、轻量 run query 和 selected store event reads。
- `agent/sqlite_run_store.py`：本地 SQLite Agent run store v1，使用标准库 `sqlite3` 持久化 runs、requests、reports、events、cancel markers 和 artifact index，并支持 `list_runs(...)` 与 DB-backed `load_events(...)`。
- `agent/runtime.py`：通用 Agent run/session/step 状态机、事件流、审批门、skill loop、provider execution、stream provider tool bridge、incremental stream tool execution、provider usage reconciliation、workspace quota preflight/actual recording、取消 checkpoint 与 model tool loop 运行时；已支持可选 run store 写入 request/report/artifact index/event index、实时 DB-backed event append，并可读取 store cancel marker。
- `agent/lifecycle.py`：Agent status、cancel、retry、resume 生命周期控制 CLI 与服务函数，已支持 `--run-store file|sqlite`、`--sqlite-path`，并将 retry/resume 子 run 通过选定 store 写入 runtime。
- `agent/tool_loop.py`：模型返回 tool calls 后的工具解析、skill 执行、tool_result 回填、多轮 provider 调用、provider stream chunks 到 provider response 的桥接、完整 partial tool call 的增量执行、多轮 provider usage/cost 聚合 artifact 写入，以及 same-stream continuation fallback events。
- `providers/base.py`：Provider adapter 基础合同，已包含 ProviderStreamEvent 标准 chunk 结构、fallback stream_generate、continuation capability 与 same-stream continuation hook。
- `providers/openai_compatible.py`：OpenAI-compatible chat completions provider adapter，已支持原生 `stream=true` SSE 解析、`data: [DONE]` 结束、usage 合并、provider stream chunk 输出和 streamed tool-call delta reconstruction。
- `providers/local_text.py`：本地 transformers 文本 provider adapter，已接入现有 `inference/model_utils.py`，并具备进程内缓存、加载锁、生成串行保护、cache stats、clear cache 和 stream_generate。
- `providers/factory.py`：按模型实例构造 provider 的工厂，已支持 OpenAI-compatible、local transformers、`stream_generate_with_registry`、continuation capability 查询和 continuation hook 调用入口。
- `skills/registry.py`：Foundation Skills 注册表和调用入口。
- `mcp/adapter.py`：Foundation Skills 到 MCP-style tools/resources/prompts 的适配器。
- `inference/api_server.py`：统一 Foundation `/v1/*` API server 集成，已接入 auth、audit、rate limit middleware、Agent events selected store JSON/SSE endpoint、Agent lifecycle status/cancel/retry/resume endpoints、`GET /v1/agent/runs`、file/sqlite Agent run store 选择和 `/v1/chat` provider SSE streaming。

### 测试与文档

- `tests/test_run_store.py`：Agent run store 抽象、`FileRunStore`、run store factory 与 file-backed run listing 测试。
- `tests/test_sqlite_run_store.py`：SQLiteRunStore schema、request/report、event、cancel marker、status、artifact index 与 SQLite run listing 测试。
- `tests/test_agent_events.py`：Agent event JSONL、summary、SQLite event append 与 runtime DB-backed event 写入测试。
- `tests/test_agent_runtime.py`：Agent runtime、stream provider tool bridge、incremental stream tool execution、provider usage reconciliation、workspace quota 与 run store writes 测试。
- `tests/test_agent_lifecycle.py`：Agent status/cancel/retry/resume 生命周期测试，已覆盖 SQLite store 注入。
- `tests/test_api_server_foundation.py`：Foundation API server、provider streaming、Agent lifecycle API、Agent runs API、DB-backed Agent events 与 SQLite run store 选择测试。
- `tests/test_auth_service.py`：Auth 服务与 Agent lifecycle/run listing scope 测试。
- `docs/p1_agent_run_store.md`：Agent run store 抽象、SQLite store、file/sqlite 选择、run listing/query 和 DB-backed events 说明。
- `docs/p1_agent_runtime_run_store_writes.md`：Agent runtime run store writes 说明。
- `docs/p1_api_server_integration.md`：API server 集成、run store 选择、Agent runs API、DB-backed Agent events 与 Agent lifecycle API 说明。

## 已完成研究并已开始工程化

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

P0/P1 已经把核心研究结果转成第一版工程契约和一批可运行服务；OpenAPI 已同步当前 FastAPI runtime，API server 已接入轻量 API key/workspace scope、auth audit、文件状态限流、Agent selected store JSON/SSE 事件接口、Agent lifecycle status/cancel/retry/resume API、Agent run listing API、file/sqlite Agent run store 选择和 provider SSE streaming；Agent runtime 已能在传入 run store 时写入 request/report/artifact index/event index，并在 SQLite 模式下实时 append events 到 `run_events` 表；Agent lifecycle 已可通过 `FileRunStore` 或 `SQLiteRunStore` 读写 request/report/cancel marker；`FileRunStore` 与 `SQLiteRunStore` 都已支持轻量 `list_runs(...)`。下一步应继续实现 Postgres run store、distributed quota backend 或 provider-native bidirectional adapter。

## 当前最重要的未完成项

### P1：底座核心服务剩余项

1. 增加 Postgres run store 实现。
2. 增加 provider-native bidirectional continuation adapter。
3. 增加分布式 quota/rate limit backend。
4. 增加 secret-gated real provider smoke tests。

### P2：Provider 接入与生产化

1. Qwen/DeepSeek/GLM/Gemini/Claude provider adapters。
2. 图片、视频、音频、ASR、TTS provider adapters。
3. OTel tracing。
4. Audit log。
5. Usage ledger reconciliation。
6. Evaluation suite。
7. Deployment profiles。
8. Deprecation watcher。
9. Region/data-residency routing。

## 后续开发顺序

1. P1：继续实现 Postgres run store、provider-native bidirectional continuation adapter、distributed quota backend、secret-gated provider smoke profiles。
2. P2：接入多 provider、多模态生成/理解、MCP SDK 兼容层、评测、观测、审计、部署。
3. P3：加强 AI 短剧/漫剧专项模型能力，包括故事理解、集数规划、角色一致性、分镜规划、视觉提示词生成、短剧质检评测。

## 禁止误判

- 不能把“DB-backed Agent events 完成”说成“分布式事件总线、WebSocket、Postgres run store 或生产级任务队列完成”。
- 不能把“Agent run listing/query 完成”说成“Postgres run store、全文搜索系统或分布式任务队列完成”。
- 不能把“Agent runtime run store writes 完成”说成“Postgres run store 或分布式任务队列完成”。
- 不能把“Agent run store selection 完成”说成“Postgres run store、分布式任务队列或事务型调度完成”。
- 不能把“SQLiteRunStore 完成”说成“Postgres/distributed run store 完成”。
- 不能把“Agent lifecycle API 完成”说成“数据库 run store、分布式任务队列或强制中断 provider 进程完成”。
- 不能把“same-stream continuation contract 完成”说成“所有 provider 都已支持同一条流内回灌 tool result”。
- 不能把“CI dependency profiles 完成”说成“真实 provider smoke tests 或 GPU 模型加载 CI 完成”。
- 不能把“本地 provider adapter 完成”说成“所有 provider 已接入”。
- 不能把“AI 短剧能力矩阵”说成“AI 短剧平台已经完成”。
- 不能把“训练 runbook”说成“模型已经训练完成”。
