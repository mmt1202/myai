from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from agent.run_store import build_run_store
from agent.worker_dispatcher import DEFAULT_MAX_ATTEMPTS, dispatch_loop


def worker_pool_iteration(
    *,
    project_root: Path,
    output_root: Path,
    run_store: str = "file",
    sqlite_db: str | None = None,
    worker_prefix: str = "worker",
    worker_count: int = 1,
    max_runs_per_worker: int = 1,
    lease_seconds: int = 60,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> dict[str, Any]:
    workers = []
    total_processed = 0
    for index in range(max(1, int(worker_count))):
        worker_id = f"{worker_prefix}-{index + 1}"
        store = build_run_store(run_store, output_root, sqlite_path=sqlite_db)
        result = dispatch_loop(project_root=project_root, store=store, worker_id=worker_id, max_runs=max_runs_per_worker, lease_seconds=lease_seconds, max_attempts=max_attempts)
        total_processed += int(result.get("processed") or 0)
        workers.append(result)
    return {"status": "ok", "worker_count": max(1, int(worker_count)), "processed": total_processed, "workers": workers}


def worker_pool_loop(
    *,
    project_root: Path,
    output_root: Path,
    run_store: str = "file",
    sqlite_db: str | None = None,
    worker_prefix: str = "worker",
    worker_count: int = 1,
    max_runs_per_worker: int = 1,
    lease_seconds: int = 60,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    poll_seconds: float = 1.0,
    max_iterations: int | None = None,
    max_idle_iterations: int = 1,
) -> dict[str, Any]:
    iterations: list[dict[str, Any]] = []
    idle_count = 0
    index = 0
    while True:
        if max_iterations is not None and index >= max_iterations:
            break
        result = worker_pool_iteration(project_root=project_root, output_root=output_root, run_store=run_store, sqlite_db=sqlite_db, worker_prefix=worker_prefix, worker_count=worker_count, max_runs_per_worker=max_runs_per_worker, lease_seconds=lease_seconds, max_attempts=max_attempts)
        iterations.append(result)
        if int(result.get("processed") or 0) == 0:
            idle_count += 1
        else:
            idle_count = 0
        index += 1
        if idle_count >= max(1, int(max_idle_iterations)):
            break
        time.sleep(max(0.0, poll_seconds))
    return {"status": "ok", "iterations": iterations, "processed": sum(int(item.get("processed") or 0) for item in iterations), "idle_iterations": idle_count}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a small Agent worker pool over the internal dispatcher.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--output-root", default="outputs/agent_runtime/queue")
    parser.add_argument("--run-store", default="file")
    parser.add_argument("--sqlite-db", default=None)
    parser.add_argument("--worker-prefix", default="worker")
    parser.add_argument("--worker-count", type=int, default=1)
    parser.add_argument("--max-runs-per-worker", type=int, default=1)
    parser.add_argument("--lease-seconds", type=int, default=60)
    parser.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS)
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    parser.add_argument("--max-iterations", type=int, default=None)
    parser.add_argument("--max-idle-iterations", type=int, default=1)
    args = parser.parse_args()
    result = worker_pool_loop(project_root=Path(args.project_root), output_root=Path(args.output_root), run_store=args.run_store, sqlite_db=args.sqlite_db, worker_prefix=args.worker_prefix, worker_count=args.worker_count, max_runs_per_worker=args.max_runs_per_worker, lease_seconds=args.lease_seconds, max_attempts=args.max_attempts, poll_seconds=args.poll_seconds, max_iterations=args.max_iterations, max_idle_iterations=args.max_idle_iterations)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
