from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class MCPSessionState:
    session_id: str
    role: str
    status: str = "initialized"
    protocol_version: str = "2025-06-18"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_mcp_tool(tool: dict[str, Any]) -> dict[str, Any]:
    name = tool.get("name") or tool.get("id")
    description = tool.get("description") or ""
    input_schema = tool.get("inputSchema") or tool.get("input_schema") or tool.get("schema") or {"type": "object", "properties": {}}
    return {"name": str(name), "description": str(description), "inputSchema": input_schema}


def foundation_tool_to_mcp(tool: dict[str, Any]) -> dict[str, Any]:
    schema = tool.get("parameters") or tool.get("input_schema") or {"type": "object", "properties": {}}
    return {"name": str(tool.get("name")), "description": str(tool.get("description") or ""), "inputSchema": schema}


def mcp_call_request(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"method": "tools/call", "params": {"name": name, "arguments": arguments or {}}}


def mcp_list_tools_request() -> dict[str, Any]:
    return {"method": "tools/list", "params": {}}


def mcp_initialize_request(*, client_name: str = "myai-foundation", protocol_version: str = "2025-06-18") -> dict[str, Any]:
    return {"method": "initialize", "params": {"protocolVersion": protocol_version, "clientInfo": {"name": client_name}}}


def transition_mcp_session(state: MCPSessionState, next_status: str) -> MCPSessionState:
    valid = {"initialized": {"ready", "closed", "failed"}, "ready": {"closed", "failed"}, "closed": set(), "failed": set()}
    if next_status not in valid.get(state.status, set()):
        raise ValueError(f"invalid MCP session transition: {state.status} -> {next_status}")
    return MCPSessionState(session_id=state.session_id, role=state.role, status=next_status, protocol_version=state.protocol_version)
