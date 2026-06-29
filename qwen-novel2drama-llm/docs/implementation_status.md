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

### P0/P1/P2 底座工程契约

- 统一 content block、错误码、response envelope schema。
- 模型能力注册表、模型实例注册表、模型路由策略契约。
- OpenAPI 规格已同步当前 `/v1/*` runtime endpoints。
- OpenAPI/runtime 合同检查脚本与默认 CI workflow。
- CI profiles 已覆盖 contracts、core、provider adapter、provider smoke、API server、Postgres run store、Postgres quota、本地模型导入检查。
- P2 provider catalog、resilience、multimodal routing、MCP SDK compatibility、eval、tracing、audit query、deploy profile 已补齐。

### P1 底座核心服务 v1

- router、token counter、cost estimator、usage ledger、provider usage reconciliation。
- model tool loop usage aggregation。
- memory store、rule engine、skills registry、MCP-style adapter。
- auth、audit、rate limit。
- file/SQLite/Postgres quota backend。
- Agent events、run store、SQLiteRunStore、PostgresRunStore persistence v1、lifecycle、runtime、tool loop。
- `agent/worker_dispatcher.py`：支持 queued run enqueue/list/dispatch/loop、worker lease claim/release、attempt tracking 和 dead-letter。
- `agent/worker_pool.py`：支持 worker pool loop、idle stop、multi-worker dispatcher iteration。
- `agent/postgres_migration_history.py`：支持 `schema_migrations`、migration checksum、幂等记录和 checksum 冲突检测。
- `providers/realtime_base.py`：支持 provider-native continuation test double、OpenAI Responses continuation adapter、OpenAI Realtime session adapter。
- `scripts/provider_smoke_test.py` 与 `.github/workflows/foundation-provider-smoke.yml`：provider smoke config/dry-run profile。
- `inference/api_server.py`：支持 API-level workspace quota middleware、`/v1/ready`、`/v1/health/deep`、`/v1/agent/queue`。
- `services/secret_resolver.py`：支持 env/file/literal secret references，默认拒绝 raw secret。
- `services/metrics.py`：支持 Prometheus-style metrics rendering contract。
- `scripts/postgres_backup.py`：支持 Postgres backup/restore planning 和显式执行入口，不打印 DSN。
- `scripts/production_preflight.py`：支持生产 hardening 文件、flag、env 模板预检。
- `Dockerfile`、`compose.production.yml`、`configs/deploy/production.example.env`、`configs/deploy/nginx.tls.example.conf`：生产化部署 profile、worker profile、preflight profile、TLS reverse proxy template。
- `providers/session_lifecycle.py`：provider session lifecycle 状态机和 health contract。
- `agent/postgres_db_ops.py`：forward migration plan、manual rollback plan、DB ops health。
- `services/billing_limits.py`：billing/global rate-limit readiness helpers。

### P2 底座增强 v1

- `providers/provider_catalog.py`：DeepSeek、Qwen/DashScope、Anthropic、Gemini provider catalog 和 instance template。
- `providers/resilience.py`：retry、fallback、circuit breaker、provider health scoring。
- `services/multimodal_router.py`：多模态 input modality 推断、candidate filtering、route plan。
- `mcp/sdk_compat.py`：MCP initialize/list/call request shape、tool schema normalize、session transition。
- `evals/eval_runner.py` 与 `evals/golden/foundation_smoke.json`：golden eval runner 和 smoke dataset。
- `services/tracing.py`：trace/span lifecycle、JSONL persistence、summary。
- `services/audit_query.py`：workspace-level audit query、export、retention filter。
- `scripts/deploy_profile.py` 与 `.github/workflows/foundation-deploy-profile.yml`：deploy profile validator 和 CI workflow。

### 测试与文档

