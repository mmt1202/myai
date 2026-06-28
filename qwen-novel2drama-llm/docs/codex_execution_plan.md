# Codex 连续执行任务总控文档

本文档用于让 Codex 按顺序继续完成 `qwen-novel2drama-llm` 的剩余工程任务。

当前项目定位：**可部署、可扩展、可观测、可审计、可路由、可控成本的 AI 大模型底座**。

AI 短剧/漫剧是长期特色方向，不是当前优先完成的完整应用平台。当前优先级是继续补齐底座的运行时、存储、Provider、CI、观测、部署和评测能力。

---

## 0. Codex 执行总规则

### 0.1 分支与提交

默认在当前仓库主项目目录执行：

```text
qwen-novel2drama-llm/
```

每个任务尽量独立提交，commit message 使用：

```text
Txxx: <short English summary>
```

示例：

```text
T001: Add SQLite run store
```

### 0.2 每个任务必须做的事

每完成一个任务，必须同步：

1. 代码实现。
2. 单元测试。
3. 文档。
4. `docs/implementation_status.md` 状态。
5. 必要时同步 OpenAPI。
6. 必要时同步 CI profile。

### 0.3 测试优先级

先跑轻量测试：

```bash
python scripts/check_openapi_contract.py
python -m unittest tests.test_openapi_contract_check tests.test_foundation_contracts
python -m unittest tests.test_foundation_core_services tests.test_memory_store tests.test_rule_engine tests.test_auth_service tests.test_auth_audit_rate_limit tests.test_usage_reconciliation tests.test_model_tool_loop_usage tests.test_provider_continuation tests.test_run_store tests.test_ci_profiles tests.test_workspace_quota tests.test_skill_registry tests.test_mcp_adapter
```

如果改到 API server，再跑：

```bash
python -m unittest tests.test_api_server_foundation
```

如果改到 Agent runtime/tool loop，再跑：

```bash
python -m unittest tests.test_agent_runtime tests.test_agent_lifecycle tests.test_agent_events tests.test_agent_tool_loop tests.test_run_store
```

如果改到 Provider，再跑：

```bash
python -m unittest tests.test_provider_adapter_contract tests.test_provider_factory tests.test_local_text_provider tests.test_provider_continuation
```

### 0.4 禁止误判

不能把阶段性工程能力说成完整生产系统。例如：

- RunStore 抽象完成 ≠ 数据库 run store 完成。
- SQLiteRunStore 完成 ≠ 分布式 Postgres run store 完成。
- Agent lifecycle API 完成 ≠ 分布式任务队列完成。
- same-stream continuation contract 完成 ≠ provider 已支持同一条流内回灌 tool result。
- CI profiles 完成 ≠ 真实 provider smoke test 完成。
- Provider adapter 完成 ≠ 所有 provider 都已接入。
- AI 短剧能力矩阵完成 ≠ AI 短剧平台完成。

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

### 目标

新增本地数据库版 Agent run store，用 Python 标准库 `sqlite3`，实现 `RunStore` 接口的 SQLite 版本。

### 建议新增/修改文件

```text
agent/sqlite_run_store.py
tests/test_sqlite_run_store.py
docs/p1_agent_run_store.md
docs/implementation_status.md
```

### 实现要求

新增：

```python
class SQLiteRunStore(RunStore):
    ...
```

支持表：

```text
runs
run_requests
run_reports
run_events
cancel_requests
run_artifacts
```

最少支持字段：

```text
runs: run_id, status, created_at, updated_at, completed_at, error
run_requests: run_id, request_json
run_reports: run_id, report_json
run_events: run_id, event_id, event_type, status, created_at, event_json
cancel_requests: run_id, marker_json, created_at
run_artifacts: run_id, name, path, artifact_json
```

### 验收标准

- `SQLiteRunStore` 通过和 `FileRunStore` 类似的接口测试。
- 支持 `save_request/load_request`。
- 支持 `save_report/load_report`。
- 支持 event 追加和读取。
- 支持 cancel marker 读写。
- 支持 `status(run_id)`。
- 缺失 run 抛 `RunNotFoundError` 或兼容异常。
- 不引入第三方依赖。

