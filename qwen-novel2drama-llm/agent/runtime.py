from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from inference.model_router import route_model
from services.rule_engine import evaluate_rules, load_rules

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
        "required_capabilities": ["text.chat"],
        "input": run.get("input") or [],
    }
    if run.get("task"):
        request["input"] = [{"type": "text", "text": run["task"]}] + request["input"]
    for key in ["privacy", "budget", "expected_output_tokens", "expected_reasoning_tokens", "max_sensitivity", "owner_id"]:
        if run.get(key) is not None:
            request[key] = run[key]
    return request


def rule_context_from_route(request: dict[str, Any], route_decision: dict[str, Any]) -> dict[str, Any]:
    selected = route_decision.get("selected") or {}
    return {
        "request": request,
        "candidate": {
            "provider": selected.get("provider"),
            "estimated_cost": selected.get("estimated_cost") or {},
            "capabilities": selected.get("capabilities") or [],
            "lifecycle": selected.get("lifecycle"),
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
    rule_context = rule_context_from_route(foundation_request, route_decision)
    rule_decision = evaluate_rules(ruleset, rule_context)
    run["rule_decision"] = rule_decision
    add_step(run, "evaluate_rules", input_data=rule_context, output_data=rule_decision)

    if rule_decision.get("decision") == "deny":
        run["error"] = "policy_denied"
        transition(run, "failed")
    elif approval_required(run, rule_decision, route_decision):
        add_step(run, "approval_gate", status="waiting_approval", output_data={"reason": "approval_required"})
        transition(run, "waiting_approval")
    else:
        add_step(run, "ready_for_provider", output_data={"selected_model_id": route_decision.get("selected_model_id")})
        transition(run, "completed")

    run["artifacts"] = {"report": str(output_dir / "agent_run_report.json")}
    save_json(output_dir / "agent_run_report.json", run)
    return run


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--request", required=True)
    parser.add_argument("--output-dir", default="outputs/agent_runtime/run")
    parser.add_argument("--instances", default=None)
    parser.add_argument("--rules", default=None)
    args = parser.parse_args()
    project_root = Path(args.project_root).resolve()
    request = load_json(Path(args.request))
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
