# P1 Context management

P1 starts moving the project from a single text runtime toward a coding-agent capable foundation.

The first step is project-level context indexing, search, chunk reading and code-symbol indexing.

## Goal

Build a lightweight index of project files so later agents can:

- understand repository structure
- find relevant files
- track file hashes
- split long files into context chunks
- locate Python classes and functions
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

The output records file path, size, sha256, line count, character count, chunk size and chunk count.

## Search indexed files

```bash
python scripts/search_context_index.py --query api_server
python scripts/search_context_index.py --query model_version --limit 5
```

The search command uses the generated index to decide which files are in scope, then scans those files for matching lines.

## Read a chunk

```bash
python scripts/read_context_chunk.py --path inference/api_server.py --chunk 0
python scripts/read_context_chunk.py --path inference/api_server.py --chunk 1 --chunk-chars 2000
```

The chunk reader prevents reading files outside the project root and returns a JSON payload with chunk metadata and text.

## Build code symbols

```bash
python scripts/build_code_symbols.py
```

Custom output:

```bash
python scripts/build_code_symbols.py --output outputs/code_symbols.json
```

The code-symbol index records Python classes, functions, async functions and imports.

## Search code symbols

```bash
python scripts/search_code_symbols.py --query build
python scripts/search_code_symbols.py --query Runtime --type class
python scripts/search_code_symbols.py --query resolve --type function
```

## Next steps

- Add summary compression for large contexts.
- Add symbol-to-chunk mapping.
- Add vector/RAG backend later.
- Add CLI commands for coding-agent workflows.
