# Codex 连续执行任务总控文档

本文档用于让 Codex 按顺序继续完成 `qwen-novel2drama-llm` 的剩余工程任务。

当前项目定位：可部署、可扩展、可观测、可审计、可路由、可控成本的 AI 大模型底座。

AI 短剧/漫剧专项能力已进入 P3 v1。

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
python -m unittest tests.test_drama_pipeline tests.test_drama_api tests.test_ci_profiles
python -m unittest tests.test_provider_catalog_resilience tests.test_multimodal_router tests.test_mcp_sdk_compat tests.test_eval_runner tests.test_tracing tests.test_audit_query tests.test_deploy_profile
```

---

## 1. 当前已完成基线

```text
P1 foundation and hardening = completed_v1
P2 foundation capabilities = completed_v1
P3 drama pipeline = completed_v1
```

P3 完成标记：

```text
P3_novel_parsing_implemented_v1 = true
P3_novel_to_drama_outline_implemented_v1 = true
P3_character_system_implemented_v1 = true
P3_storyboard_planning_implemented_v1 = true
P3_ai_video_prompt_generation_implemented_v1 = true
P3_short_drama_quality_checks_implemented_v1 = true
P3_short_drama_workflow_api_implemented_v1 = true
```

---

## P3-001：小说解析

状态：已完成。

文件：`drama/novel_parser.py`。

能力：章节解析、人物抽取、世界观抽取、剧情线抽取。

## P3-002：小说转短剧大纲

状态：已完成。

文件：`drama/outline.py`。

能力：剧集结构、单集剧情、开场钩子、冲突升级、转折点、集尾悬念、series bible。

## P3-003：角色设定系统

状态：已完成。

文件：`drama/characters.py`。

能力：角色卡、人物关系、角色一致性规则、视觉 profile、声音 profile、定妆提示词。

## P3-004：分镜规划

状态：已完成。

文件：`drama/storyboard.py`。

能力：镜头列表、景别、镜头调度、动作、台词、旁白、时长估算。

## P3-005：AI 视频提示词生成

状态：已完成。

文件：`drama/video_prompts.py`。

能力：即梦、可灵、Runway、Pika 平台提示词适配。

## P3-006：短剧质检

状态：已完成。

文件：`drama/quality.py`。

能力：剧情连续性、角色覆盖、镜头可拍性、提示词完整性检查。

## P3-007：短剧生产工作流 API

状态：已完成。

文件：`drama/pipeline.py`、`drama/api.py`、`drama/fastapi_router.py`。

能力：从小说文本到解析、剧集大纲、角色系统、分镜、视频提示词、质量报告、资产包写出的完整 pipeline。

---

## 仍未完成的外部专项

```text
Kubernetes / Terraform = not_completed
AWS/GCP/Azure/Vault secret manager = not_completed
证书、域名、WAF、CDN = not_completed
Prometheus/Grafana/SLO deployment = not_completed
backup policy and RPO/RTO drill = not_completed
external MQ / cross-region scheduling = not_completed
billing invoice import/export = not_completed
real image/audio/video provider execution and asset hosting = not_completed
```

---

## 下一阶段

1. Cloud deployment specialization。
2. External queue / billing / asset provider integration。
3. Human review workspace and production asset management。
