"""Runtime registry helpers."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

IMPLEMENTED_STATUS = "implemented"
SUPPORTED_GENERATE_CAPABILITY = "text_generation"


class RuntimeRegistryError(ValueError):
    pass


class UnsupportedRuntimeError(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimeSpec:
    name: str
    family: str
    capability: str
    stage: str
    status: str
    model_path: str | None = None
    adapter_path: str | None = None
    system_prompt_file: str | None = None
    source_repo: str | None = None
    description: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RuntimeSpec":
        required = ["name", "family", "capability", "stage", "status"]
        missing = [key for key in required if not data.get(key)]
        if missing:
            raise RuntimeRegistryError(f"runtime entry is missing fields: {', '.join(missing)}")
        return cls(
            name=str(data["name"]),
            family=str(data["family"]),
            capability=str(data["capability"]),
            stage=str(data["stage"]),
            status=str(data["status"]),
            model_path=str(data["model_path"]) if data.get("model_path") else None,
            adapter_path=str(data["adapter_path"]) if data.get("adapter_path") else None,
            system_prompt_file=str(data["system_prompt_file"]) if data.get("system_prompt_file") else None,
            source_repo=str(data["source_repo"]) if data.get("source_repo") else None,
            description=str(data.get("description", "")),
        )

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "family": self.family,
            "capability": self.capability,
            "stage": self.stage,
            "status": self.status,
            "model_path": self.model_path,
            "adapter_path": self.adapter_path,
            "system_prompt_file": self.system_prompt_file,
            "source_repo": self.source_repo,
            "description": self.description,
        }


@dataclass(frozen=True)
class RuntimeRegistry:
    default_runtime: str
    runtimes: dict[str, RuntimeSpec]

    def list_runtimes(self, capability: str | None = None, status: str | None = None) -> list[RuntimeSpec]:
        rows = list(self.runtimes.values())
        if capability:
            rows = [row for row in rows if row.capability == capability]
        if status:
            rows = [row for row in rows if row.status == status]
        return rows

    def resolve(self, name: str | None = None) -> RuntimeSpec:
        runtime_name = name or self.default_runtime
        if runtime_name not in self.runtimes:
            available = ", ".join(sorted(self.runtimes))
            raise RuntimeRegistryError(f"unknown runtime: {runtime_name}; available: {available}")
        return self.runtimes[runtime_name]


def load_runtime_registry(path: str | Path) -> RuntimeRegistry:
    registry_path = Path(path)
    if not registry_path.exists():
        raise FileNotFoundError(f"runtime registry does not exist: {registry_path}")
    raw = json.loads(registry_path.read_text(encoding="utf-8"))
    default_runtime = str(raw.get("default_runtime", "")).strip()
    raw_runtimes = raw.get("runtimes", [])
    if not default_runtime:
        raise RuntimeRegistryError("runtime registry requires default_runtime")
    if not isinstance(raw_runtimes, list) or not raw_runtimes:
        raise RuntimeRegistryError("runtime registry requires a non-empty runtimes list")
    runtimes = {spec.name: spec for spec in (RuntimeSpec.from_dict(item) for item in raw_runtimes)}
    if default_runtime not in runtimes:
        raise RuntimeRegistryError(f"default runtime does not exist: {default_runtime}")
    return RuntimeRegistry(default_runtime=default_runtime, runtimes=runtimes)


def ensure_text_generation_runtime(spec: RuntimeSpec) -> None:
    if spec.status != IMPLEMENTED_STATUS:
        raise UnsupportedRuntimeError(f"runtime {spec.name} status is {spec.status}, not implemented")
    if spec.capability != SUPPORTED_GENERATE_CAPABILITY:
        raise UnsupportedRuntimeError(
            f"runtime {spec.name} capability is {spec.capability}; only {SUPPORTED_GENERATE_CAPABILITY} is supported"
        )
    if not spec.model_path:
        raise RuntimeRegistryError(f"runtime {spec.name} requires model_path")
