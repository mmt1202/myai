from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
from typing import Any, Callable


class SkillError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def skill_index(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {skill["id"]: skill for skill in registry.get("skills", [])}


def list_skills(registry: dict[str, Any], *, category: str | None = None, status: str | None = None, capability: str | None = None, include_planned: bool = False) -> list[dict[str, Any]]:
    skills = registry.get("skills", [])
    if not include_planned:
        skills = [skill for skill in skills if skill.get("status") == "active"]
    if category:
        skills = [skill for skill in skills if skill.get("category") == category]
    if status:
        skills = [skill for skill in skills if skill.get("status") == status]
    if capability:
        skills = [skill for skill in skills if capability in skill.get("capabilities", [])]
    return skills


def validate_registry(registry: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for index, skill in enumerate(registry.get("skills", [])):
        prefix = f"skills[{index}]"
        for field in ["id", "name", "category", "entrypoint", "status", "capabilities", "permissions", "description"]:
            if field not in skill:
                errors.append(f"{prefix}.{field} is required")
        skill_id = skill.get("id")
        if not isinstance(skill_id, str) or not skill_id:
            errors.append(f"{prefix}.id must be a non-empty string")
        elif skill_id in seen:
            errors.append(f"duplicate skill id: {skill_id}")
        else:
            seen.add(skill_id)
        if skill.get("status") not in {"active", "planned", "deprecated", "disabled"}:
            errors.append(f"{prefix}.status is invalid")
        if not isinstance(skill.get("capabilities"), list):
            errors.append(f"{prefix}.capabilities must be a list")
        if not isinstance(skill.get("permissions"), dict):
            errors.append(f"{prefix}.permissions must be an object")
    if not registry.get("skills"):
        errors.append("skills must be a non-empty list")
    return errors


def import_entrypoint(entrypoint: str) -> Callable[..., Any]:
    if ":" not in entrypoint:
        raise SkillError(f"invalid entrypoint: {entrypoint}")
    module_name, function_name = entrypoint.split(":", 1)
    module = importlib.import_module(module_name)
    function = getattr(module, function_name, None)
    if function is None or not callable(function):
        raise SkillError(f"entrypoint is not callable: {entrypoint}")
    return function


def check_permissions(skill: dict[str, Any], *, allow_provider: bool = False, allow_write: bool = False, approved: bool = False) -> None:
    permissions = skill.get("permissions") or {}
    if permissions.get("calls_provider") and not allow_provider:
        raise SkillError("skill requires provider access")
    if permissions.get("writes_files") and not allow_write:
        raise SkillError("skill requires file write access")
    if permissions.get("requires_approval") and not approved:
        raise SkillError("skill requires approval")


def call_skill(registry: dict[str, Any], skill_id: str, arguments: dict[str, Any], *, allow_provider: bool = False, allow_write: bool = False, approved: bool = False) -> dict[str, Any]:
    skills = skill_index(registry)
    if skill_id not in skills:
        raise SkillError(f"unknown skill: {skill_id}")
    skill = skills[skill_id]
    if skill.get("status") != "active":
        raise SkillError(f"skill is not active: {skill_id}")
    check_permissions(skill, allow_provider=allow_provider, allow_write=allow_write, approved=approved)
    function = import_entrypoint(skill["entrypoint"])
    result = function(**arguments) if arguments else function()
    return {"skill_id": skill_id, "status": "ok", "result": result}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default="configs/skills/foundation_skills.json")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--category", default=None)
    parser.add_argument("--status", default=None)
    parser.add_argument("--capability", default=None)
    parser.add_argument("--include-planned", action="store_true")
    args = parser.parse_args()
    registry = load_json(Path(args.registry))
    if args.validate:
        errors = validate_registry(registry)
        result = {"valid": not errors, "errors": errors}
    else:
        result = {"registry_name": registry.get("registry_name"), "skills": list_skills(registry, category=args.category, status=args.status, capability=args.capability, include_planned=args.include_planned)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result.get("errors") else 1


if __name__ == "__main__":
    raise SystemExit(main())
