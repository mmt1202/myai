# P1 CI Dependency Profiles

The foundation CI is split into explicit dependency profiles so core checks stay fast and deterministic while heavier provider/model checks remain available on demand.

Implemented files:

- `.github/workflows/foundation-contract-check.yml`
- `.github/workflows/foundation-optional-profiles.yml`
- `scripts/ci_profiles.py`
- `tests/test_ci_profiles.py`
- `requirements/ci-core.txt`
- `requirements/provider-adapter.txt`
- `requirements/api-server.txt`
- `requirements/local-model.txt`
- `requirements/dev.txt`

## Profiles

### `contracts`

Purpose:

- OpenAPI/runtime route consistency.
- Static OpenAPI token contract.
- Contract tests.

Requirements:

```text
requirements/ci-core.txt
```

Runs by default on push and pull request.

### `core`

Purpose:

- Dependency-free core service tests.
- No provider SDKs.
- No FastAPI.
- No torch/transformers/peft.

Requirements:

```text
requirements/ci-core.txt
```

Runs by default on push and pull request.

### `provider-adapter`

Purpose:

- Provider adapter shape tests.
- OpenAI-compatible payload and stream parsing tests with mocks.
- Provider continuation capability/fallback tests.

Requirements:

```text
requirements/provider-adapter.txt
```

This profile is optional and manually triggered through `Foundation Optional Profiles`.

### `api-server`

Purpose:

- FastAPI API server function tests.
- Provider SSE response type tests.
- Agent events API tests.

Requirements:

```text
requirements/api-server.txt
```

This profile is optional and manually triggered through `Foundation Optional Profiles`.

### `local-provider-contract`

Purpose:

- Local provider dry-run/cache/stream contract tests.
- Uses mocks for local model loading.
- Does not install torch or transformers.

Requirements:

```text
requirements/ci-core.txt
```

This profile is optional and manually triggered through `Foundation Optional Profiles`.

### `local-model-imports`

Purpose:

- Heavy dependency import check for the local model stack.
- Validates that torch/transformers/peft dependency installation works in CI.
- Does not download or load real model weights.

Requirements:

```text
requirements/local-model.txt
```

This profile is heavyweight and manually triggered through `Foundation Optional Profiles`.

## Inspect profiles locally

Show default profiles:

```bash
python scripts/ci_profiles.py --profile default
```

Show all profiles as JSON:

```bash
python scripts/ci_profiles.py --profile all --json
```

Print shell commands for a profile:

```bash
python scripts/ci_profiles.py --profile api-server --commands
```

## Default CI workflow

Default workflow:

```text
.github/workflows/foundation-contract-check.yml
```

Runs automatically on:

- push to `main`
- pull requests
- manual dispatch

It runs only:

- `contracts`
- `core`

The default workflow intentionally avoids heavyweight dependencies so core development does not depend on torch, transformers, provider SDKs or external credentials.

## Optional workflow

Optional workflow:

```text
.github/workflows/foundation-optional-profiles.yml
```

It is manually triggered and supports these selections:

- `optional`
- `provider-adapter`
- `api-server`
- `local-provider-contract`
- `heavyweight`
- `local-model-imports`
- `all`

## Current limitations

- `local-model-imports` validates package importability only; it does not load real model weights.
- There is no real provider smoke test with credentials yet.
- There is no GPU CI profile yet.
- Provider SDK profiles should be added when concrete provider adapters are implemented.

## Next steps

- Add provider-specific profiles such as `deepseek-provider`, `qwen-provider`, `gemini-provider`, `claude-provider` after adapters exist.
- Add secret-gated smoke tests for real provider API calls.
- Add optional GPU/local-model loading profile when runner capacity is available.
