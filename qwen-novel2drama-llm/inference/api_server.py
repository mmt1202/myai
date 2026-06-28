"""FastAPI service for local generation and foundation APIs."""
from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, AsyncIterator, Iterator

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INFERENCE_DIR = Path(__file__).resolve().parent
for path in [PROJECT_ROOT, INFERENCE_DIR]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from model_version_registry import resolve_model_paths
from pydantic import BaseModel, Field

from agent.events import read_agent_events, summarize_agent_events
from agent.lifecycle import cancel_run, index_run_in_store, resume_run, retry_run, status_run
from agent.run_store import RunStore, build_run_store, default_sqlite_path
from agent.runtime import run_agent_once
from inference.model_router import route_model
from mcp.adapter import FoundationMCPAdapter
from providers.base import ProviderError, provider_stream_event, response_envelope
from providers.factory import generate_with_registry, stream_generate_with_registry
from services.auth import AuthError, auth_required_from_env, build_auth_context, key_store_path_from_env, load_key_store
from services.auth_audit import write_auth_event
from services.cost_estimator import estimate_request_cost, instance_by_id
from services.memory_store import search_memory, write_memory
from services.rate_limiter import RateLimitError, check_rate_limit, load_json as load_rate_limit_json, rate_limit_config_path_from_env, rate_limit_enabled_from_env, rate_limit_state_path_from_env
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
AUTH_AUDIT_PATH = PROJECT_ROOT / "outputs" / "auth" / "auth_audit.jsonl"
TERMINAL_AGENT_EVENTS = {"run_completed", "run_failed", "run_cancelled", "run_waiting_approval"}


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    max_new_tokens: int = Field(1024, ge=1, le=8192)
    temperature: float = Field(0.7, ge=0.0, le=2.0)


class GenerateResponse(BaseModel):
    result: str
    model_version: str | None = None


def model_utils_module() -> Any:
    return importlib.import_module("model_utils")


def generate_text_runtime(tokenizer: Any, model: Any, prompt: str, max_new_tokens: int, temperature: float, system_prompt: str) -> str:
    return model_utils_module().generate_text(tokenizer, model, prompt, max_new_tokens, temperature, system_prompt)


def load_model_runtime(model_path: str, adapter_path: str | None = None) -> tuple[Any, Any, Any]:
    return model_utils_module().load_model(model_path, adapter_path)


def load_system_prompt_runtime(system_prompt_file: str | None = None) -> str:
    return model_utils_module().load_system_prompt(system_prompt_file)


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


def safe_run_id(value: str | None) -> str:
    run_id = str(value or "latest").strip()
    if not run_id or "/" in run_id or "\\" in run_id or ".." in run_id:
        raise HTTPException(status_code=400, detail="invalid run_id")
    return run_id


def agent_run_store_kind() -> str:
    return os.environ.get("FOUNDATION_AGENT_RUN_STORE", "file")


def agent_run_store_db_path() -> Path:
    configured = os.environ.get("FOUNDATION_AGENT_RUN_DB")
    return Path(configured) if configured else default_sqlite_path(AGENT_OUTPUT_DIR)


def agent_run_store() -> RunStore:
    return build_run_store(agent_run_store_kind(), AGENT_OUTPUT_DIR, sqlite_path=agent_run_store_db_path())


def agent_run_id_from_body(body: dict[str, Any]) -> str:
    return safe_run_id(request_id(body) or body.get("run_id") or "latest")


def agent_output_dir_for(body: dict[str, Any]) -> Path:
    store = agent_run_store()
    return store.run_dir(agent_run_id_from_body(body))


def agent_events_path(run_id: str | None) -> Path:
    store = agent_run_store()
    return store.artifact_path(safe_run_id(run_id), "events.jsonl")


def events_after(events: list[dict[str, Any]], since_event_id: str | None = None) -> list[dict[str, Any]]:
    if not since_event_id:
        return events
    for index, event in enumerate(events):
        if event.get("event_id") == since_event_id:
            return events[index + 1 :]
    return events


def limited_events(events: list[dict[str, Any]], limit: int = 200) -> list[dict[str, Any]]:
    if limit <= 0:
        return events
    return events[-limit:]


