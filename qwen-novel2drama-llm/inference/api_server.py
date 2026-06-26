"""FastAPI service for local generation and foundation APIs."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INFERENCE_DIR = Path(__file__).resolve().parent
for path in [PROJECT_ROOT, INFERENCE_DIR]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from model_utils import generate_text, load_model, load_system_prompt
from model_version_registry import resolve_model_paths
from pydantic import BaseModel, Field

from agent.runtime import run_agent_once
from inference.model_router import route_model
from mcp.adapter import FoundationMCPAdapter
from providers.base import ProviderError, response_envelope
from providers.factory import generate_with_registry
from services.auth import AuthError, auth_required_from_env, build_auth_context, key_store_path_from_env, load_key_store
from services.cost_estimator import estimate_request_cost, instance_by_id
from services.memory_store import search_memory, write_memory
from services.rule_engine import evaluate_rules, load_rules
from services.token_counter import estimate_request_usage
from skills.registry import SkillError, call_skill, list_skills, load_json

app = FastAPI(title="MyAI Foundation API", version="0.1.0")
TOKENIZER: Any | None = None
MODEL: Any | None = None
SYSTEM_PROMPT = "你是专业 AI 短剧编剧、短视频分镜导演、AI 视频生成提示词专家。"
ACTIVE_MODEL_VERSION: str | None = None
ACTIVE_MODEL_PATH: str | None = None
MEMORY_STORE_PATH = PROJECT_ROOT / "outputs" / "memory" / "memory.jsonl"
AGENT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "agent_runtime" / "api"


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    max_new_tokens: int = Field(1024, ge=1, le=8192)
    temperature: float = Field(0.7, ge=0.0, le=2.0)


class GenerateResponse(BaseModel):
    result: str
    model_version: str | None = None


def request_id(body: dict[str, Any]) -> str | None:
    value = body.get("request_id")
    return str(value) if value else None


def trace_id(body: dict[str, Any]) -> str | None:
    value = body.get("trace_id")
    return str(value) if value else request_id(body)


def model_instances() -> dict[str, Any]:
    return load_json(PROJECT_ROOT / "configs" / "model_instance_registry.json")


def skills_registry() -> dict[str, Any]:
    return load_json(PROJECT_ROOT / "configs" / "skills" / "foundation_skills.json")


def default_rules() -> dict[str, Any]:
    return load_rules(PROJECT_ROOT / "configs" / "rules" / "default_rules.yaml")


def ok(body: dict[str, Any], output: Any, **kwargs: Any) -> dict[str, Any]:
    return response_envelope(status="ok", request_id_value=request_id(body), trace_id=trace_id(body), output=output, **kwargs)


def failed(body: dict[str, Any], code: str, message: str, **kwargs: Any) -> dict[str, Any]:
    return response_envelope(
        status="failed",
        request_id_value=request_id(body),
        trace_id=trace_id(body),
        output=kwargs.get("output"),
        route=kwargs.get("route"),
        error={"code": code, "message": message, "retryable": False, "details": kwargs},
    )


@app.middleware("http")
async def foundation_auth_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    path = request.url.path
    if not path.startswith("/v1/") and path != "/health":
        return await call_next(request)
    try:
        store = load_key_store(key_store_path_from_env(PROJECT_ROOT))
        auth_context = build_auth_context(
            method=request.method,
            path=path,
            api_key=request.headers.get("X-API-Key"),
            workspace_id=request.headers.get("X-Workspace-Id"),
            store=store,
            auth_required=auth_required_from_env(),
        )
        request.state.auth_context = auth_context
    except AuthError as exc:
        content = response_envelope(
            status="failed",
            output=None,
            error={"code": exc.code, "message": exc.message, "retryable": False, "details": exc.to_dict()},
        )
        return JSONResponse(status_code=exc.status_code, content=content)
    response = await call_next(request)
    key_id = str(getattr(request.state, "auth_context", {}).get("key_id") or "")
    if key_id:
        response.headers["X-Foundation-Auth-Key-Id"] = key_id
    return response


@app.get("/health")
def health() -> dict[str, str | None]:
    return {"status": "ok", "model_version": ACTIVE_MODEL_VERSION, "model_path": ACTIVE_MODEL_PATH}


@app.get("/v1/health")
def foundation_health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "myai-foundation",
        "model_version": ACTIVE_MODEL_VERSION,
        "model_path": ACTIVE_MODEL_PATH,
        "capabilities": ["router", "token", "cost", "memory", "rules", "skills", "mcp", "agent", "provider", "auth"],
    }


@app.post("/generate", response_model=GenerateResponse)
def generate_api(request: GenerateRequest) -> GenerateResponse:
    if TOKENIZER is None or MODEL is None:
        raise HTTPException(status_code=503, detail="model is not loaded")
    try:
        result = generate_text(TOKENIZER, MODEL, request.prompt, request.max_new_tokens, request.temperature, SYSTEM_PROMPT)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"generation failed: {exc}") from exc
    return GenerateResponse(result=result, model_version=ACTIVE_MODEL_VERSION)


@app.post("/v1/token/count")
def token_count_api(body: dict[str, Any]) -> dict[str, Any]:
    usage = estimate_request_usage(body, expected_output_tokens=int(body.get("expected_output_tokens") or 512))
    return ok(body, {"usage": usage}, usage=usage)


@app.post("/v1/cost/estimate")
def cost_estimate_api(body: dict[str, Any]) -> dict[str, Any]:
    registry = model_instances()
    model_id = body.get("model_id") or body.get("model")
    if model_id:
        instance = instance_by_id(registry, str(model_id))
        report = estimate_request_cost(body, instance, expected_output_tokens=int(body.get("expected_output_tokens") or 512), currency=registry.get("default_currency", "USD"))
        return ok(body, report, usage=report.get("usage"), cost=report.get("cost"), model=report.get("model"))
    route = route_model(body, registry)
    selected = route.get("selected") or {}
    return ok(body, {"route": route}, usage=route.get("estimated_usage"), cost=selected.get("estimated_cost"), route=route)


@app.post("/v1/route")
def route_api(body: dict[str, Any]) -> dict[str, Any]:
    route = route_model(body, model_instances())
    selected = route.get("selected") or {}
    return ok(body, {"route": route}, usage=route.get("estimated_usage"), cost=selected.get("estimated_cost"), route=route)


@app.post("/v1/rules/evaluate")
def rules_evaluate_api(body: dict[str, Any]) -> dict[str, Any]:
    ruleset = body.get("ruleset") or default_rules()
    context = body.get("context") or body
    decision = evaluate_rules(ruleset, context)
    return ok(body, {"decision": decision})


@app.post("/v1/memory/search")
def memory_search_api(body: dict[str, Any]) -> dict[str, Any]:
    items = search_memory(MEMORY_STORE_PATH, body)
    return ok(body, {"items": items})


@app.post("/v1/memory/write")
def memory_write_api(body: dict[str, Any]) -> dict[str, Any]:
    item = write_memory(MEMORY_STORE_PATH, body.get("item") or body)
    return ok(body, {"item": item})


@app.get("/v1/skills/list")
def skills_list_api(category: str | None = None, status: str | None = None, capability: str | None = None, include_planned: bool = False) -> dict[str, Any]:
    body: dict[str, Any] = {}
    skills = list_skills(skills_registry(), category=category, status=status, capability=capability, include_planned=include_planned)
    return ok(body, {"skills": skills})


@app.post("/v1/skills/call")
def skills_call_api(body: dict[str, Any]) -> dict[str, Any]:
    try:
        result = call_skill(
            skills_registry(),
            str(body.get("name")),
            body.get("arguments") or {},
            allow_provider=bool(body.get("allow_provider")),
            allow_write=bool(body.get("allow_write")),
            approved=bool(body.get("approved")),
        )
        return ok(body, result)
    except SkillError as exc:
        return failed(body, "tool_denied", str(exc))


@app.get("/v1/mcp/tools")
def mcp_tools_api(include_planned: bool = False) -> dict[str, Any]:
    body: dict[str, Any] = {}
    adapter = FoundationMCPAdapter(PROJECT_ROOT / "configs" / "skills" / "foundation_skills.json", audit_log=None)
    return ok(body, adapter.list_tools(include_planned=include_planned))


@app.post("/v1/mcp/call")
def mcp_call_api(body: dict[str, Any]) -> dict[str, Any]:
    adapter = FoundationMCPAdapter(
        PROJECT_ROOT / "configs" / "skills" / "foundation_skills.json",
        audit_log=PROJECT_ROOT / "outputs" / "mcp" / "api_mcp_adapter.jsonl",
        allow_provider=bool(body.get("allow_provider")),
        allow_write=bool(body.get("allow_write")),
        approved=bool(body.get("approved")),
    )
    result = adapter.call_tool(str(body.get("name")), body.get("arguments") or {})
    return ok(body, result)


@app.post("/v1/agent/run")
def agent_run_api(body: dict[str, Any]) -> dict[str, Any]:
    run = run_agent_once(PROJECT_ROOT, body, AGENT_OUTPUT_DIR / (request_id(body) or "latest"))
    return ok(body, {"run": run}, usage=run.get("usage"), cost=run.get("cost"), route=run.get("route_decision"))


@app.post("/v1/chat")
def chat_api(body: dict[str, Any]) -> dict[str, Any]:
    registry = model_instances()
    route = route_model({**body, "required_capabilities": body.get("required_capabilities") or ["text.chat"]}, registry)
    if route.get("status") != "routed":
        return failed(body, "router_no_candidate", "no model candidate matched request", route=route)
    if not body.get("execute_provider"):
        selected = route.get("selected") or {}
        return ok(body, {"route": route, "provider_execution": "skipped"}, usage=route.get("estimated_usage"), cost=selected.get("estimated_cost"), route=route, warnings=["provider_execution_skipped"])
    provider_request = {**body, "model_id": route.get("selected_model_id")}
    try:
        result = generate_with_registry(provider_request, registry, model_id=route.get("selected_model_id"), base_url=body.get("base_url"), api_key_env=body.get("api_key_env") or "MODEL_API_KEY")
    except ProviderError as exc:
        return failed(body, exc.code, exc.message)
    result["route"] = route
    return result


@app.post("/v1/reason")
def reason_api(body: dict[str, Any]) -> dict[str, Any]:
    return chat_api({**body, "required_capabilities": body.get("required_capabilities") or ["text.reason"], "expected_reasoning_tokens": body.get("expected_reasoning_tokens") or 512})


@app.post("/v1/multimodal/analyze")
def multimodal_analyze_api(body: dict[str, Any]) -> dict[str, Any]:
    return chat_api({**body, "required_capabilities": body.get("required_capabilities") or ["vision.understand"]})


def resolve_startup_model(args: argparse.Namespace) -> tuple[str, str | None, str | None]:
    if args.model_path:
        return args.model_path, args.adapter_path, None
    model_path, adapter_path, item = resolve_model_paths(args.model_versions, args.model_version)
    return model_path, args.adapter_path if args.adapter_path is not None else adapter_path, item.get("version")


def main() -> int:
    parser = argparse.ArgumentParser(description="Start MyAI foundation FastAPI service.")
    parser.add_argument("--model-path", default=None, help="Base or merged model path. If omitted, use model version registry.")
    parser.add_argument("--adapter-path", default=None, help="Optional LoRA adapter path.")
    parser.add_argument("--model-versions", default="configs/model_versions.json", help="Model version registry path.")
    parser.add_argument("--model-version", default=None, help="Model version to load. If omitted, use active_version.")
    parser.add_argument("--system-prompt-file", default="prompts/system_prompt.txt", help="System prompt file path.")
    parser.add_argument("--host", default="127.0.0.1", help="Host.")
    parser.add_argument("--port", type=int, default=8000, help="Port.")
    parser.add_argument("--skip-model-load", action="store_true", help="Start foundation APIs without loading the local text model.")
    args = parser.parse_args()

    global TOKENIZER, MODEL, SYSTEM_PROMPT, ACTIVE_MODEL_VERSION, ACTIVE_MODEL_PATH
    if not args.skip_model_load:
        try:
            model_path, adapter_path, version = resolve_startup_model(args)
            SYSTEM_PROMPT = load_system_prompt(args.system_prompt_file)
            TOKENIZER, MODEL, _ = load_model(model_path, adapter_path)
            ACTIVE_MODEL_VERSION = version
            ACTIVE_MODEL_PATH = model_path
        except Exception as exc:  # noqa: BLE001
            print(f"service startup failed: {exc}")
            return 1
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
