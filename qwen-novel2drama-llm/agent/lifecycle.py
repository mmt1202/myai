from __future__ import annotations

import argparse
import json
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any

from agent.events import AgentEventWriter, read_agent_events, summarize_agent_events
from agent.runtime import CANCEL_REQUEST_FILENAME, run_agent_once, save_json, now_iso

TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
RESTARTABLE_STATUSES = {"failed", "cancelled", "waiting_approval", "waiting_tool"}


def safe_run_id(value: str) -> str:
    run_id = str(value or "").strip()
    if not run_id or "/" in run_id or "\\" in run_id or ".." in run_id:
        raise ValueError(f"invalid run_id: {value}")
    return run_id


def run_dir(output_root: Path, run_id: str) -> Path:
    return output_root / safe_run_id(run_id)


def load_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        if default is not None:
            return deepcopy(default)
        raise FileNotFoundError(str(path))
    return json.loads(path.read_text(encoding="utf-8"))


def run_report_path(output_root: Path, run_id: str) -> Path:
    return run_dir(output_root, run_id) / "agent_run_report.json"


def load_run_report(output_root: Path, run_id: str) -> dict[str, Any]:
    return load_json(run_report_path(output_root, run_id))


def original_request_from_report(report: dict[str, Any]) -> dict[str, Any]:
    request: dict[str, Any] = {}
    for key in [
        "run_id",
        "session_id",
        "owner_id",
        "project_id",
        "workspace_id",
        "task",
        "input",
        "route_mode",
        "approval_policy",
        "usage",
        "cost",
    ]:
        if report.get(key) is not None:
            request[key] = deepcopy(report[key])
    if report.get("route_decision"):
        selected = (report.get("route_decision") or {}).get("selected_model_id")
        if selected:
            request["model_id"] = selected
    return request


def load_original_request(output_root: Path, run_id: str) -> dict[str, Any]:
    directory = run_dir(output_root, run_id)
    request_path = directory / "agent_request.json"
    if request_path.exists():
        return load_json(request_path)
    return original_request_from_report(load_run_report(output_root, run_id))


def status_run(output_root: Path, run_id: str) -> dict[str, Any]:
    report = load_run_report(output_root, run_id)
    directory = run_dir(output_root, run_id)
    events_path = directory / "events.jsonl"
    events = read_agent_events(events_path)
    return {
        "run_id": safe_run_id(run_id),
        "status": report.get("status"),
        "error": report.get("error"),
        "created_at": report.get("created_at"),
        "updated_at": report.get("updated_at"),
        "completed_at": report.get("completed_at"),
        "cancel_requested": (directory / CANCEL_REQUEST_FILENAME).exists(),
        "artifacts": report.get("artifacts") or {},
        "event_summary": summarize_agent_events(events),
    }


def write_lifecycle_event(output_root: Path, run_id: str, report: dict[str, Any], event_type: str, *, status: str, message: str | None = None, data: dict[str, Any] | None = None, error: str | None = None) -> None:
    writer = AgentEventWriter(run_dir(output_root, run_id) / "events.jsonl", report, enabled=True)
    writer.emit(event_type, status=status, message=message, data=data or {}, error=error)


def cancel_run(output_root: Path, run_id: str, *, reason: str | None = None, requested_by: str | None = None) -> dict[str, Any]:
    directory = run_dir(output_root, run_id)
    directory.mkdir(parents=True, exist_ok=True)
    marker = {
        "created_at": now_iso(),
        "run_id": safe_run_id(run_id),
        "reason": reason or "cancel_requested",
        "requested_by": requested_by,
    }
    save_json(directory / CANCEL_REQUEST_FILENAME, marker)
    report_path = directory / "agent_run_report.json"
    report = load_json(report_path, {"run_id": safe_run_id(run_id), "status": "cancelled", "steps": [], "artifacts": {}})
    previous_status = report.get("status")
    if previous_status not in TERMINAL_STATUSES or previous_status == "cancelled":
        report["status"] = "cancelled"
        report["error"] = "cancelled"
        report["cancelled"] = marker
        report["updated_at"] = marker["created_at"]
        report["completed_at"] = marker["created_at"]
        report.setdefault("steps", []).append(
            {
                "step_id": f"step_{uuid.uuid4().hex}",
                "type": "cancel_request",
                "status": "cancelled",
                "input": {},
                "output": marker,
                "error": marker["reason"],
                "created_at": marker["created_at"],
                "updated_at": marker["created_at"],
            }
        )
        save_json(report_path, report)
        write_lifecycle_event(output_root, run_id, report, "run_cancelled", status="cancelled", message=marker["reason"], data={"cancel": marker})
    return {"run_id": safe_run_id(run_id), "previous_status": previous_status, "status": report.get("status"), "cancel": marker, "run": report}


