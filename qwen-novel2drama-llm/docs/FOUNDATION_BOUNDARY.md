# Foundation Boundary

This document defines what MyAI Foundation owns and what should be left for the future ForgePilot layer.

## Foundation owns

MyAI Foundation is the model/runtime service layer. It owns:

- model version registry
- model instance registry
- model routing
- local and external provider generation contracts
- token and cost estimation
- memory read/write contracts
- skills registry and skill execution permissions
- MCP-style server adapter exposing Foundation capabilities
- lightweight Agent runtime orchestration
- run store and event store
- auth, rate limit, quota and audit contracts
- drama pipeline capabilities: novel parsing, outline, character system, storyboard, video prompt package, media generation job adapters

## ForgePilot owns later

ForgePilot is the future coding/desktop/CLI automation layer. It should own:

- real repository reading and indexing workflows
- file edits and patch application
- terminal command execution
- Git diff, branch, commit and checkpoint workflows
- sandbox execution
- desktop UI and local agent UX
- multi-project workspace orchestration
- external MCP host responsibilities
- coding task planning and implementation loops

## Do not duplicate in Foundation

Foundation should not become a Codex-like code editing agent. Avoid adding these capabilities to Foundation:

- direct arbitrary file modification outside approved artifact outputs
- unrestricted shell command execution
- Git patch/checkpoint management
- IDE/desktop control
- long-running project coding loops

## Integration boundary

ForgePilot should call Foundation through stable APIs:

- `/v1/route`
- `/v1/chat`
- `/v1/reason`
- `/v1/agent/run`
- `/v1/skills/*`
- `/v1/mcp/*`
- `/v1/drama/*`

Foundation returns model decisions, generation results, skills outputs, agent reports and drama assets. ForgePilot decides how to apply those outputs to code, files, terminal and Git.