def sse_event(event: dict[str, Any]) -> str:
    event_id = str(event.get("event_id") or event.get("chunk_id") or "")
    event_type = str(event.get("event_type") or "agent_event")
    data = json.dumps(event, ensure_ascii=False, sort_keys=True)
    return f"id: {event_id}\nevent: {event_type}\ndata: {data}\n\n"


def provider_sse_event(chunk: dict[str, Any]) -> str:
    return sse_event(chunk)


def stream_provider_sse(chunks: Iterator[dict[str, Any]]) -> Iterator[str]:
    try:
        for chunk in chunks:
            yield provider_sse_event(chunk)
    except ProviderError as exc:
        yield provider_sse_event(
            provider_stream_event(
                "provider_stream_failed",
                error=exc.to_error(),
                done=True,
            )
        )
    except Exception as exc:  # noqa: BLE001
        yield provider_sse_event(
            provider_stream_event(
                "provider_stream_failed",
                error={"code": "provider_error", "message": str(exc), "retryable": False, "details": {}},
                done=True,
            )
        )


async def stream_agent_events(run_id: str, *, since_event_id: str | None = None, poll_interval: float = 1.0, max_seconds: int = 60, limit: int = 200) -> AsyncIterator[str]:
    events_path = agent_events_path(run_id)
    last_event_id = since_event_id
    deadline = time.time() + max(1, max_seconds)
    while True:
        events = limited_events(events_after(read_agent_events(events_path), last_event_id), limit)
        for event in events:
            last_event_id = str(event.get("event_id") or last_event_id or "")
            yield sse_event(event)
            if event.get("event_type") in TERMINAL_AGENT_EVENTS:
                return
        if time.time() >= deadline:
            yield ": stream_timeout\n\n"
            return
        yield ": heartbeat\n\n"
        await asyncio.sleep(max(0.1, poll_interval))


def client_host(request: Request) -> str | None:
    return request.client.host if request.client else None


def emit_auth_audit(request: Request, *, decision: str, status_code: int, reason: str | None = None, auth_context: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None) -> None:
    context = auth_context or getattr(request.state, "auth_context", {}) or {}
    try:
        write_auth_event(
            AUTH_AUDIT_PATH,
            {
                "event_type": "api_request",
                "decision": decision,
                "key_id": context.get("key_id"),
                "owner_id": context.get("owner_id"),
                "workspace_id": context.get("workspace_id"),
                "required_scope": context.get("required_scope"),
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "reason": reason,
                "client_host": client_host(request),
                "metadata": metadata or {},
            },
        )
    except Exception:  # noqa: BLE001
        return


@app.middleware("http")
async def foundation_auth_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    path = request.url.path
    if not path.startswith("/v1/") and path != "/health":
        return await call_next(request)
    auth_context: dict[str, Any] | None = None
    rate_limit_result: dict[str, Any] | None = None
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
        emit_auth_audit(request, decision="denied", status_code=exc.status_code, reason=exc.code, metadata=exc.to_dict())
        content = response_envelope(
            status="failed",
            output=None,
            error={"code": exc.code, "message": exc.message, "retryable": False, "details": exc.to_dict()},
        )
        return JSONResponse(status_code=exc.status_code, content=content)

    if rate_limit_enabled_from_env() and path.startswith("/v1/") and not auth_context.get("public"):
        config = load_rate_limit_json(rate_limit_config_path_from_env(PROJECT_ROOT), {"default": {"enabled": True, "limit": 120, "window_seconds": 60}})
        try:
            rate_limit_result = check_rate_limit(
                rate_limit_state_path_from_env(PROJECT_ROOT),
                config,
                key_id=str(auth_context.get("key_id") or "anonymous"),
                required_scope=auth_context.get("required_scope"),
                workspace_id=auth_context.get("workspace_id"),
            )
            request.state.rate_limit = rate_limit_result
        except RateLimitError as exc:
            emit_auth_audit(request, decision="rate_limited", status_code=429, reason="rate_limit_exceeded", auth_context=auth_context, metadata=exc.to_dict())
            content = response_envelope(
                status="failed",
                output=None,
                error={"code": "rate_limit_exceeded", "message": exc.message, "retryable": True, "details": exc.to_dict()},
            )
            headers = {
                "Retry-After": str(exc.retry_after_seconds),
                "X-RateLimit-Limit": str(exc.limit),
                "X-RateLimit-Remaining": str(exc.remaining),
                "X-RateLimit-Reset": str(exc.reset_at),
            }
            return JSONResponse(status_code=429, content=content, headers=headers)

    response = await call_next(request)
    key_id = str((auth_context or {}).get("key_id") or "")
    if key_id:
        response.headers["X-Foundation-Auth-Key-Id"] = key_id
    if rate_limit_result:
        response.headers["X-RateLimit-Limit"] = str(rate_limit_result.get("limit"))
        response.headers["X-RateLimit-Remaining"] = str(rate_limit_result.get("remaining"))
        response.headers["X-RateLimit-Reset"] = str(rate_limit_result.get("reset_at"))
    emit_auth_audit(request, decision="allowed", status_code=response.status_code, auth_context=auth_context, metadata={"rate_limit": rate_limit_result or {}})
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
        "capabilities": ["router", "token", "cost", "memory", "rules", "skills", "mcp", "agent", "agent_events", "agent_lifecycle", "agent_run_store", "provider", "provider_stream", "auth", "rate_limit", "audit"],
    }


