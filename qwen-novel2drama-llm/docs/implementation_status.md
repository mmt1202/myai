# 实现状态

当前项目定位：可部署、可扩展、可观测、可审计、可路由、可控成本的 AI 大模型底座，并已具备 AI 短剧/漫剧 P3 专项能力。

## 已完成能力概览

### P0/P1 Foundation

- 文本生成基础运行时。
- router、token counter、cost estimator、usage ledger、provider usage reconciliation。
- configurable primary model routing：主模型不写死，支持 request / env / project / workspace / task / global 多层选择。
- workspace/project model settings API：支持通过 API 设置 workspace/project 的 primary/fallback，并自动覆盖默认路由策略。
- memory、rules、skills、MCP-style adapter。
- auth、audit、rate limit、workspace quota。
- file/SQLite/Postgres run store 与 quota backend。
- Agent events、lifecycle、runtime、tool loop、worker dispatcher、worker pool。
- Postgres migration runner/history。
- provider continuation、provider smoke、local/openai-compatible provider contracts。
- OpenAI Responses provider adapter：`runtime=openai_responses` 已有专用 provider、dry-run、payload 映射、原生 SSE stream、smoke script。
- API quota、health/readiness、queue observability、deployment profile、secret resolver、metrics、backup plan、preflight、TLS template。
- `configs/model_versions.json`：active model version 已注册，不再为空。
- `configs/model_routing_policy.json`：可配置 primary/fallback/task route 策略已完成。
- `services/model_preferences.py`：request/env/project/workspace/task/global 主模型解析已完成，并会叠加 runtime settings store。
- `services/model_settings_store.py`：workspace/project runtime settings store 已完成。
- `inference/model_settings_api.py`：workspace/project model settings API handlers 已完成。
- `inference/api_server.py`：已暴露 `/v1/model/settings/*`、`/v1/model/preferences/resolve`、`/v1/model/route`。
- `inference/model_router.py`：已接入 preference boost、fallback chain、privacy/context/output/cost guard。
- `providers/openai_responses.py`：OpenAI Responses adapter 与 provider-native stream 已完成。
- `scripts/openai_responses_smoke.py`：OpenAI Responses dry-run/live、stream/non-stream smoke 已完成。
- `configs/model_instance_registry.json`：已新增 `external.openai.primary` 作为可选 primary candidate，同时保留 Claude/Gemini/DeepSeek/Qwen/local 等候选。
- `docs/CONFIGURABLE_PRIMARY_MODEL.md`：可配置主模型路线已记录。
- `docs/OPENAI_RESPONSES_PROVIDER.md`：OpenAI Responses provider contract 已记录。
- `docs/FOUNDATION_API_CONTRACT.md`：Foundation API 契约已固定。
- `docs/FOUNDATION_BOUNDARY.md`：Foundation 与 ForgePilot 职责边界已固定。
- `scripts/run_checks.py`：核心目录 compile、skills validate、MCP validate、router smoke 已纳入检查。
- `docs/FOUNDATION_RELEASE_CHECKLIST.md`：稳定发布检查清单已补齐。
- `services/sqlite_memory_store.py`：SQLite memory backend 已完成。
- `services/vector_memory_store.py`：deterministic vector memory backend 已完成。
- `services/memory_store.py`：`FOUNDATION_MEMORY_BACKEND=file|sqlite|vector` backend selection 已完成。
- `inference/api_server.py`：Memory API 已接入 selectable backend，readiness 暴露 `memory_backend`。
- `services/memory_quality.py`：Memory duplicate/conflict/merge/compression 治理 helpers 已完成。
- `docs/MEMORY_ROADMAP.md`：Memory 后端状态、API 兼容和后续路线已更新。

### P2 Foundation

- `providers/provider_catalog.py`：DeepSeek、Qwen/DashScope、Anthropic、Gemini provider catalog。
- `providers/resilience.py`：retry、fallback、circuit breaker、provider health scoring。
- `services/multimodal_router.py`：多模态 routing contract。
- `mcp/sdk_compat.py`：MCP SDK compatibility layer。
- `evals/eval_runner.py`：eval runner。
- `evals/quality_gate.py` 与 `evals/golden/*.json`：expanded golden dataset 和质量门禁已完成。
- `services/tracing.py`：trace/span lifecycle。
- `services/audit_query.py`：audit query/export/retention。
- `scripts/deploy_profile.py`：deploy profile validator。
- `scripts/cloud_deploy_profile.py`、`deploy/terraform/main.tf`、`deploy/k8s/README.md`、`deploy/security/security_profile.yaml`、`deploy/observability/slo.yaml`：云部署、Terraform、安全、WAF/CDN/SLO profile 已完成仓库级模板与校验。
- `services/managed_secret_resolver.py`：AWS/GCP/Azure/Vault/env managed secret resolver contract 已完成。
- `external_queue/*`：外部队列抽象、retry/dead-letter、跨区域调度策略已完成。
- `billing/*`：provider usage record loading、reconciliation、workspace export 已完成。

### P3 AI 短剧/漫剧专项能力

