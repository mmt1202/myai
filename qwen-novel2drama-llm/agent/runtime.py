from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from inference.model_router import route_model
from providers.base import ProviderError
from providers.factory import generate_with_registry
from services.rule_engine import evaluate_rules, load_rules
from services.usage_ledger import write_event
from skills.registry import SkillError, call_skill

RUN_STATES = {"queued", "running", "waiting_tool", "waiting_approval", "completed", "failed", "cancelled"}
TERMINAL_STATES = {"completed", "failed", "cancelled"}
APPROVAL_POLICIES = {"never", "on_write", "on_cost", "always"}
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
        "task": request.get("task") or "",
        "input": request.get("input") or [],
        "route_mode": request.get("route_mode") or "balanced",
        "approval_policy": approval_policy,
        "status": "queued",
        "steps": [],
        "route_decision": None,
        "rule_decision": None,
        "skill_results": [],
        "provider_response": None,
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


def add_step(run: dict[str, Any], step_type: str, status: str = "completed", input_data: dict[str, Any] | None = None, output_data: dict[str, Any] | None = None, error: str | None = None) -> dict[str, Any]:
    if status not in RUN_STATES:
        raise ValueError(f"unsupported step status: {status}")
    created_at = now_iso()
    step = {
        "step_id": new_id("step"),
        "type": step_type,
        "status": status,
        "input": input_data or {},
        "output": output_data or {},
        "error": error,
        "created_at": created_at,
        "updated_at": created_at,
    }
    run.setdefault("steps", []).append(step)
    run["updated_at"] = created_at
    return step


def build_foundation_request(run: dict[str, Any]) -> dict[str, Any]:
    request = {
        "request_id": run["run_id"],
        "trace_id": run["run_id"],
        "route_mode": run.get("route_mode") or "balanced",
        "required_capabilities": run.get("required_capabilities") or ["text.chat"],
        "input": run.get("input") or [],
    }
    if run.get("task"):
        request["input"] = [{"type": "text", "text": run["task"]}] + request["input"]
    for key in [
        "privacy",
        "budget",
        "expected_output_tokens",
        "expected_reasoning_tokens",
        "max_sensitivity",
        "owner_id",
        "temperature",
        "max_output_tokens",
        "tools",
        "tool_choice",
        "system",
        "developer",
    ]:
        if run.get(key) is not None:
            request[key] = run[key]
    return request


def rule_context_from_route(request: dict[str, Any], route_decision: dict[str, Any], instances: dict[str, Any]) -> dict[str, Any]:
    selected = route_decision.get("selected") or {}
    selected_id = route_decision.get("selected_model_id")
    instance = next((item for item in instances.get("instances", []) if item.get("id") == selected_id), {})
    return {
        "request": request,
        "candidate": {
            "provider": selected.get("provider") or instance.get("provider"),
            "estimated_cost": selected.get("estimated_cost") or {},
            "capabilities": instance.get("capabilities") or [],
            "lifecycle": instance.get("lifecycle"),
        },
    }


def approval_required(run: dict[str, Any], rule_decision: dict[str, Any], route_decision: dict[str, Any]) -> bool:
    policy = run.get("approval_policy") or "on_cost"
    if policy == "always":
        return True
    if rule_decision.get("decision") == "review":
        return True
    if rule_decision.get("decision") == "deny":
        return False
    if policy == "never":
        return False
    if policy == "on_cost":
        selected = route_decision.get("selected") or {}
        estimated = ((selected.get("estimated_cost") or {}).get("estimated") or 0)
        threshold = ((run.get("budget") or {}).get("approval_threshold") or None)
        return threshold is not None and float(estimated) > float(threshold)
    return False


def build_provider_request(request: dict[str, Any], foundation_request: dict[str, Any], selected_model_id: str) -> dict[str, Any]:
    provider_request = {**foundation_request}
    provider_request["model_id"] = selected_model_id
    provider_request["model"] = selected_model_id
    provider_request["dry_run"] = bool(request.get("dry_run_provider"))
    provider_request["base_url"] = request.get("base_url")
    provider_request["api_key_env"] = request.get("api_key_env") or "MODEL_API_KEY"
    return provider_request


