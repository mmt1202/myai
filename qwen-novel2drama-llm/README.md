# qwen-novel2drama-llm

基于 Qwen 开源大模型的“小说转 AI 短剧专用大模型”LoRA / QLoRA 微调工程。项目目标不是从 0 预训练 GPT 级模型，而是在 Qwen2.5-Instruct 等底座上做垂直领域 SFT，服务小说理解、短剧大纲、分集剧情、角色设定、场景设定、竖屏分镜、AI 视频提示词、配音台词、爽点反转设计和后续业务平台接入。

## 为什么选择 Qwen

Qwen 系列中文能力强、生态完善、开源模型尺寸丰富，适合从 1.5B 到 7B 逐步验证。第一版优先支持：

- Qwen2.5-1.5B-Instruct
- Qwen2.5-3B-Instruct
- Qwen2.5-7B-Instruct
- 后续可扩展 Qwen3-4B / Qwen3-8B

## 为什么不是从 0 训练

从 0 预训练需要海量语料、GPU 集群和长期工程投入。当前目标是“小说转 AI 短剧”的垂直能力，因此更适合基于强中文底座做 LoRA / QLoRA 微调。

## LoRA / QLoRA 是什么

- LoRA：只训练少量低秩适配参数，成本低、训练快。
- QLoRA：在 4bit 量化底座模型上训练 LoRA，进一步降低显存占用。

## 目录说明

```text
datasets/   训练与验证 JSONL 数据
configs/    LLaMA-Factory 训练配置
scripts/    数据处理、训练、合并脚本
inference/  transformers 推理和 FastAPI 服务
prompts/    专业提示词模板
eval/       人工评估辅助脚本
docs/       训练、数据、Windows、选型文档
```

## 环境安装

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# Linux/macOS
source .venv/bin/activate
pip install -r requirements.txt
```

注意：`bitsandbytes` 在 Windows 上可能存在兼容问题。Windows 用户如果训练 7B QLoRA 遇到问题，建议使用 WSL2 或 Linux 环境。

## Windows PowerShell 运行方式

```powershell
python scripts\validate_dataset.py --file datasets\train.jsonl
.\scripts\train_lora.ps1
```

## Linux/macOS 运行方式

```bash
python scripts/validate_dataset.py --file datasets/train.jsonl
bash scripts/train_lora.sh
```

## 数据格式

每行一个 JSON：

```json
{"instruction":"请把下面小说片段改编成一集 60 秒竖屏 AI 短剧分镜脚本","input":"林晚站在订婚宴门口……","output":"标题：订婚宴上的背叛\n核心冲突：……"}
```

训练数据只能使用你自己整理的数据，或未来使用符合许可的开源模型生成的数据。不要使用 GPT、Claude、Gemini 等闭源商业模型输出作为训练数据。

## 校验数据

```bash
python scripts/validate_dataset.py --file datasets/train.jsonl
python scripts/validate_dataset.py --file datasets/val.jsonl
```

## 拆分数据

```bash
python scripts/split_dataset.py --input datasets/raw_examples.jsonl --train datasets/train.jsonl --val datasets/val.jsonl --val-ratio 0.1 --seed 42
```

## 准备小说数据

```bash
python scripts/prepare_data.py --input-dir raw_novels --output datasets/raw_examples.jsonl --chunk-size 1200
```

生成的 `output` 为空，需要人工补写高质量答案后再训练。

## 开始训练

训练依赖 LLaMA-Factory。安装并确认 `llamafactory-cli` 可用后运行：

```bash
bash scripts/train_lora.sh configs/qwen2_5_1_5b_lora.yaml
```

Windows：

```powershell
.\scripts\train_lora.ps1 -Config configs/qwen2_5_1_5b_lora.yaml
```

## 本地推理

```bash
python inference/chat.py --model-path Qwen/Qwen2.5-1.5B-Instruct
```

加载 LoRA：

```bash
python inference/chat.py --model-path Qwen/Qwen2.5-1.5B-Instruct --adapter-path saves/qwen2_5_1_5b_lora
```

## 启动 API 服务

```bash
python inference/api_server.py --model-path Qwen/Qwen2.5-1.5B-Instruct --host 127.0.0.1 --port 8000
python inference/client_test.py
```

## 接入业务系统

后端、PC 端、移动端可调用 `POST /generate`，传入 prompt、max_new_tokens、temperature，返回结构化生成结果。后续可扩展鉴权、队列、任务状态、模型路由和多端项目 ID。

## 显卡选型

- 无 GPU：只建议推理小模型，不建议训练。
- 8GB 显存：Qwen2.5-1.5B / 3B LoRA。
- 12GB 显存：Qwen2.5-3B。
- 16GB 显存：Qwen2.5-7B QLoRA 尝试。
- 24GB 显存：Qwen2.5-7B 更合适。

## 常见问题

- CUDA 不可用：检查 PyTorch CUDA 版本、显卡驱动和 `torch.cuda.is_available()`。
- 显存不足：降低 batch size、cutoff_len、LoRA rank，或改用 QLoRA。
- transformers 下载失败：检查 Hugging Face 网络、代理和缓存目录。
- Hugging Face 访问失败：可配置镜像源或提前手动下载模型。
- Windows 路径问题：优先使用 PowerShell，并从项目根目录运行脚本。
- Python 版本问题：建议 Python 3.10 或 3.11。
- pip 安装失败：升级 pip，必要时使用国内镜像。
- LLaMA-Factory 未安装：先安装 LLaMA-Factory，并确认 `llamafactory-cli` 在 PATH 中。
