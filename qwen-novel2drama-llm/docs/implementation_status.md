# 实现状态

当前项目定位：可部署、可扩展、可观测、可审计、可路由、可控成本的 AI 大模型底座，并已具备 AI 短剧/漫剧 P3 专项能力。

## 已完成能力概览

### P0/P1 Foundation

- 文本生成基础运行时。
- router、token counter、cost estimator、usage ledger、provider usage reconciliation。
- memory、rules、skills、MCP-style adapter。
- auth、audit、rate limit、workspace quota。
- file/SQLite/Postgres run store 与 quota backend。
- Agent events、lifecycle、runtime、tool loop、worker dispatcher、worker pool。
- Postgres migration runner/history。
- provider continuation、provider smoke、local/openai-compatible provider contracts。
- API quota、health/readiness、queue observability、deployment profile、secret resolver、metrics、backup plan、preflight、TLS template。
- `configs/model_versions.json`：active model version 已注册，不再为空。
- `docs/FOUNDATION_API_CONTRACT.md`：Foundation API 契约已固定。
- `docs/FOUNDATION_BOUNDARY.md`：Foundation 与 ForgePilot 职责边界已固定。
- `scripts/run_checks.py`：核心目录 compile、skills validate、MCP validate、router smoke 已纳入检查。
- `docs/FOUNDATION_RELEASE_CHECKLIST.md`：稳定发布检查清单已补齐。
- `services/sqlite_memory_store.py`：SQLite memory backend 已完成。
- `services/vector_memory_store.py`：deterministic vector memory backend 已完成。
- `services/memory_store.py`：`FOUNDATION_MEMORY_BACKEND=file|sqlite|vector` backend selection 已完成。
- `inference/api_server.py`：Memory API 已接入 selectable backend，readiness 暴露 `memory_backend`。
- `docs/MEMORY_ROADMAP.md`：Memory 后端状态、API 兼容和后续路线已更新。

### P2 Foundation

- `providers/provider_catalog.py`：DeepSeek、Qwen/DashScope、Anthropic、Gemini provider catalog。
- `providers/resilience.py`：retry、fallback、circuit breaker、provider health scoring。
- `services/multimodal_router.py`：多模态 routing contract。
- `mcp/sdk_compat.py`：MCP SDK compatibility layer。
- `evals/eval_runner.py`：eval runner 和 golden cases。
- `services/tracing.py`：trace/span lifecycle。
- `services/audit_query.py`：audit query/export/retention。
- `scripts/deploy_profile.py`：deploy profile validator。

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
- `drama/skills.py` 与 `configs/skills/foundation_skills.json`：短剧核心 skills 已 active。

## 已完成标记

```text
P0_contracts_implemented_v1 = true
P1_foundation_runtime_implemented_v1 = true
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
P2_foundation_capabilities_implemented_v1 = true
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

1. 大规模 golden dataset 与质量门禁。
2. Kubernetes / Terraform。
3. AWS/GCP/Azure/Vault managed secret manager。
4. 真实证书、域名、WAF、CDN。
5. Prometheus/Grafana/SLO 告警部署。
6. 真实备份策略和 RPO/RTO 演练。
7. 外部 MQ / 跨区域调度。
8. 真实 billing invoice import/export integrations。
9. 平台专属媒体生成网关、资产托管、审核流、人工复核工作台。
10. Memory duplicate/contradiction/merge/compression 高级治理。

## 禁止误判

- SQLite/vector memory backend 完成，不等于外部向量数据库、真实 embedding provider 和高级记忆治理已经完成。
- 直接图片/视频生成 adapter 完成，不等于具体第三方平台账号、端点、额度和平台侧参数已经配置。
- P3 pipeline 完成，不等于已经生成最终成片。
- Media generation job client 完成，不等于资产 CDN、版权检查、审核流和人工复核系统完成。
- Foundation 边界文档完成，不等于 ForgePilot 已经开发完成。
- Repository-level hardening 完成，不等于已经部署到某个云平台生产环境。
- 训练 runbook 不等于模型已经训练完成。
