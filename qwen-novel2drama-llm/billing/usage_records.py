from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ProviderUsageRecord:
    provider: str
    record_id: str
    workspace_id: str
    usage_date: str
    model: str
    input_tokens: int
    output_tokens: int
    cost: float
    currency: str = "USD"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_usage_record(raw: dict[str, Any], *, provider: str = "generic") -> ProviderUsageRecord:
    return ProviderUsageRecord(
        provider=str(raw.get("provider") or provider),
        record_id=str(raw.get("record_id") or raw.get("invoice_id") or raw.get("id") or "unknown"),
        workspace_id=str(raw.get("workspace_id") or raw.get("workspace") or "default"),
        usage_date=str(raw.get("usage_date") or raw.get("date") or "unknown"),
        model=str(raw.get("model") or raw.get("model_id") or "unknown"),
        input_tokens=int(float(raw.get("input_tokens") or raw.get("prompt_tokens") or 0)),
        output_tokens=int(float(raw.get("output_tokens") or raw.get("completion_tokens") or 0)),
        cost=float(raw.get("cost") or raw.get("amount") or 0.0),
        currency=str(raw.get("currency") or "USD"),
    )


def load_usage_json(path: Path, *, provider: str = "generic") -> list[ProviderUsageRecord]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    items = raw.get("items") if isinstance(raw, dict) else raw
    return [normalize_usage_record(item, provider=provider) for item in items]


def load_usage_csv(path: Path, *, provider: str = "generic") -> list[ProviderUsageRecord]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [normalize_usage_record(row, provider=provider) for row in csv.DictReader(handle)]


def load_usage_records(path: Path, *, provider: str = "generic") -> list[ProviderUsageRecord]:
    if path.suffix.lower() == ".json":
        return load_usage_json(path, provider=provider)
    if path.suffix.lower() == ".csv":
        return load_usage_csv(path, provider=provider)
    raise ValueError(f"unsupported usage record file type: {path.suffix}")
