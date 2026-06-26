# AI 大模型底座需求审计

## 结论

深度研究已经完成了第一轮需求挖掘，可以作为架构设计和工程拆分的依据，但它目前仍然是“需求分析与工程草案”，不是最终实现规格，也不是功能完成证明。

当前状态应定义为：

```text
research_completed_v1 = true
requirements_ready_for_architecture = true
requirements_ready_for_coding = partially
implementation_completed = false
```

换句话说：

- 已经知道大模型底座应该覆盖哪些核心能力。
- 已经知道这些能力应该如何分层和暴露 API。
- 已经知道优先级、风险和部分工程路线。
- 但还没有把所有需求转成可执行的 OpenAPI、JSON Schema、配置、服务模块、测试用例和验收标准。

## 已经研究到位的需求域

| 需求域 | 当前研究状态 | 是否足以进入工程设计 | 说明 |
|---|---|---|---|
| 统一推理接口 | completed_v1 | yes | 已明确 chat/reason/multimodal analyze 的统一入口方向。 |
| 思考/推理状态 | completed_v1 | yes | 已明确不能把 reasoning 当普通文本，应作为受权限控制的内部状态。 |
| 多模态输入输出 | completed_v1 | yes | 已明确 text/image/video/audio/subtitle/metadata/file/url 的 content block 方向。 |
| token 与成本 | completed_v1 | yes | 已明确 preflight estimate 与 actual usage/reconciliation 分离。 |
| 模型能力注册 | completed_v1 | yes | 已明确 capability 与 model instance 分离。 |
| 模型路由 | completed_v1 | yes | 已明确 smart/cheap/balanced/local-first/cloud-first/drama-specialist/code-specialist/fallback。 |
| 记忆系统 | completed_v1 | partial | 已明确 session/user/project/task 分层，但还缺数据模型和检索策略细化。 |
| 规则系统 | completed_v1 | partial | 已明确 allow/deny/review 与规则优先级，但还缺规则 DSL。 |
| Skills/MCP | completed_v1 | partial | 已明确 Skill Registry + MCP Adapter 双层结构，但还缺正式协议兼容细节。 |
| Agent 编排 | completed_v1 | partial | 已明确 run/session/step 状态机，但还缺事件模型和恢复协议。 |
| 观测/审计/账单 | completed_v1 | partial | 已明确 trace/usage/audit/ledger，但还缺字段级 schema。 |
| 安全/权限/合规 | completed_v1 | partial | 已明确 RBAC、ZDR、region、数据保留，但还缺安全测试矩阵。 |
| 模型生命周期 | completed_v1 | yes | 已明确 snapshot/alias/deprecation/fallback/migration。 |
| 短剧/漫剧专项能力 | completed_v1 | partial | 已明确作为模型能力特色，不是当前应用平台；还缺专项评测集和 API 细化。 |

## 尚未完成的需求细化

这些不是“研究没做”，而是从草案进入可开发规格前必须补齐的内容。

### 1. API 契约还没有落成机器可读规格

需要补：

- `openapi/foundation_api.openapi.yaml`
- endpoint request/response schema
- streaming event schema
- async job schema
- error code schema
- auth scope schema
- usage/cost schema

否则当前 API 仍停留在文档级草案，不能直接给前后端或 SDK 开发使用。

### 2. 统一 content block 还没有 JSON Schema

需要补：

- `configs/schemas/content_block_schema.json`
- text/image/video/audio/subtitle/metadata/file/url block
- file reference schema
- media segment schema
- provenance/licensing fields
- watermark/content credentials fields

这是所有 chat、reason、multimodal、agent、memory、skill 的共同底层协议。

### 3. 模型能力注册表还没有落地为正式配置

需要补：

- `configs/model_capability_registry.json`
- `configs/model_instance_registry.json`
- capability taxonomy
- provider/runtime compatibility
- lifecycle/deprecation metadata
- privacy/region/licensing metadata
- cost and context window metadata

当前已有 runtime registry，但不是完整 capability registry。

### 4. 模型路由还没有实现

需要补：

- `inference/model_router.py`
- `configs/model_router.yaml`
- route decision log
- fallback chain
- policy pre-filter
- scoring layer
- provider health integration
- budget and latency constraints

没有路由器，就无法实现“最聪明、最便宜、最有性价比”的自动选择。

### 5. token/cost 仍未工程化

需要补：

- `services/token_counter.py`
- `services/cost_estimator.py`
- `services/usage_ledger.py`
- tokenizer registry
- multimodal estimate policy
- provider usage reconciliation
- cache hit/miss accounting

这会影响所有成本控制、预算、限流和商业化。

### 6. 记忆系统还缺数据模型和检索协议

需要补：