- `drama/novel_parser.py`：章节解析、人物抽取、世界观抽取、剧情线抽取。
- `drama/outline.py`：小说转短剧大纲、剧集结构、单集剧情、钩子、悬念。
- `drama/characters.py`：角色卡、人物关系、角色一致性规则、定妆提示词。
- `drama/storyboard.py`：分镜规划、镜头列表、景别、动作、台词、旁白、场景调度。
- `drama/video_prompts.py`：即梦、可灵、Runway、Pika 风格视频提示词适配。
- `drama/quality.py`：剧情连续性、角色覆盖、镜头可拍性、提示词完整性质量检查。
- `drama/pipeline.py`：小说到短剧生产资产包的完整 pipeline 和 artifact 写出。
- `drama/api.py` 与 `drama/fastapi_router.py`：短剧生产 workflow API handlers 和 route contract。
- `providers/media_generation.py`：图片/视频生成任务提交、任务轮询、资产记录写入的通用 HTTP provider client。
- `drama/media_assets.py`：角色定妆图任务和分镜视频任务提交编排。
- `drama/generation_api.py`：图片/视频生成 API handlers。
- `media/provider_gateway.py`、`media/repository.py`、`media/review_workflow.py`：平台媒体 gateway profile、资产仓库、人工审核流已完成。
- `drama/skills.py` 与 `configs/skills/foundation_skills.json`：短剧核心 skills 已 active。

## 已完成标记

```text
P0_contracts_implemented_v1 = true
P1_foundation_runtime_implemented_v1 = true
P1_configurable_primary_model_policy_implemented_v1 = true
P1_workspace_project_model_settings_store_implemented_v1 = true
P1_workspace_project_model_settings_api_implemented_v1 = true
P1_openai_responses_provider_adapter_implemented_v1 = true
P1_openai_responses_provider_smoke_implemented_v1 = true
P1_openai_responses_native_streaming_implemented_v1 = true
P1_request_workspace_project_task_model_override_implemented_v1 = true
P1_model_route_privacy_context_cost_guards_implemented_v1 = true
P1_model_fallback_chain_implemented_v1 = true
P1_hardening_implemented_v1 = true
P1_model_versions_registry_implemented_v1 = true
P1_foundation_api_contract_documented_v1 = true
P1_foundation_boundary_documented_v1 = true
P1_run_checks_core_coverage_implemented_v1 = true
P1_foundation_release_checklist_implemented_v1 = true
P1_memory_roadmap_documented_v1 = true
P1_sqlite_memory_backend_implemented_v1 = true
P1_vector_memory_backend_implemented_v1 = true
P1_memory_backend_selection_implemented_v1 = true
P1_memory_api_backend_selection_implemented_v1 = true
P1_memory_quality_governance_implemented_v1 = true
P2_foundation_capabilities_implemented_v1 = true
P2_expanded_golden_dataset_quality_gate_implemented_v1 = true
P2_cloud_deploy_profile_implemented_v1 = true
P2_managed_secret_waf_cdn_slo_profile_implemented_v1 = true
P2_external_queue_cross_region_dispatch_contract_implemented_v1 = true
P2_billing_usage_record_reconciliation_export_implemented_v1 = true
P3_media_gateway_asset_review_workflow_implemented_v1 = true
P3_novel_parsing_implemented_v1 = true
P3_novel_to_drama_outline_implemented_v1 = true
P3_character_system_implemented_v1 = true
P3_storyboard_planning_implemented_v1 = true
P3_ai_video_prompt_generation_implemented_v1 = true
P3_short_drama_quality_checks_implemented_v1 = true
P3_short_drama_workflow_api_implemented_v1 = true
P3_direct_image_generation_adapter_implemented_v1 = true
P3_direct_video_generation_adapter_implemented_v1 = true
P3_media_generation_asset_tracking_implemented_v1 = true
P3_drama_skills_active_implemented_v1 = true
runtime_services_completed = partially
implementation_completed = false
```

## 当前最重要的未完成项

1. 真实云账号中的 Kubernetes cluster / Terraform apply 尚未执行。
2. 真实域名、证书、WAF、CDN 尚未绑定到云平台。
3. 真实 AWS/GCP/Azure/Vault SDK 调用需要具体云环境和权限。
4. 真实外部 MQ adapter 需要选择 Redis/RabbitMQ/SQS/PubSub 之一并提供连接信息。
5. 真实 provider 账单文件需要接入具体平台导出格式。
6. 平台专属媒体网关需要具体平台 endpoint、鉴权、额度、callback 和资产存储桶。
7. 外部向量数据库和真实 embedding provider 尚未接入。
8. OpenAI Responses provider 的真实账号、模型名、密钥、组织策略、额度和 live smoke 仍需在部署环境配置。

## 禁止误判

- OpenAI Responses adapter/native streaming 完成，不等于真实 OpenAI API key、模型名、额度、组织策略已经配置成功。
- workspace/project model settings API 完成，不等于 UI 管理后台已经完成。
- 可配置主模型完成，不等于所有 provider 的账号、额度、模型名和真实调用都已配置成功。
- `external.openai.primary` 只是一个可配置 primary candidate，不是系统写死的唯一主模型。
- 仓库级 cloud profile 完成，不等于已经对某个云账号执行 `terraform apply`。
- Managed secret contract 完成，不等于真实云 secret manager 已经授权可读。
- WAF/CDN/SLO profile 完成，不等于真实域名和证书已经绑定。
- External queue contract 完成，不等于 Redis/RabbitMQ/SQS/PubSub 已经部署。
- Billing usage reconciliation 完成，不等于已经接入所有第三方平台真实账单格式。
- Media gateway/repository/review workflow 完成，不等于具体第三方视频平台的 endpoint 和回调已开通。
- SQLite/vector memory backend 完成，不等于外部向量数据库和真实 embedding provider 已经完成。
- Foundation 边界文档完成，不等于 ForgePilot 已经开发完成。
- Repository-level hardening 完成，不等于已经部署到某个云平台生产环境。
- 训练 runbook 不等于模型已经训练完成。
