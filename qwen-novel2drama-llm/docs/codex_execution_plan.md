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
python -m unittest tests.test_foundation_core_services tests.test_memory_store tests.test_rule_engine tests.test_auth_service tests.test_auth_audit_rate_limit tests.test_audit_query tests.test_usage_reconciliation tests.test_model_tool_loop_usage tests.test_provider_catalog_resilience tests.test_provider_continuation tests.test_provider_session_lifecycle tests.test_secret_resolver tests.test_multimodal_router tests.test_mcp_sdk_compat tests.test_eval_runner tests.test_tracing tests.test_deploy_profile tests.test_run_store tests.test_sqlite_run_store tests.test_agent_lifecycle tests.test_worker_dispatcher tests.test_worker_pool tests.test_postgres_migration_history tests.test_postgres_db_ops tests.test_agent_events tests.test_ci_profiles tests.test_workspace_quota tests.test_quota_store tests.test_billing_limits tests.test_metrics tests.test_production_preflight tests.test_skill_registry tests.test_mcp_adapter
```

API server profile:

```bash
python -m pip install -r requirements/api-server.txt
python -m unittest tests.test_api_server_foundation
```

Optional profiles:

```bash
python -m pip install -r requirements/postgres-run-store.txt
python -m unittest tests.test_postgres_run_store_contract
python -m pip install -r requirements/postgres-quota.txt
python -m unittest tests.test_postgres_quota_store
python -m unittest tests.test_provider_smoke_config
```

禁止误判：当前能力是 P1 foundation v1 + hardening v1 + P2 foundation v1，不等于完整云平台生产部署、跨区域强一致调度、完整 billing、完整 WebRTC/SIP 接入或 AI 短剧平台已完成。

---

## 1. 当前已完成基线

```text
P1_secret_gated_provider_smoke_tests_implemented_v1 = true
P1_postgres_distributed_quota_backend_implemented_v1 = true
P1_worker_queue_dispatcher_implemented_v1 = true
P1_postgres_run_store_migration_history_implemented_v1 = true
P1_real_provider_native_session_adapters_implemented_v1 = true
P1_api_middleware_quota_checks_implemented_v1 = true
P1_production_deployment_profile_implemented_v1 = true
P1_health_readiness_checks_implemented_v1 = true
P1_pool_health_checks_implemented_v1 = true
P1_queue_observability_implemented_v1 = true
P1_provider_session_lifecycle_hardening_implemented_v1 = true
P1_db_ops_rollback_planning_implemented_v1 = true
P1_billing_global_limit_hardening_implemented_v1 = true
P2_multi_provider_catalog_implemented_v1 = true
P2_provider_resilience_fallback_retry_circuit_breaker_implemented_v1 = true
P2_multimodal_routing_contract_implemented_v1 = true
P2_mcp_sdk_compat_layer_implemented_v1 = true
P2_eval_system_implemented_v1 = true
P2_observability_tracing_implemented_v1 = true
P2_audit_query_export_retention_implemented_v1 = true
P2_deploy_profile_ci_implemented_v1 = true
```

---

## T012-T016 / H001-H014

状态：**已完成**。

详见：

```text
docs/implementation_status.md
docs/p1_hardening.md
```

---

## P2-001：多 provider 接入

状态：**已完成**。

完成内容：`providers/provider_catalog.py`、`configs/model_instance_registry.json`。已覆盖 DeepSeek、Qwen/DashScope、Anthropic-compatible gateway、Gemini-compatible gateway 的 provider catalog 和 model instance template。

边界：真实调用仍需配置 provider base URL、model name、key env 和兼容网关。

---

## P2-002：Provider fallback / retry / circuit breaker

状态：**已完成**。

完成内容：`providers/resilience.py`。支持 retryable error 判断、退避延迟、circuit breaker 状态、provider health score、fallback candidate ranking。

边界：这是 policy/contract 层，不代表所有 runtime path 都已强制走 fallback engine。

---

## P2-003：多模态生成/理解 routing contract

状态：**已完成**。

完成内容：`services/multimodal_router.py`。支持 input modality 推断、output modality 选择、candidate filtering、normalized content block。

边界：真实图像/音频/视频 SDK 接入仍依赖具体 provider adapter。

---

## P2-004：MCP SDK 兼容层

状态：**已完成**。

完成内容：`mcp/sdk_compat.py`。支持 MCP initialize/list/call request shape、tool schema normalize、foundation tool schema conversion、session transition contract。

边界：不是官方 SDK 的所有端到端互操作认证。

---

## P2-005：评测系统 eval

状态：**已完成**。

完成内容：`evals/eval_runner.py`、`evals/golden/foundation_smoke.json`。支持 golden case load、score report、dependency-free eval runner。

边界：不是大规模 golden dataset 或自动质量门禁。

---

## P2-006：Observability / tracing

状态：**已完成**。

完成内容：`services/tracing.py`、`services/metrics.py`。支持 span lifecycle、JSONL persistence、trace summary、Prometheus-style metrics rendering contract。

边界：不是已部署 Grafana/Prometheus/SLO 告警体系。

---

## P2-007：Audit 查询与导出

状态：**已完成**。

完成内容：`services/audit_query.py`。支持 workspace/owner/decision/time-window query、JSONL export、retention filter。

边界：不是 SIEM 或合规归档平台。

---

## P2-008：部署体系 / deploy CI profile

状态：**已完成**。

完成内容：`scripts/deploy_profile.py`、`.github/workflows/foundation-deploy-profile.yml`、`docs/p2_foundation.md`。支持 repository-level deploy profile validation 和 production preflight CI。

边界：不是云平台专属部署。

---

## 明确未完成：云平台专项

这些按你的要求标记为**未完成**：

```text
Kubernetes / Terraform = not_completed
AWS/GCP/Azure/Vault secret manager = not_completed
真实证书、域名、WAF、CDN = not_completed
Prometheus/Grafana/SLO 告警部署 = not_completed
真实备份策略和 RPO/RTO 演练 = not_completed
外部 MQ / 跨区域调度 = not_completed
真实 billing invoice import/export = not_completed
```

---

## 下一阶段

1. P3：AI 短剧/漫剧专项能力。
2. 云平台专项：Kubernetes/Terraform/managed secrets/managed backups/WAF/CDN/SLO。
3. 外部集成：外部 MQ、跨区域调度、真实 billing invoice import/export。
