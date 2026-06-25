# P2 Tool schema, Skill and MCP preparation

This layer turns existing coding-agent scripts into a structured tool surface.

It prepares the project for future integrations such as:

- local desktop coding client
- CLI agent
- Skill system
- plugin system
- MCP server

## Tool registry

Main registry:

```text
configs/tool_registry.json
```

Inspect tools:

```bash
python scripts/inspect_tool_registry.py
python scripts/inspect_tool_registry.py --category context
python scripts/inspect_tool_registry.py --safe-only
```

Validate registry:

```bash
python scripts/validate_tool_registry.py
```

## Skill manifest

Skill manifest:

```text
configs/skill_manifest_code_agent.json
```

It describes the local code-agent foundation as a future reusable Skill.

## MCP manifest

MCP manifest draft:

```text
configs/mcp_manifest_code_agent.json
```

This is only a manifest. It does not implement an MCP server yet.

## Safety policy

The tool layer keeps the same safety defaults:

- dry-run by default
- project-root-only file access
- explicit confirmation before writing source files
- test command allowlist
- no model weight edits
- model output must become validated patch specs before apply

## Next steps

- Implement a small local MCP server wrapper.
- Add tool invocation logs.
- Add permission profiles for desktop and CLI clients.
- Add AI drama/comic production tools after the foundation is stable.
