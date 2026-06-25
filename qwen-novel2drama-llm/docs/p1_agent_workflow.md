# P1 Agent workflow

The agent workflow runner is the first end-to-end coding-agent orchestration layer.

It does not edit files by default. It creates reproducible planning artifacts for a task.

## Run workflow

```bash
python scripts/run_agent_workflow.py --task "add /models endpoint to api_server"
```

Custom output directory:

```bash
python scripts/run_agent_workflow.py \
  --task "add active model info to health endpoint" \
  --output-dir outputs/agent_runs/api_health_model
```

## Artifacts

Each run writes:

- `context_index.json`
- `code_symbols.json`
- `patch_plan.json`
- `test_plan_report.json`
- `workflow_manifest.json`

## Test behavior

By default, tests are dry-run only.

To execute tests from the patch plan:

```bash
python scripts/run_agent_workflow.py --task "your change request" --execute-tests
```

## Recommended next step

After the workflow creates a patch plan:

```bash
python scripts/read_context_chunk.py --path selected/file.py --chunk 0
python scripts/create_unified_diff.py --spec configs/patch_spec_example.json --output outputs/patches/example.diff
python scripts/apply_patch_spec.py --spec configs/patch_spec_example.json --dry-run
```

The runner is intentionally a planner and validator, not an autonomous code modifier.
