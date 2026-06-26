# P1 MCP Adapter

The MCP adapter exposes foundation skills through an MCP-style JSON-RPC interface.

It is the protocol bridge between the foundation layer and future clients, agents, plugins and desktop tools.

Implemented files:

- `mcp/__init__.py`
- `mcp/adapter.py`
- `tests/test_mcp_adapter.py`

## What it exposes

The adapter maps active skills from:

```text
configs/skills/foundation_skills.json
```

into MCP-style tools.

It supports:

- `initialize`
- `ping`
- `server/info`
- `tools/list`
- `tools/call`
- `resources/list`
- `resources/read`
- `prompts/list`
- `prompts/get`
- `registry/validate`

## Tool mapping

A skill becomes an MCP tool with:

- `name` from skill id
- `description`
- `inputSchema`
- annotations for category, status, capabilities and permissions

## Permissions

Runtime flags:

- `--allow-provider`
- `--allow-write`
- `--approved`

Provider or write-capable skills are denied unless the adapter is started with the matching permissions.

## CLI usage

List tools:

```bash
python mcp/adapter.py --list-tools
```

Validate registry:

```bash
python mcp/adapter.py --validate
```

Call a safe tool:

```bash
python mcp/adapter.py \
  --call foundation.token_count \
  --args '{"request":{"input":[{"type":"text","text":"hello"}]},"expected_output_tokens":10}'
```

Run stdio JSON-RPC mode:

```bash
python mcp/adapter.py --stdio
```

## Resources

The adapter exposes a registry resource:

```text
foundation://skills/registry
```

## Prompts

The adapter exposes an initial prompt:

```text
foundation_task
```

## Audit log

Default audit log:

```text
outputs/mcp/foundation_mcp_adapter.jsonl
```

## Current limitations

- MCP-style implementation, not full official MCP SDK integration yet.
- No streaming progress or cancellation yet.
- No remote MCP server registry yet.
- No credential vault integration yet.
- No Agent tool loop integration yet.

## Next steps

- Integrate MCP adapter with Agent runtime tool loop.
- Add official MCP SDK compatibility layer.
- Add remote MCP server registry.
- Add credential isolation and approval policy binding.
- Connect adapter to `/v1/mcp/tools` in API server.
