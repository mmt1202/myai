# P2 MCP-style tool server

`mcp_tool_server.py` exposes the local code-agent foundation through a JSON-RPC style tool interface.

It includes:

- tool discovery
- tool invocation
- permission profiles
- command argument mapping
- audit logs
- stdio mode
- direct CLI mode

## Permission profiles

Profiles are defined in:

```text
configs/tool_permission_profiles.json
```

Available profiles:

- `readonly`
- `planning`
- `model_patch`
- `trusted_apply`

Default profile is `planning`.

## List tools

```bash
python scripts/mcp_tool_server.py --list-tools
python scripts/mcp_tool_server.py --profile readonly --list-tools
```

## Call a tool

```bash
python scripts/mcp_tool_server.py --call context.search --args '{"query":"api_server","index":"outputs/context_index.json"}'
```

## Stdio mode

```bash
python scripts/mcp_tool_server.py --stdio
```

Supported methods:

- `initialize`
- `ping`
- `tools/list`
- `tools/call`
- `registry/list`
- `permissions/list`
- `server/info`

## Audit log

Default audit log:

```text
outputs/tool_logs/mcp_tool_server.jsonl
```

## Safety behavior

The server enforces profile-based permissions:

- readonly cannot call write-capable tools
- model calls require `model_patch` or `trusted_apply`
- confirmed patch apply requires `trusted_apply`
- real test execution requires `trusted_apply`
- all tools run from the configured project root

This is a local MCP-style server wrapper around the project tool registry. It follows JSON-RPC conventions and MCP-style `tools/list` and `tools/call` surfaces while keeping local safety controls explicit.
