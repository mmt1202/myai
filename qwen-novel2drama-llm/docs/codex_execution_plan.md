# Codex 连续执行任务总控文档

本文档用于让 Codex 按顺序继续完成 `qwen-novel2drama-llm` 的剩余工程任务。

当前项目定位：**可配置主模型的 AI Foundation**。系统不绑定任何单一 provider，主模型可按 request、environment、project、workspace、task、global defaults 选择，并可通过 workspace/project settings API 做运行时覆盖。

---

## 0. 执行规则

默认项目目录：

```text
qwen-novel2drama-llm/
```

每个任务完成后同步代码、测试、文档和状态。

建议轻量测试：

```bash
python scripts/check_openapi_contract.py
python -m unittest tests.test_openapi_contract_check tests.test_foundation_contracts
python -m unittest tests.test_model_preferences tests.test_model_settings_store tests.test_model_settings_api tests.test_model_settings_api_server tests.test_configurable_model_router tests.test_foundation_core_services tests.test_ci_profiles
python -m unittest tests.test_openai_responses_provider tests.test_openai_responses_smoke
python -m unittest tests.test_drama_pipeline tests.test_drama_api tests.test_media_generation
python -m unittest tests.test_quality_gate tests.test_cloud_deploy_profile tests.test_external_queue tests.test_billing_usage_records tests.test_memory_quality
```

---

## 1. 当前已完成基线

```text
P1 foundation and hardening = completed_v1
P1 configurable primary model routing = completed_v1
P1 workspace/project model settings API = completed_v1
P1 OpenAI Responses provider adapter = completed_v1
P1 OpenAI Responses provider native streaming = completed_v1
P2 foundation capabilities = completed_v1
P3 drama pipeline = completed_v1
```

主模型配置完成标记：

```text
P1_configurable_primary_model_policy_implemented_v1 = true
P1_workspace_project_model_settings_store_implemented_v1 = true
P1_workspace_project_model_settings_api_implemented_v1 = true
P1_openai_responses_provider_adapter_implemented_v1 = true
P1_openai_responses_provider_smoke_implemented_v1 = true
P1_openai_responses_native_streaming_implemented_v1 = true
P1_request_workspace_project_task_model_override_implemented_v1 = true
P1_model_route_privacy_context_cost_guards_implemented_v1 = true
P1_model_fallback_chain_implemented_v1 = true
```

---

## M001：可配置 Primary Model

状态：已完成。

文件：`configs/model_routing_policy.json`、`services/model_preferences.py`、`inference/model_router.py`。

能力：主模型不写死，支持 request/env/project/workspace/task/global 多层解析。

---

## M002：Model Route Policy

状态：已完成。

文件：`configs/model_routing_policy.json`。

能力：定义 global primary、fallback models、cheap models、private models、task routes。

---

## M003：Workspace Model Settings

状态：已完成。

文件：`services/model_settings_store.py`、`inference/model_settings_api.py`、`inference/api_server.py`。

能力：通过 API 写入 workspace 级 primary/fallback，并自动覆盖默认 policy。

接口：

```text
GET    /v1/model/settings/workspaces/{workspace_id}
PUT    /v1/model/settings/workspaces/{workspace_id}
DELETE /v1/model/settings/workspaces/{workspace_id}
```

---

## M004：Project Model Settings

状态：已完成。

文件：`services/model_settings_store.py`、`inference/model_settings_api.py`、`inference/api_server.py`。

能力：通过 API 写入 project 级 primary/fallback，并优先于 workspace setting 生效。

接口：

```text
GET    /v1/model/settings/projects/{project_id}
PUT    /v1/model/settings/projects/{project_id}
DELETE /v1/model/settings/projects/{project_id}
```

---

## M005：Request Model Override

状态：已完成。

能力：单次请求可通过 `model_id`、`model`、`primary_model`、`fallback_models` 覆盖默认模型选择。

---

## M006：Provider Capability Registry

状态：已完成 v1。

文件：`configs/model_instance_registry.json`。

能力：每个 model instance 声明 capabilities、context_window、max_output_tokens、input_modalities、output_modalities、privacy、cost、runtime_config。

---

## M007：Fallback Chain

状态：已完成。

能力：`route_model()` 输出 `fallback_chain`，且根据 policy preferred model order 排序。

---

## M008：Cost Guard

状态：已完成。

能力：请求可使用 `max_estimated_cost` 拒绝超预算候选。

---

## M009：Privacy Guard

状态：已完成。

能力：`privacy.local_only=true` 强制使用 private/local models。

---

## M010：Model Evaluation

状态：已完成 v1。

文件：`evals/quality_gate.py`、`evals/golden/*.json`。

能力：已有 quality gate 和 golden dataset；后续可加入真实 provider live eval。

---

## M011：OpenAI Responses Provider Adapter

状态：已完成。

文件：`providers/openai_responses.py`、`providers/factory.py`、`scripts/openai_responses_smoke.py`。

能力：`runtime=openai_responses` 自动走 Responses adapter；支持 text/image/file input mapping、tools、tool_choice、dry-run、response parsing、missing key preflight。

测试：`tests.test_openai_responses_provider`、`tests.test_openai_responses_smoke`。

---

## M012：OpenAI Responses Native Streaming

状态：已完成。

文件：`providers/openai_responses.py`、`scripts/openai_responses_smoke.py`。

能力：支持 provider-native SSE stream、`stream=true` payload、`stream_options`、SSE `event:`/`data:` JSON 解析、delta/completed/error/usage 映射、dry-run stream smoke。

测试：`tests.test_openai_responses_provider`、`tests.test_openai_responses_smoke`。

---

## 仍未完成的真实外部专项

```text
真实 Kubernetes cluster / terraform apply = external_required
真实 AWS/GCP/Azure/Vault SDK 权限 = external_required
真实域名、证书、WAF、CDN 绑定 = external_required
真实 Redis/RabbitMQ/SQS/PubSub 连接 = external_required
真实 provider 账单格式 = external_required
真实媒体平台 endpoint / callback / 存储桶 = external_required
真实 OpenAI/Claude/Gemini/DeepSeek/Qwen 账号与模型名 live smoke = external_required
```

---

## 下一阶段

1. Admin UI / 前端管理页对接 workspace/project model settings API。
2. ForgePilot：Codex-like 本地开发 Agent 外壳。
3. Provider live eval / live smoke 矩阵。
