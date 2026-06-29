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
python -m unittest tests.test_foundation_core_services tests.test_memory_store tests.test_rule_engine tests.test_auth_service tests.test_auth_audit_rate_limit tests.test_usage_reconciliation tests.test_model_tool_loop_usage tests.test_provider_continuation tests.test_provider_session_lifecycle tests.test_run_store tests.test_sqlite_run_store tests.test_agent_lifecycle tests.test_worker_dispatcher tests.test_postgres_migration_history tests.test_postgres_db_ops tests.test_agent_events tests.test_ci_profiles tests.test_workspace_quota tests.test_quota_store tests.test_billing_limits tests.test_skill_registry tests.test_mcp_adapter
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

禁止误判：当前能力是 P1 foundation v1 + hardening v1，不等于完整生产部署、跨区域强一致调度、完整 billing、完整 WebRTC/SIP 接入或 AI 短剧平台已完成。

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
```

---

## T012：secret-gated real provider smoke tests v1

状态：**已完成**。

完成内容：`scripts/provider_smoke_test.py`、`requirements/provider-smoke.txt`、`tests/test_provider_smoke_config.py`、`.github/workflows/foundation-provider-smoke.yml`、CI profile、文档、状态同步。

边界：默认 CI 不发起真实 provider 调用，真实调用仍由环境配置显式启用。

---

## T013：Postgres/distributed quota backend v1

状态：**已完成**。

完成内容：`PostgresQuotaStore`、Postgres quota migration、optional dependency profile、DSN-gated tests、`build_quota_store(..., postgres_dsn=...)`、`FOUNDATION_QUOTA_BACKEND=postgres`。

边界：不是完整 billing、不是全局强一致分布式限流、不是生产级账单系统。

---

## T014：Worker queue / dispatcher v1

状态：**已完成**。

完成内容：`agent/worker_dispatcher.py`，支持 enqueue/list/dispatch/dispatch_loop、worker lease claim/release、attempt tracking 和 dead-letter。

边界：不是外部消息队列、不是跨区域分布式调度器、不是自动 worker pool。

---

## T015：Postgres schema version tracking / migration history table

状态：**已完成**。

完成内容：`agent/postgres_migration_history.py`、`schema_migrations` 表、migration checksum、幂等记录、checksum 冲突检测、runner 接入、`tests/test_postgres_migration_history.py`、文档。

边界：不是完整回滚系统、不是数据库运维治理平台。

---

## T016：Real provider-native session adapters

状态：**已完成**。

完成内容：`OpenAIResponsesContinuationAdapter` 和 `OpenAIRealtimeSessionContinuationAdapter`。Responses adapter 通过 `/responses` 追加 `function_call_output`；Realtime adapter 向调用方提供的 realtime session 注入 function-call output 并触发 response。

边界：Realtime adapter 需要调用方提供已打开的 realtime session；本项目仍未托管 WebRTC/SIP/browser audio 连接生命周期。

---

## H001-H008：P1 hardening v1

状态：**已完成**。

完成内容：

- H001：`inference/api_server.py` API-level workspace quota middleware。
- H002：`Dockerfile`、`compose.production.yml`、`configs/deploy/production.example.env`。
- H003：`/v1/ready`、`/v1/health/deep`。
- H004：readiness 中暴露 run store / Postgres pool metadata。
- H005：`/v1/agent/queue` queue observability。
- H006：`providers/session_lifecycle.py` provider session lifecycle contract。
- H007：`agent/postgres_db_ops.py` migration rollback/DB ops planning helpers。
- H008：`services/billing_limits.py` billing/global limit hardening helpers。

边界：hardening v1 不等于完整 secret manager、TLS、autoscaling、backup/restore automation、external MQ、billing reconciliation 或全球强一致限流。

---

## 下一阶段

1. P1 production hardening：secret manager integration、TLS/reverse proxy、backup/restore automation、metrics exporter、queue worker pool。
2. P2：多 provider、多模态生成/理解、MCP SDK 兼容层、评测、观测、审计、部署。
3. P3：AI 短剧/漫剧专项能力。
