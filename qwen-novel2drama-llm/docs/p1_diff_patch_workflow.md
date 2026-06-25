# P1 Diff and patch workflow

This workflow generates a reviewable unified diff from a structured patch spec. It does not edit source files.

## Example command

```bash
python scripts/create_unified_diff.py --spec configs/patch_spec_example.json --output outputs/patches/example.diff --report outputs/patches/example_report.json
```

## Patch spec fields

```json
{
  "task": "update docs wording",
  "changes": [
    {
      "path": "docs/p1_patch_planning.md",
      "find": "old text",
      "replace": "new text",
      "count": 1
    }
  ]
}
```

Supported operations:

- exact `find` and `replace`
- optional `count`
- `append`

## Safety behavior

The generator:

- does not edit source files
- blocks paths outside the project root
- fails if exact find text is missing
- fails if expected count does not match
- writes a unified diff for review

## Recommended flow

```bash
python scripts/create_patch_plan.py --task "your change request"
python scripts/create_unified_diff.py --spec configs/patch_spec_example.json --output outputs/patches/example.diff
python scripts/run_test_plan.py --plan outputs/patch_plan.json --dry-run
```

Next step: add a safe patch applier with explicit confirmation.