def record_usage(output_dir: Path, run: dict[str, Any], provider_response: dict[str, Any] | None = None) -> None:
    response = provider_response or {}
    usage = response.get("usage") or run.get("usage") or {}
    cost = response.get("cost") or run.get("cost") or {}
    write_event(
        output_dir / "usage_ledger.jsonl",
        {
            "request_id": run.get("run_id"),
            "trace_id": run.get("run_id"),
            "model_id": (run.get("route_decision") or {}).get("selected_model_id"),
            "provider": (((run.get("route_decision") or {}).get("selected") or {}).get("provider")),
            "route_mode": run.get("route_mode"),
            "usage": usage,
            "cost": cost,
            "status": "actual" if provider_response else "estimated",
        },
    )


def normalize_skill_call(call: dict[str, Any]) -> dict[str, Any]:
    name = call.get("name") or call.get("skill_id")
    if not name:
        raise SkillError("skill call requires name or skill_id")
    return {
        "name": str(name),
        "arguments": call.get("arguments") or {},
        "allow_provider": bool(call.get("allow_provider")),
        "allow_write": bool(call.get("allow_write")),
        "approved": bool(call.get("approved")),
        "continue_on_error": bool(call.get("continue_on_error")),
    }


def run_skill_loop(project_root: Path, output_dir: Path, run: dict[str, Any], request: dict[str, Any]) -> None:
    calls = request.get("skill_calls") or []
    if not calls:
        return
    registry = load_json(project_root / "configs" / "skills" / "foundation_skills.json")
    results: list[dict[str, Any]] = []
    default_allow_provider = bool(request.get("allow_skill_provider"))
    default_allow_write = bool(request.get("allow_skill_write"))
    default_approved = bool(request.get("approve_skills"))
    add_step(run, "skill_loop_start", output_data={"skill_call_count": len(calls)})
    for raw_call in calls:
        call = normalize_skill_call(raw_call)
        allow_provider = default_allow_provider or call["allow_provider"]
        allow_write = default_allow_write or call["allow_write"]
        approved = default_approved or call["approved"]
        try:
            result = call_skill(
                registry,
                call["name"],
                call["arguments"],
                allow_provider=allow_provider,
                allow_write=allow_write,
                approved=approved,
            )
            results.append(result)
            add_step(run, "skill_call", input_data={"name": call["name"], "permissions": {"allow_provider": allow_provider, "allow_write": allow_write, "approved": approved}}, output_data=result)
        except Exception as exc:  # noqa: BLE001
            failure = {"skill_id": call["name"], "status": "failed", "error": str(exc)}
            results.append(failure)
            add_step(run, "skill_call", status="failed", input_data={"name": call["name"]}, output_data=failure, error=str(exc))
            if not call["continue_on_error"]:
                run["skill_results"] = results
                save_json(output_dir / "skill_results.json", {"results": results})
                raise SkillError(str(exc)) from exc
    run["skill_results"] = results
    save_json(output_dir / "skill_results.json", {"results": results})
    add_step(run, "skill_loop_completed", output_data={"skill_result_count": len(results)})


def run_provider_step(project_root: Path, output_dir: Path, run: dict[str, Any], request: dict[str, Any], foundation_request: dict[str, Any], route_decision: dict[str, Any], instances: dict[str, Any]) -> None:
    selected_model_id = route_decision.get("selected_model_id")
    if not selected_model_id:
        raise ProviderError("model_not_found", "selected model id is missing")
    provider_request = build_provider_request(request, foundation_request, selected_model_id)
    response = generate_with_registry(
        provider_request,
        instances,
        model_id=selected_model_id,
        base_url=request.get("base_url"),
        api_key_env=request.get("api_key_env") or "MODEL_API_KEY",
    )
    run["provider_response"] = response
    if response.get("usage"):
        run["usage"] = response["usage"]
    if response.get("cost"):
        run["cost"] = response["cost"]
    save_json(output_dir / "provider_response.json", response)
    record_usage(output_dir, run, provider_response=response)
    add_step(run, "provider_generate", input_data={"model_id": selected_model_id, "dry_run": provider_request.get("dry_run")}, output_data=response, status="completed" if response.get("status") == "ok" else "failed")
    if response.get("status") != "ok":
        raise ProviderError("provider_error", "provider response was not ok", details=response)