@app.post("/generate", response_model=GenerateResponse)
def generate_api(request: GenerateRequest) -> GenerateResponse:
    if TOKENIZER is None or MODEL is None:
        raise HTTPException(status_code=503, detail="model is not loaded")
    try:
        result = generate_text_runtime(TOKENIZER, MODEL, request.prompt, request.max_new_tokens, request.temperature, SYSTEM_PROMPT)
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
    store = agent_run_store()
    run_id_value = agent_run_id_from_body(body)
    request_body = {**body, "run_id": body.get("run_id") or run_id_value}
    run = run_agent_once(PROJECT_ROOT, request_body, store.run_dir(run_id_value))
    index_run_in_store(store, run_id_value, request_body, run)
    return ok(request_body, {"run": run}, usage=run.get("usage"), cost=run.get("cost"), route=run.get("route_decision"))


@app.get("/v1/agent/events")
def agent_events_api(run_id: str = "latest", stream: bool = False, since_event_id: str | None = None, limit: int = 200, poll_interval: float = 1.0, max_seconds: int = 60) -> dict[str, Any] | StreamingResponse:
    safe_id = safe_run_id(run_id)
    if stream:
        return StreamingResponse(
            stream_agent_events(safe_id, since_event_id=since_event_id, poll_interval=poll_interval, max_seconds=max_seconds, limit=limit),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    events_path = agent_events_path(safe_id)
    events = limited_events(events_after(read_agent_events(events_path), since_event_id), limit)
    return ok(
        {"request_id": safe_id},
        {"run_id": safe_id, "events": events, "summary": summarize_agent_events(events), "events_path": str(events_path)},
    )


@app.get("/v1/agent/status")
def agent_status_api(run_id: str = "latest") -> dict[str, Any]:
    safe_id = safe_run_id(run_id)
    body = {"request_id": safe_id, "run_id": safe_id}
    try:
        result = status_run(AGENT_OUTPUT_DIR, safe_id, store=agent_run_store())
        return ok(body, result)
    except FileNotFoundError as exc:
        return failed(body, "agent_run_not_found", str(exc))
    except ValueError as exc:
        return failed(body, "invalid_agent_run", str(exc))


@app.post("/v1/agent/cancel")
def agent_cancel_api(body: dict[str, Any]) -> dict[str, Any]:
    run_id_value = safe_run_id(body.get("run_id") or request_id(body) or "latest")
    request_body = {**body, "request_id": request_id(body) or run_id_value, "run_id": run_id_value}
    try:
        result = cancel_run(
            AGENT_OUTPUT_DIR,
            run_id_value,
            reason=body.get("reason"),
            requested_by=body.get("requested_by") or body.get("owner_id"),
            store=agent_run_store(),
        )
        return ok(request_body, result)
    except ValueError as exc:
        return failed(request_body, "invalid_agent_run", str(exc))


@app.post("/v1/agent/retry")
def agent_retry_api(body: dict[str, Any]) -> dict[str, Any]:
    run_id_value = safe_run_id(body.get("run_id") or "latest")
    request_body = {**body, "request_id": request_id(body) or run_id_value, "run_id": run_id_value}
    try:
        result = retry_run(
            project_root=PROJECT_ROOT,
            output_root=AGENT_OUTPUT_DIR,
            run_id=run_id_value,
            new_run_id=body.get("new_run_id"),
            overrides=body.get("overrides") or {},
            store=agent_run_store(),
        )
        child = result.get("run") or {}
        return ok(request_body, result, usage=child.get("usage"), cost=child.get("cost"), route=child.get("route_decision"))
    except FileNotFoundError as exc:
        return failed(request_body, "agent_run_not_found", str(exc))
    except ValueError as exc:
        return failed(request_body, "invalid_agent_run", str(exc))


@app.post("/v1/agent/resume")
def agent_resume_api(body: dict[str, Any]) -> dict[str, Any]:
    run_id_value = safe_run_id(body.get("run_id") or "latest")
    request_body = {**body, "request_id": request_id(body) or run_id_value, "run_id": run_id_value}
    try:
        result = resume_run(
            project_root=PROJECT_ROOT,
            output_root=AGENT_OUTPUT_DIR,
            run_id=run_id_value,
            new_run_id=body.get("new_run_id"),
            overrides=body.get("overrides") or {},
            allow_completed=bool(body.get("allow_completed")),
            store=agent_run_store(),
        )
        child = result.get("run") or {}
        return ok(request_body, result, usage=child.get("usage"), cost=child.get("cost"), route=child.get("route_decision"))
    except FileNotFoundError as exc:
        return failed(request_body, "agent_run_not_found", str(exc))
    except ValueError as exc:
        return failed(request_body, "invalid_agent_run", str(exc))


@app.post("/v1/chat")
def chat_api(body: dict[str, Any]) -> dict[str, Any] | StreamingResponse:
    registry = model_instances()
    route = route_model({**body, "required_capabilities": body.get("required_capabilities") or ["text.chat"]}, registry)
    if route.get("status") != "routed":
        return failed(body, "router_no_candidate", "no model candidate matched request", route=route)
    if not body.get("execute_provider"):
        selected = route.get("selected") or {}
        return ok(body, {"route": route, "provider_execution": "skipped"}, usage=route.get("estimated_usage"), cost=selected.get("estimated_cost"), route=route, warnings=["provider_execution_skipped"])
    provider_request = {**body, "model_id": route.get("selected_model_id")}
    if body.get("stream"):
        chunks = stream_generate_with_registry(provider_request, registry, model_id=route.get("selected_model_id"), base_url=body.get("base_url"), api_key_env=body.get("api_key_env") or "MODEL_API_KEY")
        return StreamingResponse(
            stream_provider_sse(chunks),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    try:
        result = generate_with_registry(provider_request, registry, model_id=route.get("selected_model_id"), base_url=body.get("base_url"), api_key_env=body.get("api_key_env") or "MODEL_API_KEY")
    except ProviderError as exc:
        return failed(body, exc.code, exc.message)
    result["route"] = route
    return result


@app.post("/v1/reason")
def reason_api(body: dict[str, Any]) -> dict[str, Any] | StreamingResponse:
    return chat_api({**body, "required_capabilities": body.get("required_capabilities") or ["text.reason"], "expected_reasoning_tokens": body.get("expected_reasoning_tokens") or 512})


@app.post("/v1/multimodal/analyze")
def multimodal_analyze_api(body: dict[str, Any]) -> dict[str, Any] | StreamingResponse:
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
            SYSTEM_PROMPT = load_system_prompt_runtime(args.system_prompt_file)
            TOKENIZER, MODEL, _ = load_model_runtime(model_path, adapter_path)
            ACTIVE_MODEL_VERSION = version
            ACTIVE_MODEL_PATH = model_path
        except Exception as exc:  # noqa: BLE001
            print(f"service startup failed: {exc}")
            return 1
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
