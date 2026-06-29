# Foundation Release Checklist

Use this checklist before declaring a Foundation release stable.

## Required checks

- `configs/model_versions.json` has non-null `active_version`.
- The active model version exists in `versions`.
- `python scripts/run_checks.py` passes.
- `python scripts/check_openapi_contract.py` passes.
- `python -m skills.registry --registry configs/skills/foundation_skills.json --validate` passes.
- `python -m mcp.adapter --registry configs/skills/foundation_skills.json --validate` passes.
- `python inference/model_router.py --request examples/route_request.json` returns `status=routed`.
- API smoke tests pass.
- Provider smoke dry-run passes.
- Postgres optional tests are either skipped by missing environment configuration or pass against a test database.

## Contract checks

- Response envelope fields are stable.
- Error shape is stable.
- Streaming event shape is documented.
- `run_id`, `request_id` and `trace_id` rules are documented.
- Auth and workspace headers are documented.

## Boundary checks

- Foundation does not implement ForgePilot file edit / terminal / Git patch responsibilities.
- Drama pipeline does not claim to generate final media unless media provider runtime is configured.
- Cloud deployment tasks are marked separately from repository-level deployment profile.

## Release decision

A release can be tagged `stable` only when all required checks pass and the boundary checks are reviewed.
