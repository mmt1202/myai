from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class CIProfile:
    name: str
    description: str
    requirements: tuple[str, ...]
    tests: tuple[str, ...]
    import_checks: tuple[str, ...] = ()
    default_on_push: bool = False
    heavyweight: bool = False


PROFILES: dict[str, CIProfile] = {
    "contracts": CIProfile(
        name="contracts",
        description="OpenAPI/runtime contract checks with no third-party dependencies.",
        requirements=("requirements/ci-core.txt",),
        tests=("tests.test_openapi_contract_check", "tests.test_foundation_contracts"),
        default_on_push=True,
    ),
    "core": CIProfile(
        name="core",
        description="Dependency-free foundation service tests.",
        requirements=("requirements/ci-core.txt",),
        tests=(
            "tests.test_foundation_core_services",
            "tests.test_memory_store",
            "tests.test_rule_engine",
            "tests.test_auth_service",
            "tests.test_auth_audit_rate_limit",
            "tests.test_audit_query",
            "tests.test_usage_reconciliation",
            "tests.test_model_tool_loop_usage",
            "tests.test_provider_catalog_resilience",
            "tests.test_provider_continuation",
            "tests.test_provider_session_lifecycle",
            "tests.test_secret_resolver",
            "tests.test_multimodal_router",
            "tests.test_mcp_sdk_compat",
            "tests.test_eval_runner",
            "tests.test_tracing",
            "tests.test_deploy_profile",
            "tests.test_drama_pipeline",
            "tests.test_drama_api",
            "tests.test_run_store",
            "tests.test_sqlite_run_store",
            "tests.test_agent_lifecycle",
            "tests.test_worker_dispatcher",
            "tests.test_worker_pool",
            "tests.test_postgres_migration_history",
            "tests.test_postgres_db_ops",
            "tests.test_postgres_backup",
            "tests.test_workspace_quota",
            "tests.test_quota_store",
            "tests.test_billing_limits",
            "tests.test_metrics",
            "tests.test_production_preflight",
            "tests.test_skill_registry",
            "tests.test_mcp_adapter",
        ),
        default_on_push=True,
    ),
    "provider-adapter": CIProfile(
        name="provider-adapter",
        description="Provider adapter contract tests without live provider calls.",
        requirements=("requirements/provider-adapter.txt",),
        tests=("tests.test_provider_adapter_contract", "tests.test_provider_factory", "tests.test_provider_continuation"),
    ),
    "provider-smoke": CIProfile(
        name="provider-smoke",
        description="Optional provider smoke configuration tests. Live calls are environment-gated.",
        requirements=("requirements/provider-smoke.txt",),
        tests=("tests.test_provider_smoke_config",),
    ),
    "api-server": CIProfile(
        name="api-server",
        description="FastAPI API server tests. Installs the API server dependency profile only.",
        requirements=("requirements/api-server.txt",),
        tests=("tests.test_api_server_foundation",),
    ),
    "postgres-run-store": CIProfile(
        name="postgres-run-store",
        description="Optional Postgres run store contract tests. Real DB tests are DSN gated.",
        requirements=("requirements/postgres-run-store.txt",),
        tests=("tests.test_postgres_run_store_contract",),
    ),
    "postgres-quota": CIProfile(
        name="postgres-quota",
        description="Optional Postgres quota store contract tests. Real DB tests are DSN gated.",
        requirements=("requirements/postgres-quota.txt",),
        tests=("tests.test_postgres_quota_store",),
    ),
    "local-provider-contract": CIProfile(
        name="local-provider-contract",
        description="Local provider dry-run/cache/streaming contract tests using mocks, without installing torch or transformers.",
        requirements=("requirements/ci-core.txt",),
        tests=("tests.test_local_text_provider",),
    ),
    "local-model-imports": CIProfile(
        name="local-model-imports",
        description="Heavy local model dependency import check for torch/transformers/peft stack.",
        requirements=("requirements/local-model.txt",),
        tests=(),
        import_checks=("torch", "transformers", "peft", "accelerate", "sentencepiece", "safetensors"),
        heavyweight=True,
    ),
}


PROFILE_GROUPS: dict[str, tuple[str, ...]] = {
    "default": ("contracts", "core"),
    "optional": ("provider-adapter", "provider-smoke", "api-server", "postgres-run-store", "postgres-quota", "local-provider-contract"),
    "heavyweight": ("local-model-imports",),
    "all": tuple(PROFILES),
}


def profile_names_for(value: str) -> list[str]:
    key = value.strip()
    if key in PROFILE_GROUPS:
        return list(PROFILE_GROUPS[key])
    if key in PROFILES:
        return [key]
    raise KeyError(f"unknown CI profile or group: {value}")


def profiles_for(value: str) -> list[CIProfile]:
    return [PROFILES[name] for name in profile_names_for(value)]


def unittest_command(profile: CIProfile) -> str | None:
    if not profile.tests:
        return None
    return "python -m unittest " + " ".join(profile.tests)


def import_check_command(profile: CIProfile) -> str | None:
    if not profile.import_checks:
        return None
    modules = ", ".join(repr(item) for item in profile.import_checks)
    return f"python -c \"import importlib; [importlib.import_module(name) for name in [{modules}]]; print('import_check=ok')\""


def install_command(profile: CIProfile) -> str | None:
    requirements = [item for item in profile.requirements if item != "requirements/ci-core.txt"]
    if not requirements:
        return None
    return "python -m pip install " + " ".join(f"-r {item}" for item in requirements)


def command_plan(profile: CIProfile) -> list[str]:
    commands = []
    install = install_command(profile)
    tests = unittest_command(profile)
    imports = import_check_command(profile)
    if install:
        commands.append(install)
    if tests:
        commands.append(tests)
    if imports:
        commands.append(imports)
    return commands


def profile_report(value: str) -> dict[str, Any]:
    items = []
    for profile in profiles_for(value):
        data = asdict(profile)
        data["commands"] = command_plan(profile)
        items.append(data)
    return {"selection": value, "profiles": items}


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect CI dependency/test profiles for the foundation project.")
    parser.add_argument("--profile", default="default", help="Profile or group: default, optional, heavyweight, all, or a concrete profile name.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--commands", action="store_true", help="Print runnable shell commands only.")
    args = parser.parse_args()

    report = profile_report(args.profile)
    if args.commands:
        for profile in report["profiles"]:
            for command in profile["commands"]:
                print(command)
        return 0
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for profile in report["profiles"]:
            print(f"profile={profile['name']}")
            print(f"description={profile['description']}")
            print("requirements=" + ",".join(profile["requirements"]))
            print("tests=" + ",".join(profile["tests"]))
            print("imports=" + ",".join(profile["import_checks"]))
            for command in profile["commands"]:
                print(f"command={command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
