from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from providers.base import ProviderError
from providers.openai_compatible import OpenAICompatibleProvider

SMOKE_ENABLED_ENV = "FOUNDATION_PROVIDER_SMOKE_ENABLED"
SMOKE_BASE_URL_ENV = "FOUNDATION_PROVIDER_SMOKE_BASE_URL"
SMOKE_MODEL_ENV = "FOUNDATION_PROVIDER_SMOKE_MODEL"
SMOKE_CREDENTIAL_ENV = "FOUNDATION_PROVIDER_SMOKE_CREDENTIAL_ENV"
SMOKE_TIMEOUT_ENV = "FOUNDATION_PROVIDER_SMOKE_TIMEOUT"


@dataclass(frozen=True)
class ProviderSmokeConfig:
    enabled: bool
    base_url: str
    model: str
    credential_env: str
    timeout: int = 60

    def credential_configured(self) -> bool:
        return bool(os.environ.get(self.credential_env))

    def public_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["credential_configured"] = self.credential_configured()
        return data


def bool_env(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name) or default)
    except ValueError:
        return default


def load_config(args: argparse.Namespace) -> ProviderSmokeConfig:
    return ProviderSmokeConfig(
        enabled=bool(args.enabled) or bool_env(SMOKE_ENABLED_ENV, False),
        base_url=(args.base_url or os.environ.get(SMOKE_BASE_URL_ENV) or "").rstrip("/"),
        model=args.model or os.environ.get(SMOKE_MODEL_ENV) or "",
        credential_env=args.credential_env or os.environ.get(SMOKE_CREDENTIAL_ENV) or "MODEL_API_KEY",
        timeout=int(args.timeout or int_env(SMOKE_TIMEOUT_ENV, 60)),
    )


def skip_reasons(config: ProviderSmokeConfig) -> list[str]:
    reasons: list[str] = []
    if not config.enabled:
        reasons.append("smoke_not_enabled")
    if not config.base_url:
        reasons.append("missing_base_url")
    if not config.model:
        reasons.append("missing_model")
    if not config.credential_configured():
        reasons.append("missing_credential")
    return reasons


def request_payload(config: ProviderSmokeConfig) -> dict[str, Any]:
    return {
        "request_id": "provider_smoke_test",
        "model": config.model,
        "input": [{"type": "text", "text": "Return exactly: provider_smoke_ok"}],
        "temperature": 0,
        "max_output_tokens": 32,
    }


def run_smoke(config: ProviderSmokeConfig, *, dry_run: bool = False) -> dict[str, Any]:
    reasons = skip_reasons(config)
    if dry_run:
        return {"status": "dry_run", "config": config.public_dict(), "skip_reasons": reasons, "request": request_payload(config)}
    if reasons:
        return {"status": "skipped", "config": config.public_dict(), "skip_reasons": reasons}
    provider = OpenAICompatibleProvider({"id": config.model, "provider": "openai_compatible", "runtime": "http_chat_completions", "model_name": config.model}, base_url=config.base_url, api_key_env=config.credential_env, timeout=config.timeout)
    try:
        response = provider.generate(request_payload(config))
    except ProviderError as exc:
        return {"status": "failed", "config": config.public_dict(), "error": exc.to_error(request_id_value="provider_smoke_test")}
    return {"status": "ok" if response.get("status") == "ok" else "failed", "config": config.public_dict(), "provider_response": response}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--enabled", action="store_true")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--credential-env", default=None)
    parser.add_argument("--timeout", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fail-on-skip", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run_smoke(load_config(args), dry_run=bool(args.dry_run))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"status={result['status']}")
        for reason in result.get("skip_reasons") or []:
            print(f"skip_reason={reason}")
    if result["status"] in {"ok", "dry_run"}:
        return 0
    if result["status"] == "skipped" and not args.fail_on_skip:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
