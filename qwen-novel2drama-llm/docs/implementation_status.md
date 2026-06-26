# 实现状态

这个文件用于区分项目已经能跑的部分、已经完成研究但尚未工程化的部分，以及还需要继续开发的部分。

当前项目长期定位是：**可部署、可扩展、可观测、可审计、可路由、可控成本的 AI 大模型底座**。

AI 短剧/漫剧不是当前要先做的应用平台，而是这个大模型底座的长期特色能力方向之一。未来短剧/漫剧平台、代码工具、桌面端或其他产品可以使用这个底座，但底座本身必须先解决模型能力、推理、多模态、token、成本、记忆、规则、Skills、MCP、Agent、API、评测和部署问题。

## 已经能跑

### P0 文本生成基础运行时

- `inference/model_utils.py`：文本模型加载与生成。
- `configs/model_registry.json`：基础模型运行时注册表。
- `scripts/inspect_model_registry.py`：查看模型运行时注册表。
- `scripts/plan_training_run.py`：生成训练运行 manifest。
- `scripts/register_model_version.py`：登记训练后的模型版本。
- `inference/api_server.py`：可从 active model version 启动 API。

### P0 底座工程契约 v1

这些是大模型底座的第一版机器可读工程契约，不是完整运行时服务：

- `configs/schemas/content_block_schema.json`：统一多模态 content block schema。
- `configs/schemas/error_code_schema.json`：统一错误码 schema。
- `configs/schemas/response_envelope_schema.json`：统一响应 envelope schema。
- `configs/model_capability_registry.json`：模型能力注册表。
- `configs/model_instance_registry.json`：模型实例注册表。
- `configs/model_router.yaml`：模型路由策略契约。
- `openapi/foundation_api.openapi.yaml`：Foundation API OpenAPI 规格。
- `docs/foundation_api_contract.md`：API 合同说明。
- `scripts/inspect_model_capabilities.py`：查看模型能力注册表。
- `scripts/inspect_model_instances.py`：查看模型实例注册表。
- `tests/test_foundation_contracts.py`：底座契约测试。

### P1 底座核心服务 v1

这些服务已经开始把 P0 合同变成可运行模块，但仍不是最终生产级 provider 集成：

- `inference/model_router.py`：基于能力、模态、隐私、上下文窗口和 route mode 的模型路由器。
- `services/token_counter.py`：统一 request token 与多模态 billable unit 估算。
- `services/cost_estimator.py`：基于模型实例价格元数据的成本估算。
- `services/usage_ledger.py`：JSONL usage ledger 与汇总。
- `services/memory_store.py`：分层记忆服务。
- `configs/schemas/memory_item_schema.json`：记忆条目 schema。
- `services/__init__.py`：服务包标记。
- `tests/test_foundation_core_services.py`：核心服务测试。
- `tests/test_memory_store.py`：记忆服务测试。
- `docs/p1_foundation_core_services.md`：核心服务说明。
- `docs/p1_memory_store.md`：记忆服务说明。

### P1 coding-agent 工程基础设施

这些能力是代码 Agent 方向的工程闭环 v1，不等于完整大模型底座已经完成：

- 项目上下文索引。
- Python 代码符号索引。
- patch plan。
- patch spec prompt。
- 模型 patch spec API adapter。
- patch spec validation。
- unified diff generation。
- safe patch apply。
- test plan runner。
- `scripts/ai_code_agent.py`：完整代码 Agent CLI v1。
- `configs/tool_registry.json`：工具注册表。
- `scripts/mcp_tool_server.py`：本地 MCP-style JSON-RPC 工具服务器 wrapper。

## 已完成研究并已开始工程化

深度研究已经完成第一轮需求挖掘，形成了可部署 AI 大模型底座的需求方向。当前状态是：

```text
research_completed_v1 = true
requirements_ready_for_architecture = true
P0_contracts_implemented_v1 = true
P1_router_token_cost_usage_memory_implemented_v1 = true
runtime_services_completed = partially
implementation_completed = false
```

对应文件：

- `docs/foundation_requirements_audit.md`：需求完成度审计与遗留需求。
- `configs/foundation_requirement_backlog.json`：需求工程化 backlog。

研究已经覆盖：

- 统一推理接口。
- 思考/推理状态。
- 多模态输入输出。
- token 与成本。
- 模型能力注册。
- 模型路由。
- 记忆系统。
- 规则系统。
- Skills/MCP。
- Agent 编排。
- 观测、审计和账单。
- 安全、权限和合规。
- 模型生命周期。
- AI 短剧/漫剧专项模型能力。

P0 已经把核心研究结果转成第一版工程契约；P1 已经开始实现 router、token、cost、usage ledger 和 memory store。下一步应继续实现 rules、agent runtime 和 provider adapter base。

## 当前最重要的未完成项

### P1：底座核心服务剩余项

1. `services/rule_engine.py`
2. `agent/runtime.py`
3. `providers/base.py`
4. `skills/registry.py`
5. `mcp/adapter.py`
6. 把 `inference/api_server.py` 接入新的 router/token/cost/memory/envelope。

### P2：Provider 接入与生产化

1. OpenAI-compatible provider adapter。
2. Qwen/DeepSeek/GLM/Gemini/Claude provider adapters。
3. 图片、视频、音频、ASR、TTS provider adapters。
4. OTel tracing。
5. Audit log。
6. Usage ledger reconciliation。
7. Evaluation suite。
8. Deployment profiles。
9. Deprecation watcher。
10. Region/data-residency routing。

## 已经存在但需要继续演进的能力矩阵

- `configs/foundation_capability_matrix.json` 是高层能力矩阵。
- `configs/model_capability_registry.json` 是模型能力注册表。
- `configs/model_instance_registry.json` 是模型实例注册表。
- `inference/model_router.py` 已开始使用模型实例注册表进行真实路由。

## 后续开发顺序

1. P1：继续实现 rules、agent runtime、provider adapter base、API server route integration。
2. P2：接入多 provider、多模态生成/理解、MCP SDK 兼容层、评测、观测、审计、部署。
3. P3：加强 AI 短剧/漫剧专项模型能力，包括故事理解、集数规划、角色一致性、分镜规划、视觉提示词生成、短剧质检评测。

## 禁止误判

- 不能把“需求研究完成”说成“大模型底座实现完成”。
- 不能把“P0 工程契约完成”说成“运行时服务完成”。
- 不能把“P1 router/token/cost/ledger/memory 完成”说成“所有核心服务完成”。
- 不能把“runtime registry”说成“多模态模型已经接入”。
- 不能把“MCP-style wrapper”说成“正式 MCP SDK 完整兼容”。
- 不能把“AI 短剧能力矩阵”说成“AI 短剧平台已经完成”。
- 不能把“训练 runbook”说成“模型已经训练完成”。
