from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from agent.run_store import RunStore, build_run_store
from agent.runtime import now_iso, run_agent_once, save_json

DEFAULT_MAX_ATTEMPTS = 3


def queued_report(run_id: str, request: dict[str, Any]) -> dict[str, Any]:
    created_at = request.get("created_at") or now_iso()
    return {
        "run_id": run_id,
        "status": "queued",
        "task": request.get("task") or "",
        "owner_id": request.get("owner_id"),
        "project_id": request.get("project_id"),
        "workspace_id": request.get("workspace_id"),
        "parent_run_id": request.get("parent_run_id"),
        "route_mode": request.get("route_mode") or "balanced",
        "queue": {"status": "queued", "attempts": int(request.get("queue_attempts") or 0), "max_attempts": int(request.get("max_queue_attempts") or DEFAULT_MAX_ATTEMPTS), "created_at": created_at},
        "created_at": created_at,
        "updated_at": created_at,
        "artifacts": {},
    }


def enqueue_run(store: RunStore, request: dict[str, Any], *, run_id: str | None = None) -> dict[str, Any]:
    selected_run_id = store.safe_run_id(str(run_id or request.get("run_id") or f"queued_{now_iso().replace(':', '').replace('.', '')}"))
    queued_request = {**request, "run_id": selected_run_id, "queue_attempts": int(request.get("queue_attempts") or 0)}
    report = queued_report(selected_run_id, queued_request)
    store.save_request(selected_run_id, queued_request)
    store.save_report(selected_run_id, report)
    return {"status": "queued", "run_id": selected_run_id, "request": queued_request, "report": report, "run_store": store.metadata()}


def list_queue(store: RunStore, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
    return store.list_runs(status="queued", limit=limit, offset=offset, order="asc")


def dead_letter_report(run_id: str, request: dict[str, Any], *, reason: str) -> dict[str, Any]:
    current = now_iso()
    attempts = int(request.get("queue_attempts") or 0)
    return {
        "run_id": run_id,
        "status": "failed",
        "task": request.get("task") or "",
        "owner_id": request.get("owner_id"),
        "project_id": request.get("project_id"),
        "workspace_id": request.get("workspace_id"),
        "parent_run_id": request.get("parent_run_id"),
        "route_mode": request.get("route_mode") or "balanced",
        "error": reason,
        "queue": {"status": "dead_letter", "attempts": attempts, "max_attempts": int(request.get("max_queue_attempts") or DEFAULT_MAX_ATTEMPTS), "reason": reason, "updated_at": current},
        "updated_at": current,
        "completed_at": current,
        "artifacts": {},
    }


def dispatch_one(
    *,
    project_root: Path,
    store: RunStore,
    worker_id: str,
    lease_seconds: int = 60,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> dict[str, Any]:
    queue = list_queue(store, limit=1)
    if not queue.get("runs"):
        return {"status": "idle", "worker_id": worker_id, "processed": 0, "run_store": store.metadata()}
    run_id = str(queue["runs"][0]["run_id"])
    claim = store.claim_run(run_id, worker_id, lease_seconds=lease_seconds)
    if not claim.get("claimed"):
        return {"status": "busy", "worker_id": worker_id, "processed": 0, "run_id": run_id, "claim": claim, "run_store": store.metadata()}
    request = store.load_request(run_id)
    attempts = int(request.get("queue_attempts") or 0) + 1
    limit = int(request.get("max_queue_attempts") or max_attempts or DEFAULT_MAX_ATTEMPTS)
    request = {**request, "run_id": run_id, "queue_attempts": attempts, "max_queue_attempts": limit}
    store.save_request(run_id, request)
    if attempts > limit:
        report = dead_letter_report(run_id, request, reason="max_queue_attempts_exceeded")
        store.save_report(run_id, report)
        release = store.release_run(run_id, worker_id)
        return {"status": "dead_letter", "worker_id": worker_id, "processed": 1, "run_id": run_id, "attempts": attempts, "claim": claim, "release": release, "run_store": store.metadata()}
    try:
        run = run_agent_once(project_root, request, store.run_dir(run_id), store=store)
        release = store.release_run(run_id, worker_id)
        return {"status": "processed", "worker_id": worker_id, "processed": 1, "run_id": run_id, "attempts": attempts, "run": run, "claim": claim, "release": release, "run_store": store.metadata()}
    except Exception as exc:  # noqa: BLE001
        failure = dead_letter_report(run_id, request, reason=str(exc) or "dispatcher_run_failed")
        store.save_report(run_id, failure)
        release = store.release_run(run_id, worker_id)
        return {"status": "failed", "worker_id": worker_id, "processed": 1, "run_id": run_id, "attempts": attempts, "error": str(exc), "claim": claim, "release": release, "run_store": store.metadata()}


def dispatch_loop(
    *,
    project_root: Path,
    store: RunStore,
    worker_id: str,
    max_runs: int = 1,
    lease_seconds: int = 60,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for _ in range(max(1, int(max_runs))):
        result = dispatch_one(project_root=project_root, store=store, worker_id=worker_id, lease_seconds=lease_seconds, max_attempts=max_attempts)
        results.append(result)
        if result.get("status") in {"idle", "busy"}:
            break
    processed = sum(int(item.get("processed") or 0) for item in results)
    return {"status": "ok", "worker_id": worker_id, "processed": processed, "results": results, "run_store": store.metadata()}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Agent worker queue dispatcher.")
    parser.add_argument("command", choices=["enqueue", "list", "dispatch"])
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--output-root", default="outputs/agent_runtime/queue")
    parser.add_argument("--run-store", default="file")
    parser.add_argument("--sqlite-db", default=None)
    parser.add_argument("--worker-id", default="worker-local")
    parser.add_argument("--lease-seconds", type=int, default=60)
    parser.add_argument("--max-runs", type=int, default=1)
    parser.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS)
    parser.add_argument("--request", default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    store = build_run_store(args.run_store, Path(args.output_root), sqlite_path=args.sqlite_db)
    if args.command == "enqueue":
        if not args.request:
            raise SystemExit("--request is required for enqueue")
        result = enqueue_run(store, load_json(Path(args.request)), run_id=args.run_id)
    elif args.command == "list":
        result = list_queue(store)
    else:
        result = dispatch_loop(project_root=Path(args.project_root), store=store, worker_id=args.worker_id, max_runs=args.max_runs, lease_seconds=args.lease_seconds, max_attempts=args.max_attempts)
    if args.output:
        save_json(Path(args.output), result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
