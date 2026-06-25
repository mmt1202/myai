# 多轮数据建设说明

第一版训练配置以 `instruction/input/output` 单轮 SFT 为主，但后续可以补充多轮数据，让模型学会：

1. 先分析小说冲突，再生成短剧大纲。
2. 先生成角色设定，再保持角色一致性生成分镜。
3. 先生成分镜，再继续生成 AI 视频提示词。
4. 用户追问修改风格、压缩时长、增强爽点。

## messages JSONL 示例

```json
{"messages":[{"role":"system","content":"..."},{"role":"user","content":"请分析核心冲突"},{"role":"assistant","content":"..."},{"role":"user","content":"继续改成分镜"},{"role":"assistant","content":"..."}]}
```

示例文件：`datasets/multiturn_examples.jsonl`。

## 单轮样本转换为 messages

```bash
python scripts/convert_to_messages.py --input datasets/train.jsonl --output outputs/train_messages.jsonl --system-prompt-file prompts/system_prompt.txt
```

注意：转换得到的是单轮 messages 样本。真正的多轮能力仍需要人工设计连续对话样本。
