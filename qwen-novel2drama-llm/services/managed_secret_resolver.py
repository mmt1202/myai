from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ManagedSecretRef:
    provider: str
    name: str
    version: str | None = None
    region: str | None = None

    @classmethod
    def parse(cls, value: str) -> "ManagedSecretRef":
        # Format: provider://region/name#version or provider://name
        if "://" not in value:
            raise ValueError("managed secret ref must use provider://name")
        provider, rest = value.split("://", 1)
        version = None
        if "#" in rest:
            rest, version = rest.split("#", 1)
        region = None
        name = rest
        if "/" in rest:
            first, second = rest.split("/", 1)
            region, name = first, second
        if provider not in {"aws", "gcp", "azure", "vault", "env"}:
            raise ValueError(f"unsupported managed secret provider: {provider}")
        return cls(provider=provider, region=region, name=name, version=version)


def resolve_managed_secret(ref: str, *, env: dict[str, str] | None = None) -> dict[str, Any]:
    parsed = ManagedSecretRef.parse(ref)
    source = env if env is not None else os.environ
    if parsed.provider == "env":
        value = source.get(parsed.name)
        return {"status": "resolved" if value is not None else "missing", "provider": parsed.provider, "name": parsed.name, "value": value}
    return {"status": "external_provider_required", "provider": parsed.provider, "name": parsed.name, "region": parsed.region, "version": parsed.version, "value": None}


def managed_secret_health(refs: list[str]) -> dict[str, Any]:
    checks = []
    for ref in refs:
        try:
            result = resolve_managed_secret(ref)
            checks.append({"ref": ref, "status": result["status"], "provider": result["provider"]})
        except ValueError as exc:
            checks.append({"ref": ref, "status": "invalid", "error": str(exc)})
    failed = [item for item in checks if item["status"] == "invalid"]
    return {"status": "ok" if not failed else "failed", "checks": checks}