### 测试命令

```bash
python -m unittest tests.test_run_store tests.test_sqlite_run_store
```

### 状态更新

新增：

```text
P1_sqlite_run_store_implemented_v1 = true
```

### 边界

SQLiteRunStore 完成不等于 Postgres/distributed run store 完成。

---

## T002：Agent lifecycle 支持 run_store 配置选择

### 目标

让 CLI/API 可以选择 `file` 或 `sqlite` run store。

### 建议新增/修改文件

```text
agent/run_store.py
agent/sqlite_run_store.py
agent/lifecycle.py
inference/api_server.py
docs/p1_agent_run_store.md
docs/p1_api_server_integration.md
tests/test_agent_lifecycle.py
tests/test_api_server_foundation.py
```

### 实现要求

新增统一 factory：

```python
def build_run_store(kind: str, output_root: Path, *, sqlite_path: Path | None = None) -> RunStore:
    ...
```

CLI 支持：

```bash
python agent/lifecycle.py --run-store sqlite --sqlite-path outputs/agent_runtime/runs.sqlite status --run-id demo
```

API server 支持环境变量：

```text
FOUNDATION_AGENT_RUN_STORE=file|sqlite
FOUNDATION_AGENT_RUN_DB=outputs/agent_runtime/runs.sqlite
```

### 验收标准

- 默认仍是 file。
- 配置 sqlite 后 lifecycle API 使用 SQLiteRunStore。
- 不破坏已有 file-backed 测试。

### 测试命令

```bash
python -m unittest tests.test_agent_lifecycle tests.test_api_server_foundation tests.test_sqlite_run_store
```

### 状态更新

新增：

```text
P1_agent_lifecycle_run_store_selection_implemented_v1 = true
```

---

## T003：Agent runtime artifact 写入迁移到 RunStore

### 目标

让 `agent/runtime.py` 的核心 run artifact 写入走 RunStore 接口，而不是散落的直接文件写入。

### 建议修改文件

```text
agent/run_store.py
agent/runtime.py
agent/events.py
tests/test_agent_runtime.py
tests/test_run_store.py
docs/p1_agent_runtime.md
docs/p1_agent_run_store.md
docs/implementation_status.md
```

### 迁移范围

至少迁移：

```text
agent_request.json
agent_run_created.json
agent_run_report.json
events.jsonl
cancel_requested.json
```

后续 artifact 可保留文件路径，但要通过 store 记录索引：

```text
provider_response.json
usage_ledger.jsonl
provider_stream_chunks.jsonl
skill_results.json
model_tool_loop.json
workspace_quota_check.json
workspace_quota_usage.json
```

### 验收标准

- file store 下现有行为不变。
- SQLite store 下至少 request/report/events/cancel 能写入 DB。
- `run_agent_once` 可接收可选 store 或 store config。
- API server run/lifecycle 能共用同一个 store。

### 测试命令

```bash
python -m unittest tests.test_agent_runtime tests.test_agent_lifecycle tests.test_run_store tests.test_sqlite_run_store tests.test_api_server_foundation
```

### 状态更新

新增：

```text
P1_agent_runtime_run_store_writes_implemented_v1 = true
```

---

## T004：Run listing/query API v1

### 目标

为前端工作台提供 run 列表查询。

### 建议新增/修改文件

```text
agent/run_store.py
agent/sqlite_run_store.py
inference/api_server.py
openapi/foundation_api.openapi.yaml
scripts/check_openapi_contract.py
tests/test_api_server_foundation.py
tests/test_foundation_contracts.py
tests/test_openapi_contract_check.py
docs/p1_api_server_integration.md
docs/p1_agent_run_store.md
```

### 新增 API

```text
GET /v1/agent/runs
```

支持 query：

```text
workspace_id
owner_id
project_id
status
created_after
created_before
limit
offset
```

