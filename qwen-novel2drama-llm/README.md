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
scripts/    数据处理、项目检查、训练、合并脚本
inference/  transformers 推理、共享模型工具和 FastAPI 服务
prompts/    专业提示词模板（大纲、角色、场景、分镜、视频、配音、钩子反转）
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

`datasets/dataset_info.json` 同时注册了 `novel2drama` 和 `novel2drama_val`，训练配置通过 `eval_dataset: novel2drama_val` 显式使用验证集。


## 专业提示词模板

`prompts/` 目录提供可直接复制到本地推理、API 调用或标注流程中的模板：

- `system_prompt.txt`：通用系统角色和工作原则。
- `novel_to_drama_prompt.txt`：小说转短剧大纲。
- `character_prompt.txt`：角色卡和一致性关键词。
- `scene_prompt.txt`：场景卡、空间布局、光线和竖屏构图。
- `storyboard_prompt.txt`：镜头级竖屏分镜脚本。
- `video_prompt.txt`：即梦 AI / 可灵 AI / Runway / Pika 视频提示词。
- `dubbing_prompt.txt`：AI 配音台词表。
- `hook_twist_prompt.txt`：前 3 秒钩子、爽点和反转设计。

## 项目静态检查

在训练前建议先运行项目级检查，确认关键文件、数据集注册、训练配置和模型权重忽略规则没有问题：

```bash
python scripts/check_project.py --project-root .
```

## 校验数据

```bash
python scripts/validate_dataset.py --file datasets/train.jsonl
python scripts/validate_dataset.py --file datasets/val.jsonl
```

## 拆分数据

```bash
python scripts/split_dataset.py --input datasets/raw_examples.jsonl --train datasets/train.jsonl --val datasets/val.jsonl --val-ratio 0.1 --seed 42
```


## 合规采集真实语料

如果你拥有小说版权或已获得训练授权，可以先维护来源清单，再采集网页正文：

```bash
python scripts/collect_web_text.py --sources datasets/sources.example.jsonl --output datasets/raw_corpus.jsonl
```

采集脚本默认检查 `robots.txt`，并要求来源清单显式声明 `allow_training: true` 和授权说明。未授权小说站、付费章节、盗版内容不要用于训练。详细说明见 `docs/data_collection.md`。

采集后可以转换为待人工标注模板：

```bash
python scripts/corpus_to_sft_template.py --input datasets/raw_corpus.jsonl --output datasets/annotation_todo.jsonl --chunk-size 1200
```

## 准备小说数据

```bash
python scripts/prepare_data.py --input-dir raw_novels --output datasets/raw_examples.jsonl --chunk-size 1200
```

生成的 `output` 为空，需要人工补写高质量答案后再训练。




## 数据集建设计划

数据任务比例配置在 `datasets/task_mix.json`，可以按 500/1000/3000 条目标生成建设计划：

```bash
python scripts/plan_dataset_mix.py --total 500
python scripts/plan_dataset_mix.py --total 1000 --output outputs/dataset_plan_1000.json
```

详细说明见 `docs/dataset_plan.md`。

## 数据质量分析、去重和抽样

训练前建议先分析数据质量，并抽样人工复核：

```bash
python scripts/analyze_dataset.py --file datasets/train.jsonl --output outputs/train_report.json
python scripts/dedupe_dataset.py --input datasets/train.jsonl --output outputs/train.dedup.jsonl --mode instruction_input
python scripts/sample_dataset.py --input datasets/train.jsonl --output outputs/sample_review.jsonl --size 20 --seed 42
```

标注规范见 `docs/annotation_guide.md`，人工评估标准见 `eval/scoring_guide.md`。

## 运行轻量测试

项目包含基于 `unittest` 的轻量测试，不需要下载模型：

```bash
python -m unittest discover -s tests
```

也可以一次性运行项目检查、数据校验、单元测试和语法检查：

```bash
python scripts/run_checks.py --project-root .
```


## 环境诊断

训练前可以先检查 Python、依赖、CUDA 和 LLaMA-Factory 命令是否可用：

```bash
python scripts/check_environment.py
python scripts/check_environment.py --check-torch
```

LLaMA-Factory 安装和排错见 `docs/llamafactory_setup.md`。

## 开始训练

训练依赖 LLaMA-Factory。训练脚本会自动切换到项目根目录、校验 train/val 数据，并在 `llamafactory-cli` 不存在时给出安装提示。安装并确认 `llamafactory-cli` 可用后运行：

```bash
bash scripts/train_lora.sh configs/qwen2_5_1_5b_lora.yaml
```

Windows：

```powershell
.\scripts\train_lora.ps1 -Config configs/qwen2_5_1_5b_lora.yaml
```

## 本地推理

```bash
python inference/chat.py --model-path Qwen/Qwen2.5-1.5B-Instruct --system-prompt-file prompts/system_prompt.txt
```

加载 LoRA：

```bash
python inference/chat.py --model-path Qwen/Qwen2.5-1.5B-Instruct --adapter-path saves/qwen2_5_1_5b_lora
```

## 启动 API 服务

```bash
python inference/api_server.py --model-path Qwen/Qwen2.5-1.5B-Instruct --system-prompt-file prompts/system_prompt.txt --host 127.0.0.1 --port 8000
python inference/client_test.py
```


## 评估结果对比

训练前后可以分别运行 `eval/run_eval.py` 生成 JSONL，然后对比：

```bash
python eval/compare_results.py --base eval/base_results.jsonl --candidate eval/lora_results.jsonl --output eval/compare_results.csv
```

## 接入业务系统

后端、PC 端、移动端可调用 `POST /generate`，传入 prompt、max_new_tokens、temperature，返回结构化生成结果。建议业务侧为每次生成保存：用户 ID、项目 ID、原始小说片段、提示词模板版本、模型版本、生成结果和人工评分。后续可扩展鉴权、队列、任务状态、模型路由和多端项目 ID。


## 依赖分层

第一版保留 `requirements.txt` 作为全量入门依赖，同时提供分层依赖：

- `requirements-train.txt`：训练相关依赖。
- `requirements-api.txt`：本地 API 推理服务依赖。
- `requirements-dev.txt`：开发和轻量测试依赖。
- `requirements-windows.txt`：Windows 入口说明，bitsandbytes 不兼容时建议 WSL2/Linux。

## 部署预留

已提供 `Dockerfile` 和 `deploy/` 文档，预留 Docker、vLLM、Ollama、GGUF 路线。第一版不会自动下载、转换或提交任何模型权重。

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
