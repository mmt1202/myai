# P2 Foundation Capabilities

P2 expands the P1 foundation from a single-provider local/runtime base into a multi-provider, resilient, multimodal, evaluable and observable foundation layer.

## Completed repository-level P2 tasks

| ID | Capability | Implemented files | Status |
| --- | --- | --- | --- |
| P2-001 | Multi-provider catalog | `providers/provider_catalog.py`, `configs/model_instance_registry.json` | Completed |
| P2-002 | Provider fallback / retry / circuit breaker | `providers/resilience.py` | Completed |
| P2-003 | Multimodal routing contract | `services/multimodal_router.py` | Completed |
| P2-004 | MCP SDK compatibility layer | `mcp/sdk_compat.py` | Completed |
| P2-005 | Evaluation system | `evals/eval_runner.py`, `evals/golden/foundation_smoke.json` | Completed |
| P2-006 | Observability / tracing | `services/tracing.py`, `services/metrics.py` | Completed |
| P2-007 | Audit query / export / retention | `services/audit_query.py` | Completed |
| P2-008 | Deploy profile / CI deploy validation | `scripts/deploy_profile.py`, `.github/workflows/foundation-deploy-profile.yml` | Completed |

## P2-001 Multi-provider catalog

The provider catalog includes environment-driven profiles for:

- DeepSeek
- Qwen / DashScope
- Anthropic-compatible gateway
- Gemini-compatible gateway

The model instance registry includes concrete provider instance templates with capability and modality metadata. These are configuration contracts; real provider calls still require correct gateway/base URL/model/key environment configuration.

## P2-002 Provider resilience

Provider resilience includes:

- retryable error classification
- exponential backoff delay plan
- circuit breaker state transitions
- provider health scoring
- fallback candidate ranking

This is dependency-free policy logic and can be used by router/runtime layers.

## P2-003 Multimodal routing

Multimodal routing includes:

- input modality inference from content blocks
- output modality selection
- model candidate filtering by `input_modalities` and `output_modalities`
- normalized multimodal block shape

## P2-004 MCP SDK compatibility

The compatibility layer includes:

- MCP initialize/list-tools/call request shapes
- MCP tool schema normalization
- foundation tool schema conversion
- MCP session state transition contract

## P2-005 Eval system

The eval system includes:

- golden case loading
- deterministic runner contract
- score/check report shape
- smoke golden dataset

Future eval suites can attach router, provider, tool-loop and agent-run runners.

## P2-006 Observability / tracing

Tracing and observability include:

- trace/span ID generation
- span lifecycle
- JSONL span persistence
- trace summary
- Prometheus-style metrics renderer from hardening

## P2-007 Audit query / export / retention

Audit query helpers include:

- load audit JSONL events
- filter by workspace, owner, decision and time window
- JSONL export
- retention filtering

## P2-008 Deploy profile

Deploy profile validation includes:

- required repository deployment artifacts
- CI workflow for deploy profile checks
- production preflight integration
- explicit cloud-specialization TODO list

## Still not implemented: cloud/platform specialization

The following are intentionally marked as not completed because they require selecting and configuring real infrastructure outside the repository:

| Item | Status | Reason |
| --- | --- | --- |
| Kubernetes / Terraform | Not completed | Requires cloud/platform target and cluster/IaC decisions. |
| AWS/GCP/Azure/Vault secret manager | Not completed | Requires a chosen secret manager and real deployment identity. |
| Real certificates, domain, WAF, CDN | Not completed | Requires domain ownership, certificate issuance and edge provider. |
| Prometheus/Grafana/SLO alerting deployment | Not completed | Repository has metrics contract, but not a deployed monitoring stack. |
| Real backup policy and RPO/RTO drill | Not completed | Repository has backup/restore planner, but not production retention policy or drill evidence. |
| External MQ / cross-region scheduling | Not completed | Repository has internal dispatcher/pool, but not external queue infrastructure. |
| Real billing invoice import/export | Not completed | Repository has readiness helpers, not provider invoice integrations. |

## Suggested P2 tests

```bash
python -m unittest tests.test_provider_catalog_resilience tests.test_multimodal_router tests.test_mcp_sdk_compat tests.test_eval_runner tests.test_tracing tests.test_audit_query tests.test_deploy_profile
```
