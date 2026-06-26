from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from skills.registry import SkillError, call_skill, list_skills, load_json, validate_registry

JSONRPC_VERSION = "2.0"
SERVER_NAME = "foundation-skills-mcp"
SERVER_VERSION = "0.1.0"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_jsonl(path: Path, item: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item, ensure_ascii=False) + "\n")


def audit(audit_log: Path | None, event: dict[str, Any]) -> None:
    if audit_log:
        save_jsonl(audit_log, {"created_at": now_iso(), **event})


def skill_to_mcp_tool(skill: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": skill["id"],
        "description": skill.get("description", ""),
        "inputSchema": skill.get("input_schema") or {"type": "object"},
        "annotations": {
            "title": skill.get("name"),
            "category": skill.get("category"),
            "status": skill.get("status"),
            "capabilities": skill.get("capabilities", []),
            "permissions": skill.get("permissions", {}),
        },
    }


def mcp_content(result: Any) -> list[dict[str, str]]:
    return [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]


class FoundationMCPAdapter:
    def __init__(self, registry_path: Path, audit_log: Path | None = None, allow_provider: bool = False, allow_write: bool = False, approved: bool = False) -> None:
        self.registry_path = registry_path
        self.registry = load_json(registry_path)
        self.audit_log = audit_log
        self.allow_provider = allow_provider
        self.allow_write = allow_write
        self.approved = approved

    def server_info(self) -> dict[str, Any]:
        return {
            "name": SERVER_NAME,
            "version": SERVER_VERSION,
            "registry": str(self.registry_path),
            "permissions": {
                "allow_provider": self.allow_provider,
                "allow_write": self.allow_write,
                "approved": self.approved,
            },
        }

    def list_tools(self, include_planned: bool = False) -> dict[str, Any]:
        skills = list_skills(self.registry, include_planned=include_planned)
        return {"tools": [skill_to_mcp_tool(skill) for skill in skills]}

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            result = call_skill(
                self.registry,
                name,
                arguments,
                allow_provider=self.allow_provider,
                allow_write=self.allow_write,
                approved=self.approved,
            )
            response = {"content": mcp_content(result), "structuredContent": result, "isError": False}
            audit(self.audit_log, {"method": "tools/call", "tool": name, "status": "ok"})
            return response
        except Exception as exc:  # noqa: BLE001
            error_result = {"skill_id": name, "status": "failed", "error": str(exc)}
            audit(self.audit_log, {"method": "tools/call", "tool": name, "status": "failed", "error": str(exc)})
            return {"content": mcp_content(error_result), "structuredContent": error_result, "isError": True}

    def list_resources(self) -> dict[str, Any]:
        return {
            "resources": [
                {
                    "uri": "foundation://skills/registry",
                    "name": "Foundation Skills Registry",
                    "mimeType": "application/json",
                    "description": "Current foundation skills registry metadata.",
                }
            ]
        }

    def read_resource(self, uri: str) -> dict[str, Any]:
        if uri != "foundation://skills/registry":
            raise SkillError(f"unknown resource: {uri}")
        return {"contents": [{"uri": uri, "mimeType": "application/json", "text": json.dumps(self.registry, ensure_ascii=False, indent=2)}]}

    def list_prompts(self) -> dict[str, Any]:
        return {
            "prompts": [
                {
                    "name": "foundation_task",
                    "description": "Prompt template for routing a task through foundation skills and model router.",
                    "arguments": [{"name": "task", "description": "Task to execute", "required": True}],
                }
            ]
        }

    def get_prompt(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name != "foundation_task":
            raise SkillError(f"unknown prompt: {name}")
        task = arguments.get("task") or ""
        return {
            "description": "Foundation task prompt",
            "messages": [
                {"role": "system", "content": {"type": "text", "text": "Use foundation routing, rules, memory, skills and provider adapters when needed."}},
                {"role": "user", "content": {"type": "text", "text": str(task)}},
            ],
        }

    def validate(self) -> dict[str, Any]:
        errors = validate_registry(self.registry)
        return {"valid": not errors, "errors": errors}

    def handle(self, request: dict[str, Any]) -> dict[str, Any] | None:
        request_id = request.get("id")
        method = request.get("method")
        params = request.get("params") or {}
        try:
            if method == "initialize":
                result = {"protocolVersion": "2024-11-05", "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION}, "capabilities": {"tools": {}, "resources": {}, "prompts": {}}}
            elif method == "ping":
                result = {}
            elif method == "server/info":
                result = self.server_info()
            elif method == "tools/list":
                result = self.list_tools(include_planned=bool(params.get("include_planned")))
            elif method == "tools/call":
                result = self.call_tool(str(params.get("name")), params.get("arguments") or {})
            elif method == "resources/list":
                result = self.list_resources()
            elif method == "resources/read":
                result = self.read_resource(str(params.get("uri")))
            elif method == "prompts/list":
                result = self.list_prompts()
            elif method == "prompts/get":
                result = self.get_prompt(str(params.get("name")), params.get("arguments") or {})
            elif method == "registry/validate":
                result = self.validate()
            else:
                raise SkillError(f"unsupported method: {method}")
            audit(self.audit_log, {"method": method, "status": "ok"})
            if request_id is None:
                return None
            return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "result": result}
        except Exception as exc:  # noqa: BLE001
            audit(self.audit_log, {"method": method, "status": "failed", "error": str(exc)})
            if request_id is None:
                return None
            return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "error": {"code": -32000, "message": str(exc)}}


def serve_stdio(adapter: FoundationMCPAdapter) -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        response = adapter.handle(json.loads(line))
        if response is not None:
            print(json.dumps(response, ensure_ascii=False), flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default="configs/skills/foundation_skills.json")
    parser.add_argument("--audit-log", default="outputs/mcp/foundation_mcp_adapter.jsonl")
    parser.add_argument("--allow-provider", action="store_true")
    parser.add_argument("--allow-write", action="store_true")
    parser.add_argument("--approved", action="store_true")
    parser.add_argument("--stdio", action="store_true")
    parser.add_argument("--list-tools", action="store_true")
    parser.add_argument("--include-planned", action="store_true")
    parser.add_argument("--call", default=None)
    parser.add_argument("--args", default="{}")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    adapter = FoundationMCPAdapter(
        registry_path=Path(args.registry),
        audit_log=Path(args.audit_log) if args.audit_log else None,
        allow_provider=args.allow_provider,
        allow_write=args.allow_write,
        approved=args.approved,
    )
    if args.stdio:
        return serve_stdio(adapter)
    if args.validate:
        result = adapter.validate()
    elif args.list_tools:
        result = adapter.list_tools(include_planned=args.include_planned)
    elif args.call:
        result = adapter.call_tool(args.call, json.loads(args.args))
    else:
        result = adapter.server_info()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result.get("isError") else 1


if __name__ == "__main__":
    raise SystemExit(main())
