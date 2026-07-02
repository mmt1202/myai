# Codex 连续执行任务总控文档

本文档用于让 Codex 按顺序继续完成 `qwen-novel2drama-llm` 的剩余工程任务。

当前项目定位：**可配置主模型的 AI Foundation**。系统不绑定任何单一 provider，主模型可按 request、environment、project、workspace、task、global defaults 选择。

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
python -m unittest tests.test_model_preferences tests.test_configurable_model_router tests.test_foundation_core_services tests.test_ci_profiles
python -m unittest tests.test_drama_pipeline tests.test_drama_api tests.test_media_generation
python -m unittest tests.test_quality_gate tests.test_cloud_deploy_profile tests.test_external_queue tests.test_billing_usage_records tests.test_memory_quality
```

---

## 1. 当前已完成基线

```text
P1 foundation and hardening = completed_v1
P1 configurable primary model routing = completed_v1
P2 foundation capabilities = completed_v1
P3 drama pipeline = completed_v1
```

主模型配置完成标记：

```text
P1_configurable_primary_model_policy_implemented_v1 = true
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

状态：已完成 contract。

文件：`configs/model_routing_policy.json`、`services/model_preferences.py`。

能力：policy 的 `workspaces` 节点支持 workspace 级 primary/fallback。

---

## M004：Project Model Settings

状态：已完成 contract。

文件：`configs/model_routing_policy.json`、`services/model_preferences.py`。

能力：policy 的 `projects` 节点支持 project 级 primary/fallback。

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

## 仍未完成的真实外部专项

```text
真实 Kubernetes cluster / terraform apply = external_required
真实 AWS/GCP/Azure/Vault SDK 权限 = external_required
真实域名、证书、WAF、CDN 绑定 = external_required
真实 Redis/RabbitMQ/SQS/PubSub 连接 = external_required
真实 provider 账单格式 = external_required
真实媒体平台 endpoint / callback / 存储桶 = external_required
真实 OpenAI/Claude/Gemini/DeepSeek/Qwen 账号与模型名 smoke test = external_required
```

---

## 下一阶段

1. OpenAI Responses provider live adapter smoke。
2. Workspace/project model settings API。
3. ForgePilot：Codex-like 本地开发 Agent 外壳。
