# P1 Safe patch applier

The safe patch applier applies a structured patch spec. It is intentionally conservative.

It does not apply arbitrary diff files. It applies exact `find` / `replace` or `append` operations from a JSON patch spec.

## Dry run

Dry run is the default behavior unless `--confirm APPLY` is provided.

```bash
python scripts/apply_patch_spec.py --spec configs/patch_spec_example.json --dry-run
```

## Apply changes

```bash
python scripts/apply_patch_spec.py --spec configs/patch_spec_example.json --confirm APPLY
```

## Custom report

```bash
python scripts/apply_patch_spec.py \
  --spec configs/patch_spec_example.json \
  --report outputs/patch_apply/example_apply.json \
  --dry-run
```

## Safety behavior

The applier:

- blocks paths outside the project root
- requires exact text matches
- validates optional `count`
- defaults to dry-run
- requires `--confirm APPLY` before writing files
- writes a JSON apply report

## Recommended flow

```bash
python scripts/create_patch_plan.py --task "your change request"
python scripts/create_unified_diff.py --spec configs/patch_spec_example.json --output outputs/patches/example.diff
python scripts/apply_patch_spec.py --spec configs/patch_spec_example.json --dry-run
python scripts/apply_patch_spec.py --spec configs/patch_spec_example.json --confirm APPLY
python scripts/run_test_plan.py --plan outputs/patch_plan.json
```
