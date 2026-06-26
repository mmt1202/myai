# P1 Skills Registry

Skills are reusable capability units owned by the foundation layer.

A skill can wrap:

- internal services
- provider calls
- MCP adapters
- tools
- future drama specialist workflows

Implemented files:

- `configs/skills/foundation_skills.json`
- `skills/__init__.py`
- `skills/registry.py`
- `tests/test_skill_registry.py`

## Skill metadata

Each skill contains:

- id
- name
- category
- entrypoint
- status
- capabilities
- input_schema
- output_schema
- permissions
- description

## Permissions

Current permission flags:

- `requires_approval`
- `writes_files`
- `calls_provider`
- `reads_memory`
- `writes_memory`

`call_skill` checks provider, write and approval permissions before importing and calling a skill entrypoint.

## List skills

```bash
python skills/registry.py --list
python skills/registry.py --category memory
python skills/registry.py --capability memory.retrieve
python skills/registry.py --include-planned --category drama_specialist
```

## Validate registry

```bash
python skills/registry.py --validate
```

## Active foundation skills

Initial active skills include:

- `foundation.token_count`
- `foundation.cost_estimate`
- `foundation.route_model`
- `foundation.memory_search`
- `foundation.memory_write`
- `foundation.rules_evaluate`
- `foundation.agent_run`
- `foundation.provider_generate`

## Planned specialist skills

Planned drama specialist skills:

- `drama.story_reasoning`
- `drama.visual_planning`

These are registered as future foundation capabilities, not application platform features.

## Current limitations

- No sandboxed execution yet.
- No remote skill package format yet.
- No versioned skill install/update flow yet.
- No MCP adapter mapping yet.
- Skill call argument validation is still lightweight.

## Next steps

- Add MCP adapter to expose skills as MCP tools.
- Add stricter JSON Schema validation for skill inputs.
- Add skill execution audit log.
- Add skill versioning and deprecation metadata.
- Connect skills registry to Agent tool loop.
