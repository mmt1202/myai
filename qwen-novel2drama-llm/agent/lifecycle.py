from __future__ import annotations

import argparse
import json
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any

from agent.events import AgentEventWriter
from agent.run_store import FileRunStore, RunNotFoundError, RunStore, file_run_store, marker_for_cancel, run_store_from_config
from agent.runtime import run_agent_once, now_iso

TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
RESTARTABLE_STATUSES = {"failed", "cancelled", "waiting_approval", "waiting_tool"}


def safe_run_id(value: str) -> str:
    return FileRunStore(Path(".")).safe_run_id(value)


def run_dir(output_root: Path, run_id: str) -> Path:
    return file_run_store(output_root).run_dir(run_id)


def load_json(path: Path, default: Any | None = None) -> Any:
    return FileRunStore(path.parent).load_json(path, default)


def run_report_path(output_root: Path, run_id: str) -> Path:
    return file_run_store(output_root).artifact_path(run_id, "agent_run_report.json")


def load_run_report(output_root: Path, run_id: str) -> dict[str, Any]:
    return file_run_store(output_root).load_report(run_id)


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


def load_original_request(output_root: Path, run_id: str, store: RunStore | None = None) -> dict[str, Any]:
    active_store = store or file_run_store(output_root)
    try:
        return active_store.load_request(run_id)
    except FileNotFoundError:
        return original_request_from_report(active_store.load_report(run_id))


def status_run(output_root: Path, run_id: str, store: RunStore | None = None) -> dict[str, Any]:
    active_store = store or file_run_store(output_root)
    return active_store.status(run_id)


def write_lifecycle_event(output_root: Path, run_id: str, report: dict[str, Any], event_type: str, *, status: str, message: str | None = None, data: dict[str, Any] | None = None, error: str | None = None, store: RunStore | None = None) -> None:
    active_store = store or file_run_store(output_root)
    event = {
        **{
            "run_id": report.get("run_id"),
            "session_id": report.get("session_id"),
            "owner_id": report.get("owner_id"),
            "project_id": report.get("project_id"),
        },
        "event_type": event_type,
        "status": status,
        "message": message,
        "data": data or {},
        "error": error,
    }
    if hasattr(active_store, "append_event"):
        getattr(active_store, "append_event")(run_id, event)
        return
    writer = AgentEventWriter(active_store.artifact_path(run_id, "events.jsonl"), report, enabled=True)
    writer.emit(event_type, status=status, message=message, data=data or {}, error=error)


def cancel_run(output_root: Path, run_id: str, *, reason: str | None = None, requested_by: str | None = None, store: RunStore | None = None) -> dict[str, Any]:
    active_store = store or file_run_store(output_root)
    safe_id = active_store.safe_run_id(run_id)
    directory = active_store.run_dir(safe_id)
    if active_store.metadata().get("type") == "file":
        directory.mkdir(parents=True, exist_ok=True)
    marker = marker_for_cancel(safe_id, reason=reason, requested_by=requested_by)
    active_store.save_cancel_request(safe_id, marker)
    try:
        report = active_store.load_report(safe_id)
    except RunNotFoundError:
        report = {"run_id": safe_id, "status": "cancelled", "steps": [], "artifacts": {}}
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
        active_store.save_report(safe_id, report)
        write_lifecycle_event(output_root, safe_id, report, "run_cancelled", status="cancelled", message=marker["reason"], data={"cancel": marker}, store=active_store)
    return {"run_id": safe_id, "previous_status": previous_status, "status": report.get("status"), "cancel": marker, "run": report, "run_store": active_store.metadata()}


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
    store: RunStore | None = None,
) -> dict[str, Any]:
    active_store = store or file_run_store(output_root)
    safe_id = active_store.safe_run_id(run_id)
    original = load_original_request(output_root, safe_id, active_store)
    request = restart_request(safe_id, original, action="retry", new_run_id=new_run_id, overrides=overrides)
    child_dir = active_store.run_dir(request["run_id"])
    run = run_agent_once(project_root, request, child_dir)
    if active_store.metadata().get("type") != "file":
        active_store.save_request(request["run_id"], request)
        active_store.save_report(request["run_id"], run)
    return {"action": "retry", "source_run_id": safe_id, "new_run_id": request["run_id"], "run": run, "run_store": active_store.metadata()}


def resume_run(
    *,
    project_root: Path,
    output_root: Path,
    run_id: str,
    new_run_id: str | None = None,
    overrides: dict[str, Any] | None = None,
    allow_completed: bool = False,
    store: RunStore | None = None,
) -> dict[str, Any]:
    active_store = store or file_run_store(output_root)
    safe_id = active_store.safe_run_id(run_id)
    report = active_store.load_report(safe_id)
    if report.get("status") == "completed" and not allow_completed:
        raise ValueError("completed runs are not resumable without allow_completed=True")
    original = load_original_request(output_root, safe_id, active_store)
    request = restart_request(safe_id, original, action="resume", new_run_id=new_run_id, overrides=overrides)
    child_dir = active_store.run_dir(request["run_id"])
    run = run_agent_once(project_root, request, child_dir)
    if active_store.metadata().get("type") != "file":
        active_store.save_request(request["run_id"], request)
        active_store.save_report(request["run_id"], run)
    return {"action": "resume", "source_run_id": safe_id, "new_run_id": request["run_id"], "source_status": report.get("status"), "run": run, "run_store": active_store.metadata()}


def parse_json_arg(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    return json.loads(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage Agent run lifecycle through the configured run store: status, cancel, retry and resume.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--output-root", default="outputs/agent_runtime/api")
    parser.add_argument("--run-store", choices=["file", "sqlite"], default="file")
    parser.add_argument("--sqlite-path", default=None)
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
    store = run_store_from_config(store_type=args.run_store, output_root=output_root, sqlite_path=Path(args.sqlite_path) if args.sqlite_path else None)
    if args.command == "status":
        result = status_run(output_root, args.run_id, store)
    elif args.command == "cancel":
        result = cancel_run(output_root, args.run_id, reason=args.reason, requested_by=args.requested_by, store=store)
    elif args.command == "retry":
        result = retry_run(project_root=project_root, output_root=output_root, run_id=args.run_id, new_run_id=args.new_run_id, overrides=parse_json_arg(args.overrides), store=store)
    elif args.command == "resume":
        result = resume_run(project_root=project_root, output_root=output_root, run_id=args.run_id, new_run_id=args.new_run_id, overrides=parse_json_arg(args.overrides), allow_completed=bool(args.allow_completed), store=store)
    else:
        raise ValueError(f"unsupported command: {args.command}")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
