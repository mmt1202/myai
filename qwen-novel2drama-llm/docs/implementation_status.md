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

## 已完成研究但还没有工程化

深度研究已经完成第一轮需求挖掘，形成了可部署 AI 大模型底座的需求方向。当前状态是：

```text
research_completed_v1 = true
requirements_ready_for_architecture = true
requirements_ready_for_coding = partially
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

但这些多数还停留在需求和设计层，没有全部转成机器可读 schema、OpenAPI、服务实现和测试。

## 当前最重要的未完成项

### P0：底座工程契约

必须先把研究结果转成可执行工程契约：

1. `configs/schemas/content_block_schema.json`
2. `configs/schemas/error_code_schema.json`
3. `configs/schemas/response_envelope_schema.json`
4. `openapi/foundation_api.openapi.yaml`
5. `configs/model_capability_registry.json`
6. `configs/model_instance_registry.json`
7. `configs/model_router.yaml`
8. `docs/foundation_api_contract.md`
9. `tests/test_foundation_contracts.py`

### P1：底座核心服务

1. `inference/model_router.py`
2. `services/token_counter.py`
3. `services/cost_estimator.py`
4. `services/usage_ledger.py`
5. `services/memory_store.py`
6. `services/rule_engine.py`
7. `agent/runtime.py`
8. `providers/base.py`
9. `skills/registry.py`
10. `mcp/adapter.py`

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

## 已经存在但需要重新定位的能力矩阵

- `configs/foundation_capability_matrix.json` 目前仍是高层能力矩阵。
- 它不是模型能力注册表。
- 后续应新增 `model_capability_registry.json` 和 `model_instance_registry.json`，把“逻辑能力”和“具体模型实例”分开。

## 后续开发顺序

1. P0：先完成 foundation contracts，包括 content block、error code、response envelope、OpenAPI、model capability registry、model instance registry、model router config。
2. P1：实现 router、token/cost、usage ledger、memory、rules、agent runtime、provider adapter base。
3. P2：接入多 provider、多模态生成/理解、MCP SDK 兼容层、评测、观测、审计、部署。
4. P3：加强 AI 短剧/漫剧专项模型能力，包括故事理解、集数规划、角色一致性、分镜规划、视觉提示词生成、短剧质检评测。

## 禁止误判

- 不能把“需求研究完成”说成“大模型底座实现完成”。
- 不能把“runtime registry”说成“多模态模型已经接入”。
- 不能把“MCP-style wrapper”说成“正式 MCP SDK 完整兼容”。
- 不能把“AI 短剧能力矩阵”说成“AI 短剧平台已经完成”。
- 不能把“训练 runbook”说成“模型已经训练完成”。
