# LLaMA-Factory 安装与检查

训练 LoRA / QLoRA 依赖 LLaMA-Factory。本项目不直接 vendoring LLaMA-Factory，也不会自动下载模型权重。

## 安装思路

1. 准备 Python 虚拟环境。
2. 安装与 CUDA 匹配的 PyTorch。
3. 安装 LLaMA-Factory。
4. 确认 `llamafactory-cli` 可用。
5. 回到本项目根目录运行训练脚本。

## 环境检查

不导入 torch 的轻量检查：

```bash
python scripts/check_environment.py
```

检查 torch / CUDA：

```bash
python scripts/check_environment.py --check-torch
```

JSON 输出：

```bash
python scripts/check_environment.py --check-torch --json
```

## 常见问题

- `llamafactory-cli` 未找到：说明 LLaMA-Factory 没有安装或命令未加入 PATH。
- CUDA 不可用：检查 NVIDIA 驱动、PyTorch CUDA 版本和虚拟环境。
- Windows bitsandbytes 不可用：建议使用 WSL2 或 Linux 服务器训练。
- Hugging Face 下载慢：配置镜像或提前下载模型到本地目录。

## 训练前建议

```bash
python scripts/run_checks.py --project-root .
python scripts/check_environment.py --check-torch
bash scripts/train_lora.sh configs/qwen2_5_1_5b_lora.yaml
```
