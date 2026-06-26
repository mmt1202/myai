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

### P0/P1 底座工程契约

这些是大模型底座的机器可读工程契约与运行时同步合同：

- `configs/schemas/content_block_schema.json`：统一多模态 content block schema。
- `configs/schemas/error_code_schema.json`：统一错误码 schema。
- `configs/schemas/response_envelope_schema.json`：统一响应 envelope schema。
- `configs/model_capability_registry.json`：模型能力注册表。
- `configs/model_instance_registry.json`：模型实例注册表。
- `configs/model_router.yaml`：模型路由策略契约。
- `openapi/foundation_api.openapi.yaml`：Foundation API OpenAPI 规格，已同步当前运行时 `/v1/*` endpoints、API key security scheme 和 model tool loop 字段。
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
- `services/rule_engine.py`：确定性规则评估服务。
- `services/auth.py`：API key、scope、workspace 校验服务。
- `agent/runtime.py`：通用 Agent run/session/step 状态机、审批门、skill loop、provider execution 与 model tool loop 运行时。
- `agent/tool_loop.py`：模型返回 tool calls 后的工具解析、skill 执行、tool_result 回填和多轮 provider 调用。
- `providers/base.py`：Provider adapter 基础合同。
- `providers/openai_compatible.py`：OpenAI-compatible chat completions provider adapter。
- `providers/local_text.py`：本地 transformers 文本 provider adapter，接入现有 `inference/model_utils.py`。
- `providers/factory.py`：按模型实例构造 provider 的工厂，已支持 OpenAI-compatible 与 local transformers。
- `skills/registry.py`：Foundation Skills 注册表和调用入口。
- `mcp/adapter.py`：Foundation Skills 到 MCP-style tools/resources/prompts 的适配器。
- `inference/api_server.py`：统一 Foundation `/v1/*` API server 集成，并已接入 auth middleware。
- `configs/auth/api_keys.example.json`：API key store 示例配置。
- `configs/skills/foundation_skills.json`：Foundation Skills 注册表配置。
- `configs/schemas/memory_item_schema.json`：记忆条目 schema。
- `configs/schemas/agent_run_schema.json`：Agent run schema。
- `configs/rules/default_rules.yaml`：默认规则集。
- `services/__init__.py`：服务包标记。
- `agent/__init__.py`：Agent 包标记。
- `providers/__init__.py`：Provider 包标记。
- `skills/__init__.py`：Skills 包标记。
- `mcp/__init__.py`：MCP 包标记。
- `tests/test_foundation_core_services.py`：核心服务测试。
- `tests/test_memory_store.py`：记忆服务测试。
- `tests/test_rule_engine.py`：规则服务测试。
- `tests/test_auth_service.py`：Auth 服务测试。
- `tests/test_agent_runtime.py`：Agent runtime 测试。
- `tests/test_agent_tool_loop.py`：Agent model tool loop 测试。
- `tests/test_provider_adapter_contract.py`：Provider adapter 合同测试。
- `tests/test_provider_factory.py`：Provider factory 测试。
- `tests/test_local_text_provider.py`：本地 provider 测试。
- `tests/test_skill_registry.py`：Skills registry 测试。
- `tests/test_mcp_adapter.py`：MCP adapter 测试。
- `tests/test_api_server_foundation.py`：Foundation API server 测试。
- `docs/p1_foundation_core_services.md`：核心服务说明。
- `docs/p1_memory_store.md`：记忆服务说明。
- `docs/p1_rule_engine.md`：规则服务说明。
- `docs/p1_auth_api_keys.md`：Auth/API key/workspace scope 说明。
- `docs/p1_agent_runtime.md`：Agent runtime 说明。
- `docs/p1_provider_adapter.md`：Provider adapter 说明。
- `docs/p1_skill_registry.md`：Skills registry 说明。
- `docs/p1_mcp_adapter.md`：MCP adapter 说明。
- `docs/p1_api_server_integration.md`：API server 集成说明。

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
P1_runtime_openapi_contract_synced_v1 = true
P1_auth_api_key_workspace_scope_implemented_v1 = true
P1_local_provider_adapter_implemented_v1 = true
P1_model_decided_tool_loop_implemented_v1 = true
P1_router_token_cost_usage_memory_rules_agent_runtime_provider_adapter_skills_mcp_adapter_api_server_agent_provider_execution_agent_skill_loop_implemented_v1 = true
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

