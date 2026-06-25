# API active model startup

After a model version is registered with `--activate`, the API can load it from `configs/model_versions.json`.

Use active version:

```bash
python inference/api_server.py --model-versions configs/model_versions.json --system-prompt-file prompts/system_prompt.txt
```

Use a named version:

```bash
python inference/api_server.py --model-versions configs/model_versions.json --model-version qwen2_5_1_5b_lora_v1 --system-prompt-file prompts/system_prompt.txt
```

Bypass registry and load a direct path:

```bash
python inference/api_server.py --model-path models/qwen2_5_1_5b_lora_v1-merged --system-prompt-file prompts/system_prompt.txt
```

`GET /health` returns the loaded `model_version` and `model_path`.
