from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any


class AssetRepository:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def write_all(self, items: list[dict[str, Any]]) -> None:
        self.path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in items), encoding="utf-8")

    def create(self, item: dict[str, Any]) -> dict[str, Any]:
        record = {"asset_id": item.get("asset_id") or f"asset_{uuid.uuid4().hex}", "status": item.get("status") or "created", "media_type": item.get("media_type") or "unknown", "workspace_id": item.get("workspace_id") or "default", "url": item.get("url"), "local_path": item.get("local_path"), "source": item.get("source") or {}, "metadata": item.get("metadata") or {}}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record

    def set_status(self, asset_id: str, status: str) -> dict[str, Any] | None:
        items = self.read_all()
        found = None
        for item in items:
            if item.get("asset_id") == asset_id:
                item["status"] = status
                found = item
        if found:
            self.write_all(items)
        return found

    def list(self, *, workspace_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        items = self.read_all()
        if workspace_id:
            items = [item for item in items if item.get("workspace_id") == workspace_id]
        if status:
            items = [item for item in items if item.get("status") == status]
        return items
