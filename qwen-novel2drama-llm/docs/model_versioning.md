# Model versioning

This project does not commit model weights. It only commits metadata that points to local or server-side model artifacts.

## Registry file

Tracked registry:

```text
configs/model_versions.json
```

Ignored artifacts:

```text
saves/
models/
outputs/
```

## Register a version

After creating a training manifest and running training, register the adapter and merged model paths:

```bash
python scripts/register_model_version.py \
  --version qwen2_5_1_5b_lora_v1 \
  --manifest outputs/training_runs/qwen2_5_1_5b_lora_v1.json \
  --adapter-path saves/qwen2_5_1_5b_lora \
  --merged-model-path models/qwen2_5_1_5b_lora_v1-merged \
  --eval-result eval/qwen2_5_1_5b_lora_v1_results.jsonl \
  --notes "first P0 text LoRA run" \
  --activate
```

The registry records:

- base model
- training manifest path and hash
- training config path and hash
- train and validation data hashes
- adapter path
- merged model path
- eval result path and hash
- active version

## Show current versions

```bash
cat configs/model_versions.json
```

## Rule

Do not commit weights. Commit only metadata and documentation.