### 验收标准

- file store 可以简单扫描目录返回列表。
- sqlite store 可以用 SQL 查询。
- OpenAPI 同步。
- Auth scope 使用 `agent:run`。

### 状态更新

新增：

```text
P1_agent_run_listing_api_implemented_v1 = true
```

---

## T005：DB-backed Agent events v1

### 目标

让 SQLiteRunStore 支持 DB-backed event append/read，并让 Agent events API 可从 store 读取。

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
```

### 验收标准

- SQLite store 下 event 写入 `run_events` 表。
- `GET /v1/agent/events` 能读取 SQLite events。
- SSE 仍可轮询 DB events。
- file store 行为不破坏。

### 状态更新

新增：

```text
P1_db_backed_agent_events_implemented_v1 = true
```

---

# Phase B：分布式控制与限流

## T006：Distributed quota/rate limit backend interface

### 目标

为 quota/rate limit 增加 backend 抽象，先支持 file 和 sqlite。

### 建议文件

```text
services/rate_limiter.py
services/workspace_quota.py
services/quota_store.py
tests/test_workspace_quota.py
tests/test_auth_audit_rate_limit.py
docs/p1_workspace_quota.md
docs/p1_auth_api_keys.md
```

### 验收标准

- 默认 file backend 不变。
- 新增 SQLite backend。
- 支持原子更新 request/token/cost 计数。
- 支持 daily/monthly key。

### 状态更新

```text
P1_sqlite_quota_rate_limit_backend_implemented_v1 = true
```

---

## T007：Worker lease / claim run v1

### 目标

为分布式 Agent worker 打基础，支持 run claim 和 lease。

### 建议文件

```text
agent/run_store.py
agent/sqlite_run_store.py
agent/worker.py
tests/test_agent_worker.py
docs/p1_agent_run_store.md
```

### 功能

```text
claim_run(run_id, worker_id, lease_seconds)
renew_lease(run_id, worker_id)
release_run(run_id, worker_id)
find_expired_leases()
```

### 状态更新

```text
P1_agent_worker_lease_implemented_v1 = true
```

### 边界

完成后仍不是完整任务队列，只是 worker lease 基础。

---

# Phase C：Provider 原生能力

## T008：provider-native bidirectional continuation adapter v1

### 目标

实现真正 provider-native same-stream tool result continuation 的第一个 adapter。

### 建议策略

优先做 OpenAI-compatible 的可扩展接口，但如果当前 API 不支持真正同一条流内回灌，则只做 provider-specific adapter scaffold 和测试 double。

### 建议文件

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

### 验收标准

- 有一个 fake provider 能证明 `continue_stream_with_tool_result` 可追加 continuation events。
- unsupported provider 继续 fallback。
- supported provider 不写 unsupported event。
- tool_result continuation event 有审计 metadata。

### 状态更新

```text
P1_provider_native_bidirectional_continuation_adapter_implemented_v1 = true
```

### 边界

如果没有真实 provider 协议，不要声称真实远程 provider 已支持。

---

## T009：DeepSeek provider adapter v1

### 目标

接入 DeepSeek OpenAI-compatible provider。

### 文件

```text
providers/deepseek.py
providers/factory.py
configs/model_instance_registry.json
tests/test_deepseek_provider.py
docs/p1_provider_adapter.md
requirements/provider-adapter.txt
```

### 功能

- payload 构造。
- chat completions。
- streaming。
- tool calls。
- usage mapping。
- error normalization。
- dry run。

### 状态更新

```text
P2_deepseek_provider_adapter_implemented_v1 = true
```

---

## T010：Qwen provider adapter v1

### 目标

接入 Qwen/通义千问 provider。

### 文件

```text
providers/qwen.py
providers/factory.py
configs/model_instance_registry.json
tests/test_qwen_provider.py
docs/p1_provider_adapter.md
```

### 状态更新

```text
P2_qwen_provider_adapter_implemented_v1 = true
```

---

## T011：Claude provider adapter v1

### 目标

接入 Anthropic Claude Messages API。

### 文件

```text
providers/claude.py
providers/factory.py
configs/model_instance_registry.json
tests/test_claude_provider.py
docs/p1_provider_adapter.md
```

### 功能

- Messages payload。
- content block mapping。
- tool_use/tool_result mapping。
- streaming parser。
- usage mapping。
- error normalization。

### 状态更新

```text
P2_claude_provider_adapter_implemented_v1 = true
```

---

## T012：Gemini provider adapter v1

### 目标

接入 Gemini 多模态 provider。

### 文件

```text
providers/gemini.py
providers/factory.py
tests/test_gemini_provider.py
docs/p1_provider_adapter.md
```

### 状态更新

```text
P2_gemini_provider_adapter_implemented_v1 = true
```

---

## T013：GLM provider adapter v1

### 目标

接入智谱 GLM provider。

### 文件

```text
providers/glm.py
providers/factory.py
tests/test_glm_provider.py
docs/p1_provider_adapter.md
```

### 状态更新

```text
P2_glm_provider_adapter_implemented_v1 = true
```

---

# Phase D：真实 Provider CI 与 Smoke Test

## T014：Secret-gated provider smoke test framework

### 目标

新增真实 provider smoke test 框架，但没有 secret 时自动 skip。

### 文件

```text
scripts/provider_smoke_test.py
tests/test_provider_smoke_config.py
.github/workflows/foundation-provider-smoke.yml
requirements/provider-adapter.txt
docs/p1_ci_dependency_profiles.md
```

### 功能

环境变量：

```text
DEEPSEEK_API_KEY
QWEN_API_KEY
CLAUDE_API_KEY
GEMINI_API_KEY
GLM_API_KEY
```

没有 key 时：

```text
skip, not fail
```

有 key 时：

```text
发送最小 chat 请求
验证 status ok
验证 usage 或 fallback usage
验证 latency
```

### 状态更新

```text
P1_secret_gated_provider_smoke_tests_implemented_v1 = true
```

---

## T015：Real streaming smoke tests

### 目标

真实 provider streaming smoke test。

### 功能

- 最少验证一个 provider 的 `stream=true`。
- 能接收 `provider_stream_started`。
- 能接收至少一个 delta 或 completed。
- 能处理 provider_stream_failed。

### 状态更新

```text
P1_secret_gated_provider_streaming_smoke_tests_implemented_v1 = true
```

---

# Phase E：可观测性与审计

## T016：OpenTelemetry tracing v1

### 目标

给 API、Agent、Provider、Skill 增加 OTel tracing scaffold。

### 文件

```text
services/tracing.py
inference/api_server.py
agent/runtime.py
agent/tool_loop.py
providers/base.py
tests/test_tracing.py
docs/p1_observability.md
```

### 功能

- trace_id/span_id。
- API request span。
- agent run span。
- provider call span。
- skill call span。
- 可配置 OTLP exporter。
- 默认 disabled。

### 状态更新

```text
P2_otel_tracing_implemented_v1 = true
```

---

## T017：Enterprise audit log v1

### 目标

把 auth audit 扩展为通用审计事件。

### 文件

```text
services/audit_log.py
inference/api_server.py
agent/runtime.py
skills/registry.py
providers/base.py
tests/test_audit_log.py
docs/p1_auth_api_keys.md
docs/p1_observability.md
```

### 功能

- request audit。
- provider call audit。
- tool call audit。
- memory write audit。
- lifecycle action audit。
- sensitive field redaction。

### 状态更新

```text
P2_enterprise_audit_log_implemented_v1 = true
```

---

## T018：Provider billing reconciliation v1

### 目标

把 provider usage reconciliation 扩展成账单级对账 scaffold。

### 文件

```text
services/provider_billing.py
services/usage_reconciliation.py
tests/test_provider_billing.py
docs/p1_usage_reconciliation.md
```

### 功能

- 导入 provider billing CSV/JSON。
- 和 usage ledger 对比。
- 输出差异报告。
- 支持 workspace/project/user 维度汇总。

### 状态更新

```text
P2_provider_billing_reconciliation_implemented_v1 = true
```

---

# Phase F：部署与生产化

## T019：Docker deployment profile v1

### 目标

新增 Dockerfile 和 docker-compose。

### 文件

```text
Dockerfile
docker-compose.yml
.env.example
docs/deployment.md
```

### 功能

- API server 容器。
- volume 挂载 outputs。
- 可选 local model path。
- healthcheck。

### 状态更新

```text
P2_docker_deployment_profile_implemented_v1 = true
```

---

## T020：Kubernetes deployment profile v1

### 目标

新增 K8s 部署样板。

### 文件

```text
deploy/k8s/api-deployment.yaml
deploy/k8s/api-service.yaml
deploy/k8s/configmap.yaml
deploy/k8s/secret.example.yaml
deploy/k8s/pvc.yaml
docs/deployment.md
```

### 状态更新

```text
P2_kubernetes_deployment_profile_implemented_v1 = true
```

---

# Phase G：Evaluation Suite

## T021：Evaluation suite scaffold

### 目标

新增评测框架骨架。

### 文件

```text
evals/runner.py
evals/datasets/basic_chat.jsonl
evals/datasets/tool_calling.jsonl
evals/metrics.py
tests/test_eval_runner.py
docs/evaluation.md
```

### 功能

- 读取 eval dataset。
- 调用 provider dry run 或真实 provider。
- 计算基础 pass/fail。
- 输出 eval report。

### 状态更新

```text
P2_evaluation_suite_scaffold_implemented_v1 = true
```

---

## T022：Agent regression evals

### 目标

给 Agent tool loop / lifecycle / provider stream 增加回归评测。

### 文件

```text
evals/datasets/agent_tool_loop.jsonl
evals/datasets/agent_lifecycle.jsonl
evals/agent_eval.py
docs/evaluation.md
```

### 状态更新

```text
P2_agent_regression_evals_implemented_v1 = true
```

---

# Phase H：AI 短剧专项能力

## T023：Drama story understanding skill v1

### 目标

新增短剧故事理解 skill。

### 文件

```text
skills/drama_story.py
configs/skills/foundation_skills.json
tests/test_drama_story_skill.py
docs/p3_drama_skills.md
```

### 功能

输入小说片段，输出：

```text
人物
关系
主线
冲突
爽点
反转点
情绪曲线
```

### 状态更新

```text
P3_drama_story_understanding_skill_implemented_v1 = true
```

---

## T024：Drama episode planner skill v1

### 目标

小说转短剧集数规划。

### 文件

```text
skills/drama_episode_planner.py
tests/test_drama_episode_planner.py
docs/p3_drama_skills.md
```

### 输出

```text
episode_index
episode_title
hook
conflict
key_beats
ending_cliffhanger
estimated_duration
```

### 状态更新

```text
P3_drama_episode_planner_skill_implemented_v1 = true
```

---

## T025：Drama character consistency skill v1

### 目标

角色一致性检查与角色卡生成。

### 文件

```text
skills/drama_character.py
tests/test_drama_character.py
docs/p3_drama_skills.md
```

### 状态更新

```text
P3_drama_character_consistency_skill_implemented_v1 = true
```

---

## T026：Drama shot planner skill v1

### 目标

短剧分镜规划 skill。

### 文件

```text
skills/drama_shot_planner.py
tests/test_drama_shot_planner.py
docs/p3_drama_skills.md
```

### 输出

```text
scene_id
shot_id
景别
镜头运动
人物动作
对白
音效
画面提示词
视频提示词
时长
```

### 状态更新

```text
P3_drama_shot_planner_skill_implemented_v1 = true
```

---

# Phase I：前端工作台准备任务

## T027：Agent workspace API aggregation v1

### 目标

为前端工作台聚合 Agent run 数据。

### API

```text
GET /v1/workspace/summary
GET /v1/workspace/runs
GET /v1/workspace/usage
```

### 文件

```text
inference/api_server.py
services/workspace_summary.py
openapi/foundation_api.openapi.yaml
tests/test_api_server_foundation.py
docs/p1_api_server_integration.md
```

### 状态更新

```text
P2_workspace_summary_api_implemented_v1 = true
```

---

## T028：Provider management API v1

### 目标

给前端管理 provider/model instance registry 的只读 API。

### API

```text
GET /v1/providers
GET /v1/models
GET /v1/models/{model_id}
POST /v1/providers/smoke-test
```

### 状态更新

```text
P2_provider_management_api_implemented_v1 = true
```

---

# Phase J：任务收口与质量门禁

## T029：Full docs index and roadmap sync

### 目标

整理所有 P0/P1/P2/P3 文档入口。

### 文件

```text
docs/README.md
docs/implementation_status.md
docs/codex_execution_plan.md
```

### 验收标准

- 所有文档有入口。
- 所有状态 flag 一致。
- 已完成/未完成边界清楚。

### 状态更新

```text
P1_docs_index_roadmap_synced_v1 = true
```

---

## T030：Quality gate command script

### 目标

新增一键质量检查脚本。

### 文件

```text
scripts/quality_gate.py
tests/test_quality_gate.py
docs/p1_ci_dependency_profiles.md
```

### 功能

支持：

```bash
python scripts/quality_gate.py --profile core
python scripts/quality_gate.py --profile api-server
python scripts/quality_gate.py --profile provider-adapter
python scripts/quality_gate.py --profile all-lightweight
```

### 状态更新

```text
P1_quality_gate_script_implemented_v1 = true
```

---

# 推荐执行顺序

Codex 应按以下顺序执行：

```text
T001 SQLiteRunStore v1
T002 Agent lifecycle 支持 run_store 配置选择
T003 Agent runtime artifact 写入迁移到 RunStore
T004 Run listing/query API v1
T005 DB-backed Agent events v1
T006 Distributed quota/rate limit backend interface
T007 Worker lease / claim run v1
T008 provider-native bidirectional continuation adapter v1
T014 Secret-gated provider smoke test framework
T015 Real streaming smoke tests
T009 DeepSeek provider adapter v1
T010 Qwen provider adapter v1
T011 Claude provider adapter v1
T012 Gemini provider adapter v1
T013 GLM provider adapter v1
T016 OpenTelemetry tracing v1
T017 Enterprise audit log v1
T018 Provider billing reconciliation v1
T019 Docker deployment profile v1
T020 Kubernetes deployment profile v1
T021 Evaluation suite scaffold
T022 Agent regression evals
T023 Drama story understanding skill v1
T024 Drama episode planner skill v1
T025 Drama character consistency skill v1
T026 Drama shot planner skill v1
T027 Agent workspace API aggregation v1
T028 Provider management API v1
T029 Full docs index and roadmap sync
T030 Quality gate command script
```

---

# 给 Codex 的总提示词

把下面这段直接发给 Codex：

```text
你现在在仓库 mmt1202/myai 的 qwen-novel2drama-llm 项目中工作。

请阅读 docs/codex_execution_plan.md，并从 T001 开始按顺序执行任务。

执行规则：
1. 每次只执行一个 Txxx 任务。
2. 不要跳任务，除非当前任务明确依赖缺失且无法继续。
3. 每个任务必须包含代码、测试、文档、implementation_status 更新。
4. 如果涉及 API，必须同步 openapi/foundation_api.openapi.yaml、scripts/check_openapi_contract.py、tests/test_openapi_contract_check.py、tests/test_foundation_contracts.py。
5. 如果涉及 CI，必须同步 scripts/ci_profiles.py 和 .github/workflows/*。
6. 每个任务完成后运行相关 unittest，并在最终回复中列出运行结果。
7. 不要把阶段性能力夸大成完整生产系统。
8. commit message 使用：Txxx: <short English summary>。

现在开始执行 T001：SQLiteRunStore v1。
```
