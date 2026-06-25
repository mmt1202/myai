from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

JSONRPC_VERSION = "2.0"
SERVER_NAME = "local-code-agent-mcp"
SERVER_VERSION = "0.1.0"

BOOLEAN_ARGS = {"dry_run", "safe_only", "execute_tests", "apply"}
SPECIAL_ARG_MAP = {
    "project_root": "--project-root",
    "output_dir": "--output-dir",
    "context_index": "--context-index",
    "patch_plan": "--patch-plan",
    "model_url": "--model-url",
    "model_mode": "--model-mode",
    "api_key_env": "--api-key-env",
    "chunk_chars": "--chunk-chars",
    "max_files": "--max-files",
    "file_limit": "--file-limit",
    "symbol_limit": "--symbol-limit",
    "allow_prefix": "--allow-prefix",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_jsonl(path: Path, item: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item, ensure_ascii=False) + "\n")


def kebab_arg(name: str) -> str:
    return SPECIAL_ARG_MAP.get(name, "--" + name.replace("_", "-"))


def load_profile(profiles: dict[str, Any], profile_id: str | None) -> dict[str, Any]:
    selected = profile_id or profiles.get("default_profile") or "planning"
    for profile in profiles.get("profiles", []):
        if profile.get("id") == selected:
            return profile
    raise ValueError(f"unknown permission profile: {selected}")


def registry_tools(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {tool["id"]: tool for tool in registry.get("tools", [])}


def tool_name_map(mcp_manifest: dict[str, Any], registry: dict[str, Any]) -> dict[str, str]:
    mapping = {tool["id"]: tool["id"] for tool in registry.get("tools", [])}
    for tool in mcp_manifest.get("tools", []):
        mapping[tool["name"]] = tool["registry_tool_id"]
    return mapping


def input_schema(tool: dict[str, Any]) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    for name in tool.get("inputs", []):
        if name in BOOLEAN_ARGS:
            properties[name] = {"type": "boolean"}
        elif name in {"timeout", "limit", "chunk", "chunk_chars", "max_files", "file_limit", "symbol_limit"}:
            properties[name] = {"type": "integer"}
        else:
            properties[name] = {"type": "string"}
    return {"type": "object", "properties": properties, "additionalProperties": True}


def public_tool(tool_name: str, tool: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": tool_name,
        "description": tool.get("description", ""),
        "inputSchema": input_schema(tool),
        "annotations": {
            "category": tool.get("category"),
            "safe_by_default": tool.get("safe_by_default"),
            "write_files": tool.get("write_files"),
            "requires_confirmation": tool.get("requires_confirmation", False),
        },
    }


def check_permission(tool: dict[str, Any], args: dict[str, Any], profile: dict[str, Any]) -> None:
    category = tool.get("category")
    allowed_categories = set(profile.get("allowed_categories", []))
    if category not in allowed_categories:
        raise PermissionError(f"category not allowed by profile {profile.get('id')}: {category}")
    if tool.get("write_files") and not profile.get("allow_write_tools"):
        raise PermissionError("profile does not allow write-capable tools")
    if tool.get("id") == "call_model_for_patch_spec" and not profile.get("allow_model_calls"):
        raise PermissionError("profile does not allow model API calls")
    if tool.get("id") == "apply_patch_spec" and args.get("confirm") == "APPLY" and not profile.get("allow_apply"):
        raise PermissionError("profile does not allow applying source changes")
    if tool.get("id") in {"run_test_plan", "ai_code_agent"}:
        will_execute = bool(args.get("execute_tests")) or args.get("dry_run") is False
        if will_execute and not profile.get("allow_execute_tests"):
            raise PermissionError("profile does not allow real test execution")
    if tool.get("id") == "ai_code_agent" and args.get("apply") and not profile.get("allow_apply"):
        raise PermissionError("profile does not allow applying source changes")


def command_for_tool(project_root: Path, tool: dict[str, Any], args: dict[str, Any]) -> list[str]:
    script = project_root / tool["script"]
    if not script.exists():
        raise FileNotFoundError(f"tool script does not exist: {tool['script']}")
    command = [sys.executable, str(script)]
    for key, value in args.items():
        if value is None:
            continue
        flag = kebab_arg(key)
        if isinstance(value, bool):
            if value:
                command.append(flag)
            continue
        if isinstance(value, list):
            for item in value:
                command.extend([flag, str(item)])
            continue
        command.extend([flag, str(value)])
    return command


def run_tool(project_root: Path, tool: dict[str, Any], args: dict[str, Any], timeout: int) -> dict[str, Any]:
    command = command_for_tool(project_root, tool, args)
    completed = subprocess.run(command, cwd=project_root, capture_output=True, text=True, timeout=timeout, check=False)
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "status": "passed" if completed.returncode == 0 else "failed",
    }


