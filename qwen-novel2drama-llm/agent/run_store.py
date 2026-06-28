from __future__ import annotations

import json
from abc import ABC, abstractmethod
from copy import deepcopy
from pathlib import Path
from typing import Any

from agent.events import read_agent_events, summarize_agent_events
from agent.runtime import CANCEL_REQUEST_FILENAME, now_iso, save_json

REQUEST_FILENAME = "agent_request.json"
REPORT_FILENAME = "agent_run_report.json"
EVENTS_FILENAME = "events.jsonl"
RUN_CREATED_FILENAME = "agent_run_created.json"


class RunStoreError(RuntimeError):
    pass


class RunNotFoundError(FileNotFoundError):
    def __init__(self, run_id: str) -> None:
        super().__init__(run_id)
        self.run_id = run_id


class RunStore(ABC):
    @abstractmethod
    def safe_run_id(self, run_id: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def run_dir(self, run_id: str) -> Path:
        raise NotImplementedError

    @abstractmethod
    def artifact_path(self, run_id: str, name: str) -> Path:
        raise NotImplementedError

    @abstractmethod
    def load_request(self, run_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def save_request(self, run_id: str, request: dict[str, Any]) -> Path:
        raise NotImplementedError

    @abstractmethod
    def load_report(self, run_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def save_report(self, run_id: str, report: dict[str, Any]) -> Path:
        raise NotImplementedError

    @abstractmethod
    def load_events(self, run_id: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def event_summary(self, run_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def load_cancel_request(self, run_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def save_cancel_request(self, run_id: str, marker: dict[str, Any]) -> Path:
        raise NotImplementedError

    @abstractmethod
    def cancel_requested(self, run_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def status(self, run_id: str) -> dict[str, Any]:
        raise NotImplementedError


class FileRunStore(RunStore):
    def __init__(self, output_root: Path) -> None:
        self.output_root = Path(output_root)

    def safe_run_id(self, run_id: str) -> str:
        value = str(run_id or "").strip()
        if not value or "/" in value or "\\" in value or ".." in value:
            raise ValueError(f"invalid run_id: {run_id}")
        return value

    def run_dir(self, run_id: str) -> Path:
        return self.output_root / self.safe_run_id(run_id)

    def artifact_path(self, run_id: str, name: str) -> Path:
        return self.run_dir(run_id) / name

    def load_json(self, path: Path, default: Any | None = None) -> Any:
        if not path.exists():
            if default is not None:
                return deepcopy(default)
            raise FileNotFoundError(str(path))
        return json.loads(path.read_text(encoding="utf-8"))

    def save_json(self, path: Path, data: dict[str, Any]) -> Path:
        save_json(path, data)
        return path

    def load_request(self, run_id: str) -> dict[str, Any]:
        return self.load_json(self.artifact_path(run_id, REQUEST_FILENAME))

    def save_request(self, run_id: str, request: dict[str, Any]) -> Path:
        return self.save_json(self.artifact_path(run_id, REQUEST_FILENAME), request)

    def load_report(self, run_id: str) -> dict[str, Any]:
        try:
            return self.load_json(self.artifact_path(run_id, REPORT_FILENAME))
        except FileNotFoundError as exc:
            raise RunNotFoundError(self.safe_run_id(run_id)) from exc

    def save_report(self, run_id: str, report: dict[str, Any]) -> Path:
        return self.save_json(self.artifact_path(run_id, REPORT_FILENAME), report)

    def load_created_run(self, run_id: str) -> dict[str, Any]:
        return self.load_json(self.artifact_path(run_id, RUN_CREATED_FILENAME))

    def save_created_run(self, run_id: str, run: dict[str, Any]) -> Path:
        return self.save_json(self.artifact_path(run_id, RUN_CREATED_FILENAME), run)

    def load_events(self, run_id: str) -> list[dict[str, Any]]:
        return read_agent_events(self.artifact_path(run_id, EVENTS_FILENAME))

    def event_summary(self, run_id: str) -> dict[str, Any]:
        return summarize_agent_events(self.load_events(run_id))

    def load_cancel_request(self, run_id: str) -> dict[str, Any] | None:
        path = self.artifact_path(run_id, CANCEL_REQUEST_FILENAME)
        if not path.exists():
            return None
        return self.load_json(path)

    def save_cancel_request(self, run_id: str, marker: dict[str, Any]) -> Path:
        return self.save_json(self.artifact_path(run_id, CANCEL_REQUEST_FILENAME), marker)

    def cancel_requested(self, run_id: str) -> bool:
        return self.artifact_path(run_id, CANCEL_REQUEST_FILENAME).exists()

    def status(self, run_id: str) -> dict[str, Any]:
        safe_id = self.safe_run_id(run_id)
        report = self.load_report(safe_id)
        return {
            "run_id": safe_id,
            "status": report.get("status"),
            "error": report.get("error"),
            "created_at": report.get("created_at"),
            "updated_at": report.get("updated_at"),
            "completed_at": report.get("completed_at"),
            "cancel_requested": self.cancel_requested(safe_id),
            "artifacts": report.get("artifacts") or {},
            "event_summary": self.event_summary(safe_id),
            "run_store": self.metadata(),
        }

    def metadata(self) -> dict[str, Any]:
        return {"type": "file", "output_root": str(self.output_root)}


def marker_for_cancel(run_id: str, *, reason: str | None = None, requested_by: str | None = None) -> dict[str, Any]:
    return {
        "created_at": now_iso(),
        "run_id": FileRunStore(Path(".")).safe_run_id(run_id),
        "reason": reason or "cancel_requested",
        "requested_by": requested_by,
    }


def file_run_store(output_root: Path) -> FileRunStore:
    return FileRunStore(output_root)