- memory item schema
- scope: session/user/project/task
- TTL and sensitivity
- dedup policy
- write/search/delete APIs
- hybrid retrieval strategy
- permission isolation tests

记忆不是聊天历史，必须作为底座服务独立存在。

### 7. 规则系统还缺 DSL 与执行器

需要补：

- `configs/rules/*.yaml`
- rule evaluation engine
- priority and conflict detection
- allow/deny/review decision model
- budget/region/provider/tool approval rules
- deterministic tests

规则不能全部写进 prompt，否则无法审计和测试。

### 8. Agent 状态机还缺正式运行时

需要补：

- run/session/step data model
- state machine
- event stream
- resume/cancel/retry
- approval gate
- tool loop control
- async job integration

当前已有 code-agent workflow，但不是通用大模型底座的 Agent runtime。

### 9. MCP/Skills 还缺正式兼容层

当前仓库已有本地 MCP-style wrapper，但还需要补：

- official MCP SDK compatibility layer
- resources/prompts support
- cancellation/progress support
- tool schema validation
- remote server registry
- credential isolation
- approval policy

现有工具层是代码 Agent 工具面，不等于整个大模型底座的通用 Skill/MCP 系统。

### 10. 多模态生成和理解还没有 provider adapter

需要补：

- image input/output adapters
- video input/output adapters
- audio ASR/TTS adapters
- OCR/PDF adapter
- realtime audio/video protocol
- media storage and signed URL policy
- async job lifecycle

当前是需求和 registry 方向，尚未完成真实 provider 对接。

### 11. 评测体系还没有建立

需要补：

- general reasoning eval
- tool calling eval
- multimodal eval
- cost/latency eval
- memory eval
- routing eval
- drama-specialist eval
- regression gate

没有评测，就无法判断模型升级、路由调整或 prompt 改动是否变好。

### 12. 部署与运维规格还不完整

需要补：

- deployment profiles: local/dev/server/enterprise
- GPU runtime profiles
- queue/worker architecture
- health checks
- OTel tracing
- logs/metrics dashboard
- secrets management
- backup/restore
- migration scripts

这决定它能不能从代码仓库变成可部署底座。

## 遗留需求优先级

### P0：必须先转成可执行规格

1. Unified content block schema
2. Foundation API OpenAPI spec
3. Model capability registry
4. Model instance registry
5. Model router config and router service
6. Token/cost/usage schema
7. Error code schema
8. Request/trace/audit schema
9. Memory schema and API spec
10. Rules schema and API spec
11. Agent run/session/step schema
12. Provider adapter interface

### P1：核心服务实现

1. API server route skeleton
2. Provider adapter base class
3. Router implementation
4. Token counter implementation
5. Cost estimator implementation
6. Usage ledger implementation
7. Memory store implementation
8. Rule engine implementation
9. Agent runtime implementation
10. MCP/Skill runtime implementation

### P2：生产化能力

1. Official MCP SDK compatibility
2. Async job queue
3. OTel tracing
4. Billing reconciliation
5. Deprecation watcher
6. Region/data-residency routing
7. Watermark/provenance metadata
8. Evaluation suite
9. Security red-team suite
10. Deployment profiles

## 当前最重要的纠偏

之前仓库里已经做了不少 code-agent 基础设施，但用户当前目标已经明确：先做 AI 大模型底座，而不是继续做应用层或单一代码 Agent。

所以后续工程重心必须切换为：

```text
foundation protocol
foundation API
model capability registry
model instance registry
model router
token/cost/usage
memory/rules/skills/MCP/agent runtime
multimodal provider adapters
evaluation and observability
```

## 判断“草案完成”与“需求完成”的标准

### 草案完成

满足：

- 已覆盖主要厂商能力和趋势。
- 已抽象核心需求域。
- 已形成优先级和工程方向。
- 已能指导下一步设计。

当前已经达到。

### 需求完成

还需要满足：

- 每个模块有机器可读 schema。
- 每个 API 有 OpenAPI 规格。
- 每个配置有示例和校验器。
- 每个服务有验收标准。
- 每个 P0 能力有测试用例。
- 每个风险有规则或 fallback。
- 每个 provider 差异有 adapter 合同。

当前尚未达到。

## 下一步建议

不要继续只写草案，也不要直接进入应用开发。下一步应先把研究结果固化成仓库里的工程契约：

1. `configs/schemas/content_block_schema.json`
2. `configs/schemas/error_code_schema.json`
3. `configs/model_capability_registry.json`
4. `configs/model_instance_registry.json`
5. `configs/model_router.yaml`
6. `openapi/foundation_api.openapi.yaml`
7. `docs/foundation_api_contract.md`
8. `tests/test_foundation_contracts.py`

完成这些后，需求才从“研究草案”进入“可开发规格”。
