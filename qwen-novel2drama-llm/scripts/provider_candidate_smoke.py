from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from providers.base import ProviderError
from providers.factory import build_provider, find_model_instance
from skills.registry import load_json

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def smoke_request() -> dict[str, Any]:
    return {"request_id": "provider_candidate_smoke", "input": [{"type": "text", "text": "Return ok."}], "max_output_tokens": 16}


def provider_env(provider: Any) -> dict[str, Any]:
    if hasattr(provider, "provider_env"):
        return provider.provider_env()
    api_key_env = getattr(provider, "api_key_env", None)
    model_name_env = getattr(provider, "model_name_env", None)
    base_url_env = getattr(provider, "base_url_env", None)
    return {
        "api_key_env": api_key_env,
        "api_key_configured": bool(os.environ.get(api_key_env or "")),
        "model_name_env": model_name_env,
        "model_name_configured": bool(os.environ.get(model_name_env or "")),
        "base_url_env": base_url_env,
        "base_url_configured": bool(os.environ.get(base_url_env or "")),
    }


def run_smoke(*, project_root: Path = PROJECT_ROOT, model_id: str, live: bool = False, stream: bool = False, base_url: str | None = None, api_key_env: str | None = None) -> dict[str, Any]:
    registry = load_json(project_root / "configs" / "model_instance_registry.json")
    instance = find_model_instance(registry, model_id)
    provider = build_provider(instance, base_url=base_url, api_key_env=api_key_env)
    env = provider_env(provider)
    request = smoke_request()
    if not live:
        result: Any = list(provider.stream_generate({**request, "dry_run": True})) if stream else provider.generate({**request, "dry_run": True})
        return {"status": "passed", "mode": "dry_run_stream" if stream else "dry_run", "model_id": model_id, "provider": provider.provider_name, "env": env, "result": result}
    if env.get("api_key_env") and not env.get("api_key_configured"):
        return {"status": "skipped", "mode": "live_stream" if stream else "live", "model_id": model_id, "provider": provider.provider_name, "reason": "api_key_missing", "env": env}
    try:
        result = list(provider.stream_generate(request)) if stream else provider.generate(request)
    except ProviderError as exc:
        return {"status": "failed", "mode": "live_stream" if stream else "live", "model_id": model_id, "provider": provider.provider_name, "error": exc.to_error(), "env": env}
    final_status = result[-1].get("event_type") if isinstance(result, list) and result else result.get("status")
    return {"status": "passed" if final_status in {"ok", "provider_stream_completed"} else "failed", "mode": "live_stream" if stream else "live", "model_id": model_id, "provider": provider.provider_name, "env": env, "result": result}


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test any configured provider candidate.")
    parser.add_argument("--project-root", default=str(PROJECT_ROOT))
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--api-key-env", default=None)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--stream", action="store_true")
    args = parser.parse_args()
    report = run_smoke(project_root=Path(args.project_root), model_id=args.model_id, live=args.live, stream=args.stream, base_url=args.base_url, api_key_env=args.api_key_env)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.get("status") in {"passed", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
