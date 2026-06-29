from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def export_workspace_costs(summary: dict[str, Any], output_path: Path) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for workspace_id, item in (summary.get("workspaces") or {}).items():
        rows.append({"workspace_id": workspace_id, "input_tokens": item.get("input_tokens", 0), "output_tokens": item.get("output_tokens", 0), "cost": item.get("cost", 0.0), "records": item.get("records", 0)})
    if output_path.suffix.lower() == ".json":
        output_path.write_text(json.dumps({"rows": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    elif output_path.suffix.lower() == ".csv":
        with output_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["workspace_id", "input_tokens", "output_tokens", "cost", "records"])
            writer.writeheader()
            writer.writerows(rows)
    else:
        raise ValueError("output must be .json or .csv")
    return {"status": "ok", "path": str(output_path), "row_count": len(rows)}
