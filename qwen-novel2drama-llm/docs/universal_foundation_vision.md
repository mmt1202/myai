# 通用本地 AI 大模型基座愿景

本项目当前目录名仍保留 `qwen-novel2drama-llm`，但长期定位不应局限于小说转短剧。短剧、漫剧、编程助手、桌面客户端、CLI、Skill、插件、MCP 和 Agent 工作流都应建立在同一个通用 AI 基座之上。

## 目标定位

目标不是只做一个“会写短剧”的小模型，而是构建一个本地可部署、可扩展、可微调、可接入外部模型和工具生态的通用 AI 大模型基座。

对标对象包括：

- Qwen 系列开源模型生态。
- Claude / Claude Code 类代码工作流。
- OpenAI ChatGPT / Codex 类通用对话和编程工作流。
- DeepSeek 类推理和代码能力。
- Trae / Cursor 类 IDE 与桌面编程助手体验。

## 现实边界

个人或小团队很难从零预训练出和商业闭源前沿模型同等级的基础权重。更现实的路线是：

1. 以 Qwen / DeepSeek / 其他开源强模型作为本地底座。
2. 做垂直数据、工具调用、Agent 编排、RAG、插件、MCP、Skills 和产品工作流。
3. 支持多模型路由：本地模型优先，必要时可接入云端模型。
4. 逐步积累自己的数据集、评测集、LoRA/Adapter 和业务能力。

## 分层架构

```text
Universal AI Foundation
├─ Model Runtime        本地模型加载、版本管理、多模型路由
├─ Capability Layer     文本、代码、视觉、语音、多模态、工具调用
├─ Agent Layer          任务规划、工具编排、记忆、上下文管理
├─ Extension Layer      Skill、插件、MCP、外部 API、文件系统、GitHub
├─ Product Layer        AI 短剧工厂、AI 漫剧工厂、Code CLI、桌面客户端
└─ Evaluation Layer     通用评测、代码评测、创作评测、多模态评测
```

## 当前阶段

当前仍处于 P0：本地文本模型训练与推理闭环。

已经在做：

- Qwen 文本模型 LoRA/QLoRA 训练配置。
- 训练 manifest。
- 模型版本登记。
- API 从 active model version 启动。
- Qwen 生态能力规划。

下一阶段应从“短剧专用工程”扩展为“通用基座工程”：

- 通用能力矩阵。
- 通用系统提示词。
- 多任务数据格式。
- 代码能力数据与评测。
- 工具调用和 MCP 接口规划。
- 多模型 runtime 路由。

## 原则

- 短剧/漫剧是应用层，不是基座边界。
- 本地可运行是核心目标。
- 不提交模型权重，只提交配置、脚本、元数据、文档和评测。
- 每个能力必须区分 `implemented`、`in_progress`、`planned`。
- 任何“对标大模型”的能力都必须拆成可验证子能力，而不是只写口号。
