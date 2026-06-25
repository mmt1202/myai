# 实现状态

这个文件用于区分项目已经能跑的部分和还需要继续开发的部分。

## 已经能跑

P0 文本生成基础运行时：

- `inference/model_utils.py`：文本模型加载与生成。
- `configs/model_registry.json`：模型运行时注册表。
- `scripts/inspect_model_registry.py`：查看注册表。

可用命令：

```bash
python scripts/inspect_model_registry.py
python scripts/inspect_model_registry.py --status implemented
python scripts/inspect_model_registry.py --status planned
python scripts/inspect_model_registry.py --capability text_generation
```

## 后续开发顺序

1. P0：跑通真实数据、LoRA 训练、合并、推理、评测。
2. P1：接入 Qwen3 文本模型和多轮创作数据。
3. P2：接入 Qwen-VL，用于参考图理解、角色一致性检查和分镜图审核。
4. P2：接入 Qwen-TTS，用于角色配音和旁白。
5. P2：接入 Qwen-ASR，用于字幕转写和素材检索。
6. P3：接入 Qwen-Omni，统一图文音视频理解。
7. P3：接入 Qwen-Agent，编排小说到短剧资产的自动化流程。
