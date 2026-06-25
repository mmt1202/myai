# 实现状态

这个文件用于区分项目已经能跑的部分和还需要继续开发的部分。当前项目长期定位已经调整为“本地通用 AI 大模型基座”，短剧/漫剧只是后续产品应用层之一。

## 已经能跑

P0 文本生成基础运行时：

- `inference/model_utils.py`：文本模型加载与生成。
- `configs/model_registry.json`：模型运行时注册表。
- `configs/foundation_capability_matrix.json`：通用基座能力矩阵。
- `scripts/inspect_model_registry.py`：查看模型运行时注册表。
- `scripts/inspect_foundation_capabilities.py`：查看通用基座能力矩阵。
- `scripts/plan_training_run.py`：生成训练运行 manifest。
- `scripts/register_model_version.py`：登记训练后的模型版本。
- `inference/api_server.py`：可从 active model version 启动 API。

可用命令：

```bash
python scripts/inspect_model_registry.py
python scripts/inspect_foundation_capabilities.py
python scripts/inspect_foundation_capabilities.py --status planned
python scripts/inspect_foundation_capabilities.py --stage P1
python scripts/plan_training_run.py --config configs/qwen2_5_1_5b_lora.yaml --run-name qwen2_5_1_5b_lora_v1
```

## 当前定位

当前不是只做 AI 短剧模型，而是先建设一个通用本地 AI 基座。后续可以在这个基座之上发展：

- AI 短剧/漫剧工厂平台。
- Claude Code / Codex / Trae 类桌面编程助手和 CLI。
- 多模型接入。
- Skill、插件和 MCP。
- RAG、记忆和知识库。
- 视觉、语音和多模态。
- Agent 工作流。

## 后续开发顺序

1. P0：跑通真实数据、LoRA 训练、合并、推理、评测、模型版本登记。
2. P1：通用对话、长上下文、复杂推理、代码能力、工具调用。
3. P2：Skill、插件、MCP、RAG、Qwen-VL、Qwen-TTS、Qwen-ASR。
4. P3：Qwen-Omni、多模态统一运行时、Agent 编排。
5. Product：AI 短剧/漫剧工厂、代码桌面客户端、CLI 工具等产品层。
