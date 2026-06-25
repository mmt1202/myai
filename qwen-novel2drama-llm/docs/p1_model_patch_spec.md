# P1 Model-generated patch spec

This layer prepares a safe bridge between a model and the patch workflow.

The model should not edit files directly. It should only generate a structured `patch_spec_v1` JSON object.

## Build model prompt payload

First create an agent workflow run:

```bash
python scripts/run_agent_workflow.py --task "your change request" --output-dir outputs/agent_runs/demo
```

Then build a prompt payload for a model:

```bash
python scripts/build_patch_spec_prompt.py \
  --workflow outputs/agent_runs/demo/workflow_manifest.json \
  --patch-plan outputs/agent_runs/demo/patch_plan.json \
  --output outputs/model_prompts/demo_patch_spec_prompt.json
```

The payload includes:

- task
- output schema
- workflow summary
- patch plan target files
- related symbols
- selected file chunks
- output contract

## Validate model output

After a model writes a patch spec JSON file:

```bash
python scripts/validate_patch_spec.py \
  --spec outputs/model_outputs/patch_spec.json \
  --patch-plan outputs/agent_runs/demo/patch_plan.json
```

The validator checks:

- required top-level fields
- path safety
- target files are allowed by the patch plan
- replace operations include exact `find`, `replace`, and `count`
- append operations include non-empty `append`

## Safe downstream workflow

```bash
python scripts/validate_patch_spec.py --spec outputs/model_outputs/patch_spec.json --patch-plan outputs/agent_runs/demo/patch_plan.json
python scripts/create_unified_diff.py --spec outputs/model_outputs/patch_spec.json --output outputs/patches/model_generated.diff
python scripts/apply_patch_spec.py --spec outputs/model_outputs/patch_spec.json --dry-run
python scripts/apply_patch_spec.py --spec outputs/model_outputs/patch_spec.json --confirm APPLY
python scripts/run_test_plan.py --plan outputs/agent_runs/demo/patch_plan.json
```

This keeps model generation separate from file mutation.
