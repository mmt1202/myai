from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from providers.factory import generate_with_registry, stream_generate_with_registry
from skills.registry import SkillError, call_skill


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def save_jsonl(path: Path, items: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in items), encoding="utf-8")


def parse_arguments(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        if not value.strip():
            return {}
        parsed = json.loads(value)
        if not isinstance(parsed, dict):
            raise SkillError("tool call arguments must decode to an object")
        return parsed
    raise SkillError("tool call arguments must be an object or JSON object string")


def provider_output(provider_response: dict[str, Any]) -> dict[str, Any]:
    output = provider_response.get("output") or {}
    return output if isinstance(output, dict) else {}


def extract_tool_calls(provider_response: dict[str, Any]) -> list[dict[str, Any]]:
    output = provider_output(provider_response)
    candidates = output.get("tool_calls")
    raw_message = output.get("raw_message") or {}
    if candidates is None and isinstance(raw_message, dict):
        candidates = raw_message.get("tool_calls")
    if candidates is None:
        return []
    if not isinstance(candidates, list):
        raise SkillError("provider tool_calls must be a list")
    return [normalize_tool_call(item) for item in candidates]


def normalize_tool_call(item: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise SkillError("tool call must be an object")
    function = item.get("function") or {}
    name = item.get("name") or function.get("name") or item.get("skill_id")
    if not name:
        raise SkillError("tool call requires name or function.name")
    arguments = item.get("arguments")
    if arguments is None:
        arguments = item.get("arguments_json")
    if arguments is None:
        arguments = function.get("arguments")
    return {
        "id": str(item.get("id") or item.get("tool_call_id") or name),
        "name": str(name),
        "arguments": parse_arguments(arguments),
        "raw": item,
    }


def tool_result_block(tool_call: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "tool_result",
        "text": json.dumps(result, ensure_ascii=False),
        "metadata": {
            "tool_call_id": tool_call.get("id"),
            "tool_name": tool_call.get("name"),
            "status": result.get("status"),
        },
    }


def execute_tool_call(registry: dict[str, Any], tool_call: dict[str, Any], *, allow_provider: bool = False, allow_write: bool = False, approved: bool = False) -> dict[str, Any]:
    try:
        result = call_skill(
            registry,
            tool_call["name"],
            tool_call.get("arguments") or {},
            allow_provider=allow_provider,
            allow_write=allow_write,
            approved=approved,
        )
        return {"tool_call_id": tool_call.get("id"), "name": tool_call["name"], "status": "ok", "result": result}
    except Exception as exc:  # noqa: BLE001
        return {"tool_call_id": tool_call.get("id"), "name": tool_call["name"], "status": "failed", "error": str(exc)}


def build_next_provider_request(base_request: dict[str, Any], selected_model_id: str, tool_results: list[dict[str, Any]]) -> dict[str, Any]:
    next_request = {**base_request}
    next_request["model_id"] = selected_model_id
    next_request["model"] = selected_model_id
    next_request["input"] = list(base_request.get("input") or []) + [tool_result_block(item["tool_call"], item["result"]) for item in tool_results]
    return next_request


def provider_response_from_stream_chunks(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    failed = next((item for item in chunks if item.get("event_type") == "provider_stream_failed"), None)
    if failed:
        return {
            "request_id": failed.get("request_id"),
            "trace_id": failed.get("trace_id"),
            "status": "failed",
            "model": failed.get("model") or {},
            "usage": failed.get("usage") or {},
            "output": failed.get("output") or {},
            "error": failed.get("error") or {"code": "provider_stream_failed", "message": "provider stream failed", "retryable": False, "details": {}},
            "stream": {"chunk_count": len(chunks), "completed": False},
        }
    completed = next((item for item in reversed(chunks) if item.get("event_type") == "provider_stream_completed"), None)
    if not completed:
        return {
            "status": "failed",
            "usage": {},
            "output": {},
            "error": {"code": "provider_stream_incomplete", "message": "provider stream did not emit a completed event", "retryable": True, "details": {"chunk_count": len(chunks)}},
            "stream": {"chunk_count": len(chunks), "completed": False},
        }
    return {
        "request_id": completed.get("request_id"),
        "trace_id": completed.get("trace_id"),
        "status": "ok",
        "model": completed.get("model") or {},
        "usage": completed.get("usage") or {},
        "output": completed.get("output") or {},
        "warnings": [],
        "error": None,
        "stream": {"chunk_count": len(chunks), "completed": True, "tool_call_count": (completed.get("metadata") or {}).get("tool_call_count", 0)},
    }


def generate_provider_round(
    request: dict[str, Any],
    instances: dict[str, Any],
    *,
    selected_model_id: str,
    base_url: str | None = None,
    api_key_env: str = "MODEL_API_KEY",
    stream: bool = False,
    stream_chunks_path: Path | None = None,
) -> dict[str, Any]:
    if not stream:
        return generate_with_registry(
            request,
            instances,
            model_id=selected_model_id,
            base_url=base_url,
            api_key_env=api_key_env,
        )
    stream_request = {**request, "stream": True}
    chunks = list(
        stream_generate_with_registry(
            stream_request,
            instances,
            model_id=selected_model_id,
            base_url=base_url,
            api_key_env=api_key_env,
        )
    )
    if stream_chunks_path:
        save_jsonl(stream_chunks_path, chunks)
    response = provider_response_from_stream_chunks(chunks)
    response["stream_chunks_path"] = str(stream_chunks_path) if stream_chunks_path else None
    return response


def run_model_tool_loop(
    *,
    project_root: Path,
    output_dir: Path,
    request: dict[str, Any],
    foundation_request: dict[str, Any],
    instances: dict[str, Any],
    selected_model_id: str,
    initial_provider_response: dict[str, Any],
    max_rounds: int = 3,
) -> dict[str, Any]:
    registry = load_json(project_root / "configs" / "skills" / "foundation_skills.json")
    allow_provider = bool(request.get("allow_model_tool_provider"))
    allow_write = bool(request.get("allow_model_tool_write"))
    approved = bool(request.get("approve_model_tools"))
    fail_on_tool_error = bool(request.get("fail_on_model_tool_error", True))
    use_stream = bool(request.get("stream_provider_tool_calls"))
    current_response = initial_provider_response
    current_request = {**foundation_request, "model_id": selected_model_id, "model": selected_model_id}
    rounds: list[dict[str, Any]] = []
    for round_index in range(max_rounds):
        tool_calls = extract_tool_calls(current_response)
        if not tool_calls:
            break
        round_results: list[dict[str, Any]] = []
        for tool_call in tool_calls:
            result = execute_tool_call(
                registry,
                tool_call,
                allow_provider=allow_provider,
                allow_write=allow_write,
                approved=approved,
            )
            round_results.append({"tool_call": tool_call, "result": result})
            if result.get("status") != "ok" and fail_on_tool_error:
                summary = {"rounds": rounds + [{"round": round_index + 1, "tool_results": round_results}], "status": "failed", "error": result.get("error"), "stream_provider_tool_calls": use_stream}
                save_json(output_dir / "model_tool_loop.json", summary)
                return summary
        next_request = build_next_provider_request(current_request, selected_model_id, round_results)
        next_request["dry_run"] = bool(request.get("dry_run_provider"))
        next_request["stream_include_usage"] = request.get("stream_include_usage")
        next_request["stream_options"] = request.get("stream_options")
        next_response = generate_provider_round(
            next_request,
            instances,
            selected_model_id=selected_model_id,
            base_url=request.get("base_url"),
            api_key_env=request.get("api_key_env") or "MODEL_API_KEY",
            stream=use_stream,
            stream_chunks_path=output_dir / f"model_tool_loop_stream_round_{round_index + 1}.jsonl" if use_stream else None,
        )
        rounds.append(
            {
                "round": round_index + 1,
                "tool_calls": tool_calls,
                "tool_results": round_results,
                "provider_response": next_response,
            }
        )
        current_request = next_request
        current_response = next_response
    summary = {"status": "ok", "round_count": len(rounds), "rounds": rounds, "final_provider_response": current_response, "stream_provider_tool_calls": use_stream}
    save_json(output_dir / "model_tool_loop.json", summary)
    return summary
