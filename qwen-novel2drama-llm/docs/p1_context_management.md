# P1 Context management

P1 starts moving the project from a single text runtime toward a coding-agent capable foundation.

The first step is project-level context indexing.

## Goal

Build a lightweight index of project files so later agents can:

- understand repository structure
- find relevant files
- track file hashes
- split long files into context chunks
- support future RAG, code editing, patch planning and CLI workflows

## Profile

Default profile:

```text
configs/context_profile.json
```

It includes docs, configs, scripts, inference code, eval code, tests and prompts.

It excludes local artifacts such as:

```text
models/
saves/
outputs/
logs/
raw_novels/
```

## Build index

```bash
python scripts/build_context_index.py
```

Custom output:

```bash
python scripts/build_context_index.py --output outputs/context_index.json
```

The output records:

- file path
- byte size
- sha256
- line count
- character count
- chunk size
- chunk count

## Next steps

- Add keyword search over the context index.
- Add file chunk extraction by path and chunk id.
- Add code-symbol indexing.
- Add vector/RAG backend later.
- Add CLI commands for coding-agent workflows.
