# 通用本地大模型基座策略

本项目后续不应只训练“小说转短剧”能力，而应把 Qwen 作为一个本地通用大模型基座，再在其上叠加垂直能力模块。

## 长期定位

```text
Local AI Foundation Base
= 通用助手 + 编程助手 + Agent/工具调用 + MCP/插件意识 + AI 内容生产 + AI短剧/漫剧垂直能力
```

AI 短剧/AI 漫剧只是其中一个内容生产模块，不是整个基座的边界。

## 能力分层

| 层级 | 能力 | 示例 |
|---|---|---|
| Core Assistant | 通用问答、总结、规划、结构化输出 | 本地个人助手 |
| Coding Assistant | 代码解释、生成、重构、测试建议 | 类 Trae / Claude Code 桌面工具基础 |
| Agent Skills | 任务拆解、工具选择、插件调用规划 | Skill / Plugin / MCP 编排 |
| Content Factory | 文案、剧本、分镜、提示词 | AI 短剧、AI 漫剧、营销内容 |
| Domain Modules | 垂直行业微调 | novel2drama、comic、legal、finance 等 |

## 当前项目如何调整

第一版仍保留 `qwen-novel2drama-llm` 名称和短剧数据，因为这是第一个垂直任务闭环；但新增 `foundation_base` 数据集和通用提示词，使训练路线可以变成：

1. 通用本地助手基础能力。
2. 编程助手与工具调用意识。
3. Agent / MCP / 插件工作流理解。
4. AI 内容生产能力。
5. AI 短剧/漫剧垂直能力。

## 不在本阶段实现的平台能力

以下能力只做基座预留，不在当前工程直接开发桌面客户端或平台：

- 类 Trae / Claude Code 桌面客户端。
- Skill marketplace。
- MCP server/client 管理。
- 插件运行沙箱。
- AI 短剧/漫剧制作发布平台。
- 多模型商业接入网关。

当前工程只负责：数据格式、训练配置、推理接口、评估和模型基座能力设计。
