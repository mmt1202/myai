from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent.events import AgentEventWriter, read_agent_events, summarize_agent_events
from agent.tool_loop import generate_provider_round, run_model_tool_loop
from inference.model_router import route_model
from providers.base import ProviderError
from services.rule_engine import evaluate_rules, load_rules
from services.usage_ledger import write_event
from services.usage_reconciliation import reconcile_provider_usage, reconciled_cost, reconciled_usage
from services.workspace_quota import (
    check_workspace_quota_from_paths,
    quota_config_path_from_env,
    quota_enabled_from_env,
    quota_state_path_from_env,
    record_workspace_usage_to_path,
)
from skills.registry import SkillError, call_skill

RUN_STATES = {"queued", "running", "waiting_tool", "waiting_approval", "completed", "failed", "cancelled"}
TERMINAL_STATES = {"completed", "failed", "cancelled"}
APPROVAL_POLICIES = {"never", "on_write", "on_cost", "always"}
CANCEL_REQUEST_FILENAME = "cancel_requested.json"
VALID_TRANSITIONS = {
    "queued": {"running", "cancelled"},
    "running": {"waiting_tool", "waiting_approval", "completed", "failed", "cancelled"},
    "waiting_tool": {"running", "failed", "cancelled"},
    "waiting_approval": {"running", "failed", "cancelled"},
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def maybe_store_save_request(store: Any | None, run_id: str, request: dict[str, Any]) -> None:
    if store is not None and hasattr(store, "save_request"):
        store.save_request(run_id, request)


def maybe_store_save_report(store: Any | None, run_id: str, run: dict[str, Any]) -> None:
    if store is not None and hasattr(store, "save_report"):
        store.save_report(run_id, run)


def maybe_store_save_created_run(store: Any | None, run_id: str, run: dict[str, Any], path: Path) -> None:
    if store is not None and hasattr(store, "save_artifact"):
        store.save_artifact(run_id, "created_run", run, path=str(path))


def maybe_store_save_artifact(store: Any | None, run_id: str, name: str, artifact_path: str) -> None:
    if store is not None and hasattr(store, "save_artifact"):
        store.save_artifact(run_id, name, {"path": artifact_path}, path=artifact_path)


def index_artifacts_in_store(store: Any | None, run: dict[str, Any]) -> None:
    if store is None:
        return
    run_id = str(run.get("run_id") or "")
    if not run_id:
        return
    for name, artifact_path in (run.get("artifacts") or {}).items():
        maybe_store_save_artifact(store, run_id, str(name), str(artifact_path))


def index_events_in_store(store: Any | None, output_dir: Path, run: dict[str, Any]) -> None:
    if store is None or not hasattr(store, "append_event"):
        return
    try:
        metadata = store.metadata() if hasattr(store, "metadata") else {}
    except Exception:  # noqa: BLE001
        metadata = {}
    if metadata.get("type") == "file":
        return
    run_id = str(run.get("run_id") or "")
    if not run_id:
        return
    for event in read_agent_events(output_dir / "events.jsonl"):
        try:
            store.append_event(run_id, event)
        except Exception:  # noqa: BLE001
            continue


def cancellation_request(output_dir: Path, store: Any | None = None, run_id: str | None = None) -> dict[str, Any] | None:
    if store is not None and run_id and hasattr(store, "load_cancel_request"):
        try:
            marker = store.load_cancel_request(run_id)
            if marker:
                return marker
        except Exception:  # noqa: BLE001
            pass
    path = output_dir / CANCEL_REQUEST_FILENAME
    if not path.exists():
        return None
    try:
        return load_json(path)
    except Exception:  # noqa: BLE001
        return {"reason": "cancel_requested", "source": str(path)}


def apply_cancellation_if_requested(output_dir: Path, run: dict[str, Any], events: AgentEventWriter | None = None, *, checkpoint: str = "checkpoint", store: Any | None = None) -> bool:
    marker = cancellation_request(output_dir, store, run.get("run_id"))
    if not marker or run.get("status") in TERMINAL_STATES:
        return False
    step = add_step(run, "cancel_check", status="cancelled", input_data={"checkpoint": checkpoint}, output_data=marker, error=marker.get("reason"))
    transition(run, "cancelled")
    run["error"] = "cancelled"
    run["cancelled"] = marker
    if events:
        events.emit("run_cancelled", status="cancelled", step=step, message=marker.get("reason") or "cancel_requested", data={"checkpoint": checkpoint, "cancel": marker})
    return True


def create_run(request: dict[str, Any]) -> dict[str, Any]:
    approval_policy = request.get("approval_policy") or "on_cost"
    if approval_policy not in APPROVAL_POLICIES:
        raise ValueError(f"unsupported approval policy: {approval_policy}")
    created_at = now_iso()
    return {
        "run_id": request.get("run_id") or new_id("run"),
        "session_id": request.get("session_id"),
        "owner_id": request.get("owner_id"),
        "project_id": request.get("project_id"),
        "workspace_id": request.get("workspace_id"),
        "retry_of": request.get("retry_of"),
        "resume_of": request.get("resume_of"),
        "parent_run_id": request.get("parent_run_id"),
        "task": request.get("task") or "",
        "input": request.get("input") or [],
        "route_mode": request.get("route_mode") or "balanced",
        "approval_policy": approval_policy,
        "status": "queued",
        "steps": [],
        "route_decision": None,
        "rule_decision": None,
        "skill_results": [],
        "model_tool_loop": None,
        "provider_response": None,
        "usage_reconciliation": None,
        "workspace_quota_check": None,
        "workspace_quota_usage": None,
        "event_summary": {},
        "usage": {},
        "cost": {},
        "artifacts": {},
        "created_at": created_at,
        "updated_at": created_at,
    }


def transition(run: dict[str, Any], next_status: str) -> dict[str, Any]:
    if next_status not in RUN_STATES:
        raise ValueError(f"unsupported run status: {next_status}")
    current = run.get("status")
    if next_status not in VALID_TRANSITIONS.get(current, set()):
        raise ValueError(f"invalid transition: {current} -> {next_status}")
    run["status"] = next_status
    run["updated_at"] = now_iso()
    if next_status in TERMINAL_STATES:
        run["completed_at"] = run["updated_at"]
    return run


def add_step(run: dict[str, Any], step_type: str, *, input_data: dict[str, Any] | None = None, output_data: dict[str, Any] | None = None, status: str = "completed", error: str | None = None) -> dict[str, Any]:
    step = {
        "step_id": new_id("step"),
        "type": step_type,
        "status": status,
        "input": input_data or {},
        "output": output_data or {},
        "error": error,
        "created_at": now_iso(),
    }
    run.setdefault("steps", []).append(step)
    run["updated_at"] = step["created_at"]
    return step


def required_capabilities_for_task(task: str, request: dict[str, Any]) -> list[str]:
    if request.get("required_capabilities"):
        return list(request["required_capabilities"])
    text = task.lower()
    if "code" in text or "代码" in task:
        return ["text.chat", "code.generate"]
    if "image" in text or "图片" in task:
        return ["vision.understand"]
    return ["text.chat"]


def build_foundation_request(request: dict[str, Any]) -> dict[str, Any]:
    task = request.get("task") or ""
    return {
        "request_id": request.get("request_id") or request.get("run_id"),
        "trace_id": request.get("trace_id") or request.get("request_id") or request.get("run_id"),
        "workspace_id": request.get("workspace_id"),
        "task": task,
        "input": request.get("input") or ([{"type": "text", "text": task}] if task else []),
        "route_mode": request.get("route_mode") or "balanced",
        "required_capabilities": required_capabilities_for_task(task, request),
        "privacy": request.get("privacy") or {},
        "budget": request.get("budget") or {},
        "expected_output_tokens": request.get("expected_output_tokens") or 512,
        "expected_reasoning_tokens": request.get("expected_reasoning_tokens") or 0,
    }


def rule_context_from_route(foundation_request: dict[str, Any], route_decision: dict[str, Any], instances: dict[str, Any]) -> dict[str, Any]:
    selected = route_decision.get("selected") or {}
    return {
        "request": foundation_request,
        "candidate": selected,
        "budget": foundation_request.get("budget") or {},
        "privacy": foundation_request.get("privacy") or {},
        "registry": {"default_currency": instances.get("default_currency")},
    }


def approval_required(run: dict[str, Any], rule_decision: dict[str, Any], route_decision: dict[str, Any]) -> bool:
    policy = run.get("approval_policy") or "on_cost"
    if rule_decision.get("decision") == "deny":
        return False
    if policy == "never":
        return False
    if policy == "always":
        return True
    if policy == "on_write":
        return False
    if policy == "on_cost":
        selected = route_decision.get("selected") or {}
        estimated_cost = (selected.get("estimated_cost") or {}).get("estimated") or 0
        limit = ((run.get("budget") or {}).get("approval_cost_threshold") or 1.0)
        return estimated_cost > limit
    return False


def record_usage(output_dir: Path, run: dict[str, Any]) -> dict[str, Any]:
    event = {
        "request_id": run.get("run_id"),
        "trace_id": run.get("session_id"),
        "workspace_id": run.get("workspace_id"),
        "model_id": (run.get("route_decision") or {}).get("selected_model_id"),
        "provider": ((run.get("route_decision") or {}).get("selected") or {}).get("provider"),
        "usage": run.get("usage") or {},
        "cost": run.get("cost") or {},
        "metadata": {"agent_status": run.get("status"), "error": run.get("error")},
    }
    write_event(output_dir / "usage_ledger.jsonl", event)
    return event


def quota_is_enabled(request: dict[str, Any]) -> bool:
    return bool(request.get("workspace_quota_enabled") or quota_enabled_from_env())


def workspace_id_for_run(run: dict[str, Any], request: dict[str, Any]) -> str:
    return str(request.get("workspace_id") or run.get("workspace_id") or "default")


def quota_config_path(project_root: Path, request: dict[str, Any]) -> Path:
    return Path(request.get("workspace_quota_config_path") or quota_config_path_from_env(project_root))


def quota_state_path(project_root: Path, request: dict[str, Any]) -> Path:
    return Path(request.get("workspace_quota_state_path") or quota_state_path_from_env(project_root))


def check_workspace_quota_preflight(project_root: Path, output_dir: Path, run: dict[str, Any], request: dict[str, Any], route_decision: dict[str, Any]) -> dict[str, Any] | None:
    if not quota_is_enabled(request):
        return None
    selected = route_decision.get("selected") or {}
    report = check_workspace_quota_from_paths(
        quota_config_path(project_root, request),
        quota_state_path(project_root, request),
        workspace_id=workspace_id_for_run(run, request),
        usage=route_decision.get("estimated_usage") or {},
        cost=selected.get("estimated_cost") or {},
    )
    save_json(output_dir / "workspace_quota_check.json", report)
    run["workspace_quota_check"] = report
    if not report.get("allowed"):
        raise ProviderError("workspace_quota_exceeded", "workspace quota exceeded", details=report)
    return report


def record_workspace_quota_actual(project_root: Path, output_dir: Path, run: dict[str, Any], request: dict[str, Any], provider_response: dict[str, Any], route_decision: dict[str, Any]) -> dict[str, Any] | None:
    if not quota_is_enabled(request):
        return None
    selected = route_decision.get("selected") or {}
    report = record_workspace_usage_to_path(
        quota_state_path(project_root, request),
        workspace_id=workspace_id_for_run(run, request),
        usage=provider_response.get("usage") or {},
        cost=provider_response.get("cost") or {},
        metadata={"request_id": run.get("run_id"), "trace_id": run.get("session_id"), "model_id": route_decision.get("selected_model_id"), "provider": selected.get("provider"), "source": "agent_provider_actual"},
    )
    run["workspace_quota_usage"] = report
    provider_response["workspace_quota_usage"] = report
    save_json(output_dir / "workspace_quota_usage.json", report)
    return report


def apply_usage_reconciliation(output_dir: Path, run: dict[str, Any], route_decision: dict[str, Any], provider_response: dict[str, Any], instances: dict[str, Any], *, filename: str = "provider_usage_reconciliation.json") -> dict[str, Any]:
    selected_model_id = route_decision.get("selected_model_id")
    instance = next((item for item in instances.get("instances", []) if item.get("id") == selected_model_id), {})
    report = reconcile_provider_usage(route_decision, provider_response, instance, currency=instances.get("default_currency", "USD"))
    provider_response["usage_reconciliation"] = report
    provider_response["usage"] = reconciled_usage(report)
    provider_response["cost"] = reconciled_cost(report)
    run["usage_reconciliation"] = report
    run["usage"] = provider_response.get("usage") or run.get("usage") or {}
    run["cost"] = provider_response.get("cost") or run.get("cost") or {}
    save_json(output_dir / filename, report)
    return report


def run_skill_loop(project_root: Path, output_dir: Path, run: dict[str, Any], request: dict[str, Any], events: AgentEventWriter | None = None, store: Any | None = None) -> None:
    skill_calls = request.get("skill_calls") or []
    if not skill_calls:
        return
    if apply_cancellation_if_requested(output_dir, run, events, checkpoint="before_skill_loop", store=store):
        return
    results = []
    for index, spec in enumerate(skill_calls):
        if apply_cancellation_if_requested(output_dir, run, events, checkpoint=f"before_skill_{index}", store=store):
            return
        name = spec.get("name") or spec.get("skill_id")
        args = spec.get("arguments") or {}
        step = add_step(run, "skill_call", input_data={"name": name, "arguments": args}, status="running")
        if events:
            events.emit("skill_started", status="running", step=step, data={"name": name})
        try:
            result = call_skill(
                load_json(project_root / "configs" / "skills" / "foundation_skills.json"),
                name,
                args,
                allow_provider=bool(spec.get("allow_provider") or request.get("allow_skill_provider")),
                allow_write=bool(spec.get("allow_write") or request.get("allow_skill_write")),
                approved=bool(spec.get("approved") or request.get("approve_skills")),
            )
            step["status"] = "completed"
            step["output"] = result
            results.append({"name": name, "status": "ok", "result": result})
            if events:
                events.emit("skill_completed", status="completed", step=step, data={"name": name})
        except Exception as exc:  # noqa: BLE001
            step["status"] = "failed"
            step["error"] = str(exc)
            item = {"name": name, "status": "failed", "error": str(exc)}
            results.append(item)
            if events:
                events.emit("skill_failed", status="failed", step=step, error=str(exc), data={"name": name})
            if not spec.get("continue_on_error"):
                run["skill_results"] = results
                save_json(output_dir / "skill_results.json", {"results": results})
                raise SkillError(str(exc)) from exc
    run["skill_results"] = results
    save_json(output_dir / "skill_results.json", {"results": results})


def build_provider_request(request: dict[str, Any], foundation_request: dict[str, Any], selected_model_id: str) -> dict[str, Any]:
    return {**request, **foundation_request, "model_id": selected_model_id, "execute_provider": True}


def run_provider_step(project_root: Path, output_dir: Path, run: dict[str, Any], request: dict[str, Any], foundation_request: dict[str, Any], route_decision: dict[str, Any], instances: dict[str, Any], events: AgentEventWriter | None = None, store: Any | None = None) -> dict[str, Any]:
    selected_model_id = route_decision.get("selected_model_id")
    if not selected_model_id:
        raise ProviderError("router_no_candidate", "no selected model for provider execution", details=route_decision)
    check_workspace_quota_preflight(project_root, output_dir, run, request, route_decision)
    provider_request = build_provider_request(request, foundation_request, selected_model_id)
    step = add_step(run, "provider_generate", input_data={"model_id": selected_model_id, "stream": bool(request.get("stream"))}, status="running")
    if events:
        events.emit("provider_started", status="running", step=step, data={"model_id": selected_model_id, "stream": bool(request.get("stream")), "workspace_quota_enabled": quota_is_enabled(request)})
    if apply_cancellation_if_requested(output_dir, run, events, checkpoint="before_provider", store=store):
        raise ProviderError("cancelled", "run cancelled before provider execution", details=run.get("cancelled") or {})
    response = generate_provider_round(
        request=provider_request,
        instances=instances,
        selected_model_id=selected_model_id,
        output_dir=output_dir,
        stream=bool(request.get("stream_provider_tool_calls")),
        stream_include_usage=bool(request.get("stream_include_usage")),
        incremental_tools=bool(request.get("incremental_stream_tool_execution")),
        registry=load_json(project_root / "configs" / "skills" / "foundation_skills.json"),
        allow_provider=bool(request.get("allow_model_tool_provider")),
        allow_write=bool(request.get("allow_model_tool_write")),
        approved=bool(request.get("approve_model_tools")),
    )
    if apply_cancellation_if_requested(output_dir, run, events, checkpoint="after_provider_generate", store=store):
        raise ProviderError("cancelled", "run cancelled after provider execution", details=run.get("cancelled") or {})
    run["provider_response"] = response
    save_json(output_dir / "provider_response.json", response)
    if response.get("status") == "ok":
        reconciliation = apply_usage_reconciliation(output_dir, run, route_decision, response, instances)
        quota_report = record_workspace_quota_actual(project_root, output_dir, run, request, response, route_decision)
        if events:
            events.emit("usage_reconciled", status="completed", data={"model_id": selected_model_id, "usage_source": reconciliation.get("usage_source"), "summary": reconciliation.get("summary") or {}})
            if quota_report:
                events.emit("workspace_quota_recorded", status="completed", data={"workspace_id": quota_report.get("workspace_id"), "periods": quota_report.get("periods") or []})
    step["status"] = "completed" if response.get("status") == "ok" else "failed"
    step["output"] = {"status": response.get("status"), "usage": response.get("usage"), "cost": response.get("cost"), "stream": response.get("stream") or {}, "incremental_tool_results": len(response.get("incremental_tool_results") or [])}
    if response.get("status") != "ok":
        if events:
            events.emit("provider_failed", status="failed", step=step, data={"model_id": selected_model_id}, error="provider response was not ok")
        raise ProviderError("provider_error", "provider response was not ok", details=response)
    if events:
        events.emit("provider_completed", status="completed", step=step, data={"model_id": selected_model_id, "usage": response.get("usage") or {}, "cost": response.get("cost") or {}, "stream": response.get("stream") or {}})
    return response


def maybe_run_model_tool_loop(project_root: Path, output_dir: Path, run: dict[str, Any], request: dict[str, Any], foundation_request: dict[str, Any], route_decision: dict[str, Any], instances: dict[str, Any], provider_response: dict[str, Any], events: AgentEventWriter | None = None, store: Any | None = None) -> None:
    if not request.get("enable_model_tool_loop"):
        return
    if apply_cancellation_if_requested(output_dir, run, events, checkpoint="before_model_tool_loop", store=store):
        return
    selected_model_id = route_decision.get("selected_model_id")
    if not selected_model_id:
        return
    max_rounds = int(request.get("max_tool_rounds") or 3)
    if events:
        events.emit("model_tool_loop_started", status="running", data={"model_id": selected_model_id, "max_rounds": max_rounds, "stream_provider_tool_calls": bool(request.get("stream_provider_tool_calls")), "incremental_stream_tool_execution": bool(request.get("incremental_stream_tool_execution"))})
    summary = run_model_tool_loop(project_root=project_root, output_dir=output_dir, request=request, foundation_request=foundation_request, instances=instances, selected_model_id=selected_model_id, initial_provider_response=provider_response, max_rounds=max_rounds)
    run["model_tool_loop"] = summary
    if summary.get("final_provider_response"):
        run["provider_response"] = summary["final_provider_response"]
        if (run["provider_response"] or {}).get("status") == "ok":
            final_report = apply_usage_reconciliation(output_dir, run, route_decision, run["provider_response"], instances, filename="provider_usage_reconciliation_final.json")
            save_json(output_dir / "provider_response_final.json", run["provider_response"])
            if events:
                events.emit("usage_reconciled", status="completed", data={"model_id": selected_model_id, "scope": "model_tool_loop_final", "usage_source": final_report.get("usage_source"), "summary": final_report.get("summary") or {}})
    if (run.get("provider_response") or {}).get("usage"):
        run["usage"] = run["provider_response"]["usage"]
    if (run.get("provider_response") or {}).get("cost"):
        run["cost"] = run["provider_response"]["cost"]
    step = add_step(run, "model_tool_loop", status="completed" if summary.get("status") == "ok" else "failed", output_data={"status": summary.get("status"), "round_count": summary.get("round_count", len(summary.get("rounds", []))), "error": summary.get("error"), "stream_provider_tool_calls": summary.get("stream_provider_tool_calls"), "incremental_stream_tool_execution": summary.get("incremental_stream_tool_execution")})
    if summary.get("status") != "ok":
        if events:
            events.emit("model_tool_loop_failed", status="failed", step=step, data={"round_count": summary.get("round_count", len(summary.get("rounds", [])))}, error=str(summary.get("error") or "model tool loop failed"))
        raise SkillError(str(summary.get("error") or "model tool loop failed"))
    if events:
        events.emit("model_tool_loop_completed", status="completed", step=step, data={"round_count": summary.get("round_count", len(summary.get("rounds", []))), "stream_provider_tool_calls": summary.get("stream_provider_tool_calls"), "incremental_stream_tool_execution": summary.get("incremental_stream_tool_execution")})


def attach_artifacts(output_dir: Path, run: dict[str, Any]) -> None:
    run["artifacts"] = {"report": str(output_dir / "agent_run_report.json"), "request": str(output_dir / "agent_request.json"), "events": str(output_dir / "events.jsonl"), "usage_ledger": str(output_dir / "usage_ledger.jsonl")}
    if (output_dir / CANCEL_REQUEST_FILENAME).exists():
        run["artifacts"]["cancel_request"] = str(output_dir / CANCEL_REQUEST_FILENAME)
    if run.get("provider_response"):
        run["artifacts"]["provider_response"] = str(output_dir / "provider_response.json")
    if (output_dir / "provider_response_final.json").exists():
        run["artifacts"]["provider_response_final"] = str(output_dir / "provider_response_final.json")
    if (output_dir / "provider_usage_reconciliation.json").exists():
        run["artifacts"]["provider_usage_reconciliation"] = str(output_dir / "provider_usage_reconciliation.json")
    if (output_dir / "provider_usage_reconciliation_final.json").exists():
        run["artifacts"]["provider_usage_reconciliation_final"] = str(output_dir / "provider_usage_reconciliation_final.json")
    if (output_dir / "workspace_quota_check.json").exists():
        run["artifacts"]["workspace_quota_check"] = str(output_dir / "workspace_quota_check.json")
    if (output_dir / "workspace_quota_usage.json").exists():
        run["artifacts"]["workspace_quota_usage"] = str(output_dir / "workspace_quota_usage.json")
    if (run.get("provider_response") or {}).get("stream_chunks_path"):
        run["artifacts"]["provider_stream_chunks"] = str((run.get("provider_response") or {}).get("stream_chunks_path"))
    if (run.get("provider_response") or {}).get("incremental_tool_results_path"):
        run["artifacts"]["incremental_tool_results"] = str((run.get("provider_response") or {}).get("incremental_tool_results_path"))
    if run.get("skill_results"):
        run["artifacts"]["skill_results"] = str(output_dir / "skill_results.json")
    if run.get("model_tool_loop"):
        run["artifacts"]["model_tool_loop"] = str(output_dir / "model_tool_loop.json")


def finalize_events(output_dir: Path, run: dict[str, Any], store: Any | None = None) -> None:
    if store is not None and hasattr(store, "load_events"):
        try:
            events = store.load_events(str(run.get("run_id")))
        except Exception:  # noqa: BLE001
            events = read_agent_events(output_dir / "events.jsonl")
    else:
        events = read_agent_events(output_dir / "events.jsonl")
    run["event_summary"] = summarize_agent_events(events)
    index_events_in_store(store, output_dir, run)


def finalize_run(output_dir: Path, run: dict[str, Any], store: Any | None = None) -> dict[str, Any]:
    attach_artifacts(output_dir, run)
    finalize_events(output_dir, run, store)
    save_json(output_dir / "agent_run_report.json", run)
    maybe_store_save_report(store, str(run.get("run_id")), run)
    index_artifacts_in_store(store, run)
    return run


def run_agent_once(project_root: Path, request: dict[str, Any], output_dir: Path, instances_path: Path | None = None, rules_path: Path | None = None, store: Any | None = None) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    run = create_run(request)
    request_to_save = {**request, "run_id": request.get("run_id") or run["run_id"]}
    save_json(output_dir / "agent_request.json", request_to_save)
    maybe_store_save_request(store, run["run_id"], request_to_save)
    events = AgentEventWriter(output_dir / "events.jsonl", run, enabled=not bool(request.get("disable_events")), store=store)
    events.emit("run_created", status="queued", data={"task": run.get("task"), "route_mode": run.get("route_mode"), "retry_of": run.get("retry_of"), "resume_of": run.get("resume_of")})
    created_path = output_dir / "agent_run_created.json"
    save_json(created_path, run)
    maybe_store_save_created_run(store, run["run_id"], run, created_path)
    if apply_cancellation_if_requested(output_dir, run, events, checkpoint="created", store=store):
        return finalize_run(output_dir, run, store)
    transition(run, "running")
    step = add_step(run, "start", output_data={"status": "running"})
    events.emit("run_started", status="running", step=step)
    if apply_cancellation_if_requested(output_dir, run, events, checkpoint="started", store=store):
        return finalize_run(output_dir, run, store)

    foundation_request = build_foundation_request({**run, **request})
    instances = load_json(instances_path or project_root / "configs" / "model_instance_registry.json")
    events.emit("route_started", status="running", data={"route_mode": foundation_request.get("route_mode"), "required_capabilities": foundation_request.get("required_capabilities")})
    route_decision = route_model(foundation_request, instances)
    run["route_decision"] = route_decision
    run["usage"] = route_decision.get("estimated_usage") or {}
    if route_decision.get("selected"):
        run["cost"] = (route_decision["selected"].get("estimated_cost") or {})
    step = add_step(run, "route_model", input_data=foundation_request, output_data=route_decision, status="completed" if route_decision.get("status") == "routed" else "failed")
    events.emit("route_completed" if route_decision.get("status") == "routed" else "route_failed", status=step["status"], step=step, data={"selected_model_id": route_decision.get("selected_model_id"), "route_status": route_decision.get("status")})
    if apply_cancellation_if_requested(output_dir, run, events, checkpoint="after_route", store=store):
        return finalize_run(output_dir, run, store)

    if route_decision.get("status") != "routed":
        run["error"] = "router_no_candidate"
        transition(run, "failed")
        events.emit("run_failed", status="failed", message="router_no_candidate", error="router_no_candidate")
        return finalize_run(output_dir, run, store)

    ruleset = load_rules(rules_path or project_root / "configs" / "rules" / "default_rules.yaml")
    rule_context = rule_context_from_route(foundation_request, route_decision, instances)
    events.emit("rules_started", status="running")
    rule_decision = evaluate_rules(ruleset, rule_context)
    run["rule_decision"] = rule_decision
    step = add_step(run, "evaluate_rules", input_data=rule_context, output_data=rule_decision)
    events.emit("rules_completed", status="completed", step=step, data={"decision": rule_decision.get("decision"), "matched_rule_count": len(rule_decision.get("matched_rules") or [])})
    if apply_cancellation_if_requested(output_dir, run, events, checkpoint="after_rules", store=store):
        return finalize_run(output_dir, run, store)

    if rule_decision.get("decision") == "deny":
        run["error"] = "policy_denied"
        record_usage(output_dir, run)
        transition(run, "failed")
        events.emit("run_failed", status="failed", message="policy_denied", error="policy_denied")
    elif approval_required(run, rule_decision, route_decision):
        step = add_step(run, "approval_gate", status="waiting_approval", output_data={"reason": "approval_required"})
        record_usage(output_dir, run)
        transition(run, "waiting_approval")
        events.emit("run_waiting_approval", status="waiting_approval", step=step, message="approval_required")
    else:
        try:
            run_skill_loop(project_root, output_dir, run, request, events, store)
            if run.get("status") == "cancelled":
                return finalize_run(output_dir, run, store)
        except SkillError as exc:
            run["error"] = "skill_failed"
            step = add_step(run, "skill_loop_error", status="failed", output_data={"message": str(exc)}, error=str(exc))
            events.emit("skill_loop_failed", status="failed", step=step, error=str(exc))
            record_usage(output_dir, run)
            transition(run, "failed")
            events.emit("run_failed", status="failed", message="skill_failed", error=str(exc))
        else:
            if apply_cancellation_if_requested(output_dir, run, events, checkpoint="before_provider_branch", store=store):
                return finalize_run(output_dir, run, store)
            if request.get("execute_provider"):
                try:
                    provider_response = run_provider_step(project_root, output_dir, run, request, foundation_request, route_decision, instances, events, store)
                    if apply_cancellation_if_requested(output_dir, run, events, checkpoint="after_provider", store=store):
                        return finalize_run(output_dir, run, store)
                    maybe_run_model_tool_loop(project_root, output_dir, run, request, foundation_request, route_decision, instances, provider_response, events, store)
                    if run.get("status") != "cancelled":
                        transition(run, "completed")
                        events.emit("run_completed", status="completed", data={"usage": run.get("usage") or {}, "cost": run.get("cost") or {}})
                except SkillError as exc:
                    run["error"] = "model_tool_loop_failed"
                    step = add_step(run, "model_tool_loop_error", status="failed", output_data={"message": str(exc)}, error=str(exc))
                    events.emit("model_tool_loop_failed", status="failed", step=step, error=str(exc))
                    transition(run, "failed")
                    events.emit("run_failed", status="failed", message="model_tool_loop_failed", error=str(exc))
                except ProviderError as exc:
                    if exc.code == "cancelled" and run.get("status") == "cancelled":
                        return finalize_run(output_dir, run, store)
                    run["error"] = exc.code
                    step = add_step(run, "provider_error", status="failed", output_data={"code": exc.code, "message": exc.message, "details": exc.details}, error=exc.message)
                    events.emit("provider_failed", status="failed", step=step, error=exc.message, data={"code": exc.code, "details": exc.details})
                    transition(run, "failed")
                    events.emit("run_failed", status="failed", message=exc.code, error=exc.message)
            else:
                step = add_step(run, "ready_for_provider", output_data={"selected_model_id": route_decision.get("selected_model_id"), "provider_execution": "skipped"})
                events.emit("provider_skipped", status="completed", step=step, data={"selected_model_id": route_decision.get("selected_model_id")})
                record_usage(output_dir, run)
                if not apply_cancellation_if_requested(output_dir, run, events, checkpoint="provider_skipped", store=store):
                    transition(run, "completed")
                    events.emit("run_completed", status="completed", data={"usage": run.get("usage") or {}, "cost": run.get("cost") or {}})

    return finalize_run(output_dir, run, store)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--request", required=True)
    parser.add_argument("--output-dir", default="outputs/agent_runtime/run")
    parser.add_argument("--instances", default=None)
    parser.add_argument("--rules", default=None)
    parser.add_argument("--run-store", choices=["none", "sqlite"], default="none")
    parser.add_argument("--sqlite-path", default=None)
    args = parser.parse_args()
    request = load_json(Path(args.request))
    store = None
    if args.run_store == "sqlite":
        from agent.sqlite_run_store import sqlite_run_store

        store = sqlite_run_store(Path(args.sqlite_path) if args.sqlite_path else Path(args.output_dir).parent / "runs.sqlite")
    run = run_agent_once(Path(args.project_root), request, Path(args.output_dir), Path(args.instances) if args.instances else None, Path(args.rules) if args.rules else None, store=store)
    print(json.dumps(run, ensure_ascii=False, indent=2))
    return 0 if run.get("status") == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
