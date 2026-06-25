# P1 Model API adapter for patch specs

This adapter sends a patch-spec prompt payload to a model API and saves the returned `patch_spec.json`.

It does not apply changes. The output must still pass validation before diff generation or patch application.

## Build prompt first

```bash
python scripts/run_agent_workflow.py --task "your change request" --output-dir outputs/agent_runs/demo
python scripts/build_patch_spec_prompt.py \
  --workflow outputs/agent_runs/demo/workflow_manifest.json \
  --patch-plan outputs/agent_runs/demo/patch_plan.json \
  --output outputs/model_prompts/demo_patch_spec_prompt.json
```

## Dry run request body

```bash
python scripts/call_model_for_patch_spec.py \
  --prompt outputs/model_prompts/demo_patch_spec_prompt.json \
  --mode openai_compatible \
  --url http://localhost:8000/v1/chat/completions \
  --model local-qwen \
  --dry-run
```

## OpenAI-compatible API

```bash
MODEL_API_KEY=your_key python scripts/call_model_for_patch_spec.py \
  --prompt outputs/model_prompts/demo_patch_spec_prompt.json \
  --mode openai_compatible \
  --url https://api.example.com/v1/chat/completions \
  --model qwen-or-gpt-compatible-model \
  --output outputs/model_outputs/patch_spec.json
```

## Local generate API

```bash
python scripts/call_model_for_patch_spec.py \
  --prompt outputs/model_prompts/demo_patch_spec_prompt.json \
  --mode local_generate \
  --url http://localhost:8000/generate \
  --output outputs/model_outputs/patch_spec.json
```

## Safe downstream flow

```bash
python scripts/validate_patch_spec.py --spec outputs/model_outputs/patch_spec.json --patch-plan outputs/agent_runs/demo/patch_plan.json
python scripts/create_unified_diff.py --spec outputs/model_outputs/patch_spec.json --output outputs/patches/model_generated.diff
python scripts/apply_patch_spec.py --spec outputs/model_outputs/patch_spec.json --dry-run
python scripts/apply_patch_spec.py --spec outputs/model_outputs/patch_spec.json --confirm APPLY
python scripts/run_test_plan.py --plan outputs/agent_runs/demo/patch_plan.json
```

API keys are read from environment variables. Do not commit API keys.
