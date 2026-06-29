from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


class SecretResolutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class SecretReference:
    source: str
    name: str
    configured: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_secret_reference(value: str | None) -> SecretReference:
    raw = (value or "").strip()
    if not raw:
        return SecretReference(source="missing", name="", configured=False)
    if raw.startswith("env:"):
        name = raw.removeprefix("env:").strip()
        return SecretReference(source="env", name=name, configured=bool(name and os.environ.get(name)))
    if raw.startswith("file:"):
        name = raw.removeprefix("file:").strip()
        return SecretReference(source="file", name=name, configured=bool(name and Path(name).exists()))
    if raw.startswith("literal:"):
        name = raw.removeprefix("literal:").strip()
        return SecretReference(source="literal", name="<literal>", configured=bool(name))
    return SecretReference(source="raw", name="<raw>", configured=True)


def resolve_secret(value: str | None, *, allow_raw: bool = False) -> str:
    raw = (value or "").strip()
    ref = parse_secret_reference(raw)
    if ref.source == "missing":
        raise SecretResolutionError("secret reference is missing")
    if ref.source == "env":
        resolved = os.environ.get(ref.name)
        if not resolved:
            raise SecretResolutionError(f"secret env is not configured: {ref.name}")
        return resolved
    if ref.source == "file":
        path = Path(ref.name)
        if not path.exists():
            raise SecretResolutionError(f"secret file does not exist: {ref.name}")
        return path.read_text(encoding="utf-8").strip()
    if ref.source == "literal":
        return raw.removeprefix("literal:")
    if allow_raw:
        return raw
    raise SecretResolutionError("raw secret values are disabled; use env:NAME or file:/path")


def secret_health(references: dict[str, str | None]) -> dict[str, Any]:
    items = {name: parse_secret_reference(value).to_dict() for name, value in references.items()}
    missing = [name for name, item in items.items() if not item["configured"]]
    unsafe_raw = [name for name, item in items.items() if item["source"] == "raw"]
    return {"status": "ok" if not missing and not unsafe_raw else "degraded", "items": items, "missing": missing, "unsafe_raw": unsafe_raw}