def next_child_run_id(source_run_id: str, action: str) -> str:
    return f"{safe_run_id(source_run_id)}_{action}_{uuid.uuid4().hex[:8]}"


def restart_request(source_run_id: str, original_request: dict[str, Any], *, action: str, new_run_id: str | None = None, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    request = deepcopy(original_request)
    request.update(overrides or {})
    request["run_id"] = new_run_id or next_child_run_id(source_run_id, action)
    request["parent_run_id"] = source_run_id
    if action == "retry":
        request["retry_of"] = source_run_id
    if action == "resume":
        request["resume_of"] = source_run_id
    return request


def retry_run(
    *,
    project_root: Path,
    output_root: Path,
    run_id: str,
    new_run_id: str | None = None,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    original = load_original_request(output_root, run_id)
    request = restart_request(run_id, original, action="retry", new_run_id=new_run_id, overrides=overrides)
    child_dir = run_dir(output_root, request["run_id"])
    run = run_agent_once(project_root, request, child_dir)
    return {"action": "retry", "source_run_id": safe_run_id(run_id), "new_run_id": request["run_id"], "run": run}


def resume_run(
    *,
    project_root: Path,
    output_root: Path,
    run_id: str,
    new_run_id: str | None = None,
    overrides: dict[str, Any] | None = None,
    allow_completed: bool = False,
) -> dict[str, Any]:
    report = load_run_report(output_root, run_id)
    if report.get("status") == "completed" and not allow_completed:
        raise ValueError("completed runs are not resumable without allow_completed=True")
    original = load_original_request(output_root, run_id)
    request = restart_request(run_id, original, action="resume", new_run_id=new_run_id, overrides=overrides)
    child_dir = run_dir(output_root, request["run_id"])
    run = run_agent_once(project_root, request, child_dir)
    return {"action": "resume", "source_run_id": safe_run_id(run_id), "new_run_id": request["run_id"], "source_status": report.get("status"), "run": run}


def parse_json_arg(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    return json.loads(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage file-backed Agent run lifecycle: status, cancel, retry and resume.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--output-root", default="outputs/agent_runtime/api")
    sub = parser.add_subparsers(dest="command", required=True)

    status_parser = sub.add_parser("status")
    status_parser.add_argument("--run-id", required=True)

    cancel_parser = sub.add_parser("cancel")
    cancel_parser.add_argument("--run-id", required=True)
    cancel_parser.add_argument("--reason", default=None)
    cancel_parser.add_argument("--requested-by", default=None)

    retry_parser = sub.add_parser("retry")
    retry_parser.add_argument("--run-id", required=True)
    retry_parser.add_argument("--new-run-id", default=None)
    retry_parser.add_argument("--overrides", default=None, help="JSON object merged into the original request.")

    resume_parser = sub.add_parser("resume")
    resume_parser.add_argument("--run-id", required=True)
    resume_parser.add_argument("--new-run-id", default=None)
    resume_parser.add_argument("--overrides", default=None, help="JSON object merged into the original request.")
    resume_parser.add_argument("--allow-completed", action="store_true")

    args = parser.parse_args()
    project_root = Path(args.project_root).resolve()
    output_root = Path(args.output_root)
    if args.command == "status":
        result = status_run(output_root, args.run_id)
    elif args.command == "cancel":
        result = cancel_run(output_root, args.run_id, reason=args.reason, requested_by=args.requested_by)
    elif args.command == "retry":
        result = retry_run(project_root=project_root, output_root=output_root, run_id=args.run_id, new_run_id=args.new_run_id, overrides=parse_json_arg(args.overrides))
    elif args.command == "resume":
        result = resume_run(project_root=project_root, output_root=output_root, run_id=args.run_id, new_run_id=args.new_run_id, overrides=parse_json_arg(args.overrides), allow_completed=bool(args.allow_completed))
    else:
        raise ValueError(f"unsupported command: {args.command}")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