def run_agent_once(project_root: Path, request: dict[str, Any], output_dir: Path, instances_path: Path | None = None, rules_path: Path | None = None) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    run = create_run(request)
    save_json(output_dir / "agent_run_created.json", run)
    transition(run, "running")
    add_step(run, "start", output_data={"status": "running"})

    foundation_request = build_foundation_request({**run, **request})
    instances = load_json(instances_path or project_root / "configs" / "model_instance_registry.json")
    route_decision = route_model(foundation_request, instances)
    run["route_decision"] = route_decision
    run["usage"] = route_decision.get("estimated_usage") or {}
    if route_decision.get("selected"):
        run["cost"] = (route_decision["selected"].get("estimated_cost") or {})
    add_step(run, "route_model", input_data=foundation_request, output_data=route_decision, status="completed" if route_decision.get("status") == "routed" else "failed")

    if route_decision.get("status") != "routed":
        run["error"] = "router_no_candidate"
        transition(run, "failed")
        save_json(output_dir / "agent_run_report.json", run)
        return run

    ruleset = load_rules(rules_path or project_root / "configs" / "rules" / "default_rules.yaml")
    rule_context = rule_context_from_route(foundation_request, route_decision, instances)
    rule_decision = evaluate_rules(ruleset, rule_context)
    run["rule_decision"] = rule_decision
    add_step(run, "evaluate_rules", input_data=rule_context, output_data=rule_decision)

    if rule_decision.get("decision") == "deny":
        run["error"] = "policy_denied"
        record_usage(output_dir, run)
        transition(run, "failed")
    elif approval_required(run, rule_decision, route_decision):
        add_step(run, "approval_gate", status="waiting_approval", output_data={"reason": "approval_required"})
        record_usage(output_dir, run)
        transition(run, "waiting_approval")
    else:
        try:
            run_skill_loop(project_root, output_dir, run, request)
        except SkillError as exc:
            run["error"] = "skill_failed"
            add_step(run, "skill_loop_error", status="failed", output_data={"message": str(exc)}, error=str(exc))
            record_usage(output_dir, run)
            transition(run, "failed")
        else:
            if request.get("execute_provider"):
                try:
                    run_provider_step(project_root, output_dir, run, request, foundation_request, route_decision, instances)
                    transition(run, "completed")
                except ProviderError as exc:
                    run["error"] = exc.code
                    add_step(run, "provider_error", status="failed", output_data={"code": exc.code, "message": exc.message, "details": exc.details}, error=exc.message)
                    transition(run, "failed")
            else:
                add_step(run, "ready_for_provider", output_data={"selected_model_id": route_decision.get("selected_model_id"), "provider_execution": "skipped"})
                record_usage(output_dir, run)
                transition(run, "completed")

    run["artifacts"] = {
        "report": str(output_dir / "agent_run_report.json"),
        "usage_ledger": str(output_dir / "usage_ledger.jsonl"),
    }
    if run.get("provider_response"):
        run["artifacts"]["provider_response"] = str(output_dir / "provider_response.json")
    if run.get("skill_results"):
        run["artifacts"]["skill_results"] = str(output_dir / "skill_results.json")
    save_json(output_dir / "agent_run_report.json", run)
    return run


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--request", required=True)
    parser.add_argument("--output-dir", default="outputs/agent_runtime/run")
    parser.add_argument("--instances", default=None)
    parser.add_argument("--rules", default=None)
    parser.add_argument("--execute-provider", action="store_true")
    parser.add_argument("--dry-run-provider", action="store_true")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--api-key-env", default="MODEL_API_KEY")
    parser.add_argument("--allow-skill-provider", action="store_true")
    parser.add_argument("--allow-skill-write", action="store_true")
    parser.add_argument("--approve-skills", action="store_true")
    args = parser.parse_args()
    project_root = Path(args.project_root).resolve()
    request = load_json(Path(args.request))
    if args.execute_provider:
        request["execute_provider"] = True
    if args.dry_run_provider:
        request["dry_run_provider"] = True
    if args.base_url:
        request["base_url"] = args.base_url
    if args.api_key_env:
        request["api_key_env"] = args.api_key_env
    if args.allow_skill_provider:
        request["allow_skill_provider"] = True
    if args.allow_skill_write:
        request["allow_skill_write"] = True
    if args.approve_skills:
        request["approve_skills"] = True
    run = run_agent_once(
        project_root=project_root,
        request=request,
        output_dir=project_root / args.output_dir,
        instances_path=Path(args.instances) if args.instances else None,
        rules_path=Path(args.rules) if args.rules else None,
    )
    print(json.dumps(run, ensure_ascii=False, indent=2))
    return 0 if run.get("status") not in {"failed", "cancelled"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