- Run store、SQLite run store、Postgres run store contract/migration runner/history、worker dispatcher/pool、provider catalog/resilience、multimodal router、MCP SDK compat、eval runner、tracing、audit query、deploy profile、provider continuation/session adapters、provider smoke config、Agent events、Agent runtime、Agent lifecycle、API server、auth、audit/rate limit、workspace quota、quota store、Postgres quota、hardening helpers、metrics、secret resolver、production preflight、skills、MCP 等测试已补充。
- `docs/p1_agent_run_store.md`
- `docs/p1_provider_adapter.md`
- `docs/p1_api_server_integration.md`
- `docs/p1_workspace_quota.md`
- `docs/p1_hardening.md`
- `docs/p2_foundation.md`
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
P1_postgres_distributed_quota_backend_implemented_v1 = true
P1_api_middleware_quota_checks_implemented_v1 = true
P1_production_deployment_profile_implemented_v1 = true
P1_health_readiness_checks_implemented_v1 = true
P1_pool_health_checks_implemented_v1 = true
P1_queue_observability_implemented_v1 = true
P1_provider_session_lifecycle_hardening_implemented_v1 = true
P1_db_ops_rollback_planning_implemented_v1 = true
P1_billing_global_limit_hardening_implemented_v1 = true
P1_secret_management_contract_implemented_v1 = true
P1_metrics_exporter_contract_implemented_v1 = true
P1_worker_pool_supervisor_implemented_v1 = true
P1_backup_restore_automation_contract_implemented_v1 = true
P1_production_preflight_implemented_v1 = true
P1_tls_reverse_proxy_template_implemented_v1 = true
P2_multi_provider_catalog_implemented_v1 = true
P2_provider_resilience_fallback_retry_circuit_breaker_implemented_v1 = true
P2_multimodal_routing_contract_implemented_v1 = true
P2_mcp_sdk_compat_layer_implemented_v1 = true
P2_eval_system_implemented_v1 = true
P2_observability_tracing_implemented_v1 = true
P2_audit_query_export_retention_implemented_v1 = true
P2_deploy_profile_ci_implemented_v1 = true
P1_provider_smoke_runner_profile_implemented_v1 = true
P1_secret_gated_provider_smoke_tests_implemented_v1 = true
P1_agent_worker_lease_implemented_v1 = true
P1_worker_queue_dispatcher_implemented_v1 = true
P1_postgres_run_store_scaffold_implemented_v1 = true
P1_postgres_run_store_persistence_implemented_v1 = true
P1_postgres_run_store_migration_runner_implemented_v1 = true
P1_postgres_run_store_migration_history_implemented_v1 = true
P1_provider_native_bidirectional_continuation_adapter_implemented_v1 = true
P1_real_provider_native_session_adapters_implemented_v1 = true
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

1. P3 AI 短剧/漫剧专项能力。
2. Kubernetes / Terraform。
3. AWS/GCP/Azure/Vault managed secret manager。
4. 真实证书、域名、WAF、CDN。
5. Prometheus/Grafana/SLO 告警部署。
6. 真实备份策略和 RPO/RTO 演练。
7. 外部 MQ / 跨区域调度。
8. 真实 billing invoice import/export integrations。

## 后续开发顺序

1. P3：AI 短剧/漫剧专项能力。
2. Cloud deployment specialization：Kubernetes/Terraform/managed secrets/managed backups/WAF/CDN/SLO。
3. External integrations：外部 MQ、跨区域调度、真实 billing invoice import/export。

## 禁止误判

- P2 provider catalog 完成，不等于所有 provider 已经配置真实可调用 key/base URL。
- Provider resilience policy 完成，不等于所有 runtime 调用路径都已强制接入 fallback engine。
- Multimodal routing contract 完成，不等于所有图像/音频/视频 provider SDK 都已真实打通。
- MCP SDK compatibility layer 完成，不等于已经通过官方 SDK 的所有端到端互操作测试。
- Eval runner 完成，不等于已有大规模 golden dataset 或自动质量门禁。
- Tracing contract 完成，不等于 Grafana/Prometheus/SLO 告警体系已经部署。
- Audit query/export 完成，不等于合规归档系统或 SIEM 已接入。
- Deploy profile CI 完成，不等于 Kubernetes/Terraform/云平台生产部署已完成。
- Repository-level hardening 完成，不等于已经部署到某个云平台生产环境。
- 训练 runbook 不等于模型已经训练完成。
