# P1 Patch planning

Patch planning is a coding-agent foundation feature.

The goal is to generate a structured plan before editing files. This keeps future agent changes smaller, easier to review and easier to test.

## Prerequisites

Build the project context index and code-symbol index first:

```bash
python scripts/build_context_index.py
python scripts/build_code_symbols.py
```

## Create a patch plan

```bash
python scripts/create_patch_plan.py --task "add /models endpoint to api_server"
```

Custom output:

```bash
python scripts/create_patch_plan.py \
  --task "add active model version response to health endpoint" \
  --output outputs/patch_plans/api_health_model_version.json
```

## Output fields

The patch plan records:

- task
- created_at
- target_files
- related_symbols
- steps
- tests_to_run
- safety_rules

## Workflow

Recommended coding-agent workflow:

```bash
python scripts/build_context_index.py
python scripts/build_code_symbols.py
python scripts/create_patch_plan.py --task "your change request"
python scripts/search_context_index.py --query keyword
python scripts/search_code_symbols.py --query symbol
python scripts/read_context_chunk.py --path selected/file.py --chunk 0
```

Then edit only the selected files, run the focused tests, and review the diff.

## Current limitations

- Ranking is keyword-based.
- It does not yet analyze call graphs.
- It does not yet generate diffs.
- It does not run tests automatically.

These limitations are intentional for the first implementation. The first goal is safe planning, not autonomous code modification.
