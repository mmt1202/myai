from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from providers.base import ProviderError
from providers.factory import find_model_instance
from providers.openai_responses import OpenAIResponsesProvider
from skills.registry import load_json

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def smoke_request() -> dict[str, Any]:
    return {"request_id": "openai_responses_smoke", "input": [{"type": "text", "text": "Return the word ok."}], "max_output_tokens": 16}


def run_smoke(*, project_root: Path = PROJECT_ROOT, model_id: str = "external.openai.primary", live: bool = False, stream: bool = False, base_url: str | None = None) -> dict[str, Any]:
    registry = load_json(project_root / "configs" / "model_instance_registry.json")
    instance = find_model_instance(registry, model_id)
    provider = OpenAIResponsesProvider(instance, base_url=base_url)
    env = {"api_key_env": provider.api_key_env, "api_key_configured": bool(os.environ.get(provider.api_key_env)), "model_name_env": provider.model_name_env, "model_name_configured": bool(os.environ.get(provider.model_name_env))}
    request = smoke_request()
    if not live:
        result: Any = list(provider.stream_generate({**request, "dry_run": True})) if stream else provider.generate({**request, "dry_run": True})
        return {"status": "passed", "mode": "dry_run_stream" if stream else "dry_run", "env": env, "result": result}
    if not env["api_key_configured"]:
        return {"status": "skipped", "mode": "live_stream" if stream else "live", "reason": "api_key_missing", "env": env}
    try:
        result = list(provider.stream_generate(request)) if stream else provider.generate(request)
    except ProviderError as exc:
        return {"status": "failed", "mode": "live_stream" if stream else "live", "error": exc.to_error(), "env": env}
    final_status = result[-1].get("event_type") if isinstance(result, list) and result else result.get("status")
    return {"status": "passed" if final_status in {"ok", "provider_stream_completed"} else "failed", "mode": "live_stream" if stream else "live", "env": env, "result": result}


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test the OpenAI Responses provider adapter.")
    parser.add_argument("--project-root", default=str(PROJECT_ROOT))
    parser.add_argument("--model-id", default="external.openai.primary")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--stream", action="store_true")
    args = parser.parse_args()
    report = run_smoke(project_root=Path(args.project_root), model_id=args.model_id, live=args.live, stream=args.stream, base_url=args.base_url)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.get("status") in {"passed", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