def audit(audit_log: Path | None, method: str, payload: dict[str, Any], result: dict[str, Any] | None = None, error: str | None = None) -> None:
    if not audit_log:
        return
    save_jsonl(
        audit_log,
        {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "method": method,
            "payload": payload,
            "result_status": result.get("status") if result else None,
            "error": error,
        },
    )


class ToolServer:
    def __init__(self, project_root: Path, registry_path: Path, mcp_manifest_path: Path, profiles_path: Path, profile_id: str | None, audit_log: Path | None, timeout: int) -> None:
        self.project_root = project_root
        self.registry = load_json(registry_path)
        self.mcp_manifest = load_json(mcp_manifest_path)
        self.profiles = load_json(profiles_path)
        self.profile = load_profile(self.profiles, profile_id)
        self.tools = registry_tools(self.registry)
        self.name_to_id = tool_name_map(self.mcp_manifest, self.registry)
        self.audit_log = audit_log
        self.timeout = timeout

    def list_tools(self) -> list[dict[str, Any]]:
        output = []
        for public_name, tool_id in sorted(self.name_to_id.items()):
            tool = self.tools.get(tool_id)
            if not tool:
                continue
            try:
                check_permission(tool, {}, self.profile)
            except PermissionError:
                continue
            output.append(public_tool(public_name, tool))
        return output

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        tool_id = self.name_to_id.get(name)
        if not tool_id or tool_id not in self.tools:
            raise KeyError(f"unknown tool: {name}")
        tool = dict(self.tools[tool_id])
        tool["id"] = tool_id
        check_permission(tool, arguments, self.profile)
        result = run_tool(self.project_root, tool, arguments, self.timeout)
        audit(self.audit_log, "tools/call", {"name": name, "arguments": arguments, "profile": self.profile.get("id")}, result=result)
        return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}], "structuredContent": result, "isError": result["returncode"] != 0}

    def handle(self, request: dict[str, Any]) -> dict[str, Any] | None:
        method = request.get("method")
        request_id = request.get("id")
        params = request.get("params") or {}
        try:
            if method == "initialize":
                result = {"protocolVersion": "2024-11-05", "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION}, "capabilities": {"tools": {}}}
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": self.list_tools()}
            elif method == "tools/call":
                result = self.call_tool(str(params.get("name")), params.get("arguments") or {})
            elif method == "registry/list":
                result = {"registry": self.registry, "profile": self.profile}
            elif method == "permissions/list":
                result = self.profiles
            elif method == "server/info":
                result = {"name": SERVER_NAME, "version": SERVER_VERSION, "profile": self.profile}
            else:
                raise NotImplementedError(f"unsupported method: {method}")
            audit(self.audit_log, method, params, result={"status": "passed"})
            if request_id is None:
                return None
            return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "result": result}
        except Exception as exc:  # noqa: BLE001
            audit(self.audit_log, str(method), params, error=str(exc))
            if request_id is None:
                return None
            return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "error": {"code": -32000, "message": str(exc)}}


def serve_stdio(server: ToolServer) -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        response = server.handle(json.loads(line))
        if response is not None:
            print(json.dumps(response, ensure_ascii=False), flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--registry", default="configs/tool_registry.json")
    parser.add_argument("--mcp-manifest", default="configs/mcp_manifest_code_agent.json")
    parser.add_argument("--profiles", default="configs/tool_permission_profiles.json")
    parser.add_argument("--profile", default=None)
    parser.add_argument("--audit-log", default="outputs/tool_logs/mcp_tool_server.jsonl")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--stdio", action="store_true")
    parser.add_argument("--list-tools", action="store_true")
    parser.add_argument("--call", default=None)
    parser.add_argument("--args", default="{}")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    audit_log = project_root / args.audit_log if args.audit_log else None
    server = ToolServer(
        project_root=project_root,
        registry_path=project_root / args.registry,
        mcp_manifest_path=project_root / args.mcp_manifest,
        profiles_path=project_root / args.profiles,
        profile_id=args.profile,
        audit_log=audit_log,
        timeout=args.timeout,
    )

    if args.stdio:
        return serve_stdio(server)
    if args.list_tools:
        print(json.dumps({"tools": server.list_tools()}, ensure_ascii=False, indent=2))
        return 0
    if args.call:
        result = server.call_tool(args.call, json.loads(args.args))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if not result.get("isError") else 1
    print(json.dumps({"server": SERVER_NAME, "version": SERVER_VERSION, "profile": server.profile, "tools": len(server.list_tools())}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
