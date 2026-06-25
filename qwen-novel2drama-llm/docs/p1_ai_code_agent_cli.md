# P1 AI code agent CLI

`ai_code_agent.py` is the first full CLI wrapper for the coding-agent workflow.

It is safe by default:

- no model call unless `--model-url` is provided
- no file write unless `--apply` is provided
- no real test execution unless `--execute-tests` is provided

## Planning only

```bash
python scripts/ai_code_agent.py --task "add /models endpoint to api_server"
```

This writes planning artifacts under `outputs/ai_code_agent_runs/<timestamp>/`.

## With OpenAI-compatible model

```bash
MODEL_API_KEY=your_key python scripts/ai_code_agent.py \
  --task "add /models endpoint to api_server" \
  --model-url http://localhost:8000/v1/chat/completions \
  --model local-qwen \
  --model-mode openai_compatible
```

## With local generate API

```bash
python scripts/ai_code_agent.py \
  --task "add /models endpoint to api_server" \
  --model-url http://localhost:8000/generate \
  --model-mode local_generate
```

## With existing patch spec

```bash
python scripts/ai_code_agent.py \
  --task "review existing patch spec" \
  --patch-spec outputs/model_outputs/patch_spec.json
```

## Apply changes after review

```bash
python scripts/ai_code_agent.py \
  --task "your change request" \
  --patch-spec outputs/model_outputs/patch_spec.json \
  --apply
```

## Execute tests

```bash
python scripts/ai_code_agent.py \
  --task "your change request" \
  --patch-spec outputs/model_outputs/patch_spec.json \
  --execute-tests
```

## Main artifacts

The CLI writes:

- `workflow_manifest.json`
- `patch_plan.json`
- `patch_spec_prompt.json`
- `patch_spec.json` when model output or input patch spec exists
- `patch_spec_validation.json`
- `generated.diff`
- `patch_apply_dry_run.json` or `patch_apply_applied.json`
- `test_report.json`
- `ai_code_agent_report.json`

## Rule

The model only generates patch specs. The repository is changed only through the safe patch applier.