P0/P1 已经把核心研究结果转成第一版工程契约和一批可运行服务；OpenAPI 已同步当前 FastAPI runtime，API server 已接入轻量 API key/workspace scope，本地模型也已接入统一 provider factory，Agent 已具备同步 model-decided tool loop v1。下一步应继续实现 OpenAPI lint/check tooling、auth audit/rate limiting、本地 provider 并发/流式和 streaming run events。

## 当前最重要的未完成项

### P1：底座核心服务剩余项

1. 增加 OpenAPI lint/check tooling。
2. 增加 auth audit log、rate limit、workspace-level quota/budget。
3. 增加本地 provider 并发保护、缓存控制和流式输出。
4. 增加 Agent streaming run events 与 resume/cancel/retry。

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

## 已经存在但需要继续演进的能力矩阵

- `configs/foundation_capability_matrix.json` 是高层能力矩阵。
- `configs/model_capability_registry.json` 是模型能力注册表。
- `configs/model_instance_registry.json` 是模型实例注册表，并已配置 local runtime env。
- `inference/model_router.py` 已开始使用模型实例注册表进行真实路由。
- `services/auth.py` 已开始提供 API key、scope、workspace 校验。
- `agent/runtime.py` 已开始把 router、rules、skills、provider factory、model tool loop 和 usage ledger 串成通用 Agent run 状态机。
- `agent/tool_loop.py` 已开始执行 provider 返回的 tool_calls 并将 tool_result 回填到下一轮 provider 请求。
- `providers/factory.py` 已开始按模型实例构造 provider，并支持本地 transformers provider。
- `providers/local_text.py` 已开始把现有本地模型运行时接入 provider 协议。
- `skills/registry.py` 已开始把内部服务注册为可调用 Skills。
- `mcp/adapter.py` 已开始把 Skills 暴露为 MCP-style tools/resources/prompts。
- `inference/api_server.py` 已开始把底座能力暴露为 `/v1/*` HTTP API，并通过 middleware 接入 auth。
- `openapi/foundation_api.openapi.yaml` 已同步当前运行时 endpoints、Agent provider/skill/tool loop 字段和 API key security scheme。

## 后续开发顺序

1. P1：继续实现 OpenAPI lint/check tooling、auth audit/rate limiting、本地 provider 并发/流式、Agent streaming events。
2. P2：接入多 provider、多模态生成/理解、MCP SDK 兼容层、评测、观测、审计、部署。
3. P3：加强 AI 短剧/漫剧专项模型能力，包括故事理解、集数规划、角色一致性、分镜规划、视觉提示词生成、短剧质检评测。

## 禁止误判

- 不能把“需求研究完成”说成“大模型底座实现完成”。
- 不能把“P0 工程契约完成”说成“运行时服务完成”。
- 不能把“OpenAPI 同步完成”说成“鉴权、流式、生产部署都完成”。
- 不能把“Auth/API key 完成”说成“完整企业 IAM/OAuth/OIDC 已完成”。
- 不能把“本地 provider adapter 完成”说成“所有 provider 已接入”。
- 不能把“model-decided tool loop v1 完成”说成“生产级分布式 Agent 已完成”。
- 不能把“P1 router/token/cost/ledger/memory/rules/auth/agent runtime/provider adapter/skills/MCP adapter/API server/Agent provider execution/Agent skill loop/local provider/model tool loop 完成”说成“所有核心服务完成”。
- 不能把“Skills registry 完成”说成“完整插件市场完成”。
- 不能把“MCP adapter 完成”说成“正式 MCP SDK 完整兼容”。
- 不能把“API server integration 完成”说成“鉴权、流式、生产部署都完成”。
- 不能把“runtime registry”说成“多模态模型已经接入”。
- 不能把“AI 短剧能力矩阵”说成“AI 短剧平台已经完成”。
- 不能把“训练 runbook”说成“模型已经训练完成”。
