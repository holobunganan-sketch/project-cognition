# Index schema

The local database is `.project-cognition/cache/index.sqlite3`.

## Tables

### `meta`

Key-value metadata including schema version, tool version, snapshot, project root, Git HEAD, branch, generation timestamps, last full-hash verification time, and FTS5 availability.

### `files`

One row per indexed file:

- relative path
- size and modification time
- SHA-256 content hash
- category and language
- line count
- top-level module
- extracted weighted search terms
- entrypoint score
- last indexed snapshot

### `symbols`

Extracted code declarations with file path, symbol kind, name, line, and signature.

### `headings`

Markdown, reStructuredText, AsciiDoc, and HTML heading records.

### `imports`

Language-specific import/include targets and line numbers.

### `changes`

Added, modified, deleted, and renamed paths for each snapshot.

### `file_search`

Optional SQLite FTS5 virtual table containing weighted path and file terms. It is created and backfilled automatically when the Python SQLite build supports FTS5. Retrieval uses the existing deterministic path when FTS5 is unavailable.

## Context-pack sidecars

Each cached context pack can have a JSON sidecar containing the selected files and cache-key inputs. Cache identity includes the project snapshot, task, limits, related-file mode, selected paths, and durable-knowledge digest.

## Generated files

`manifest.json` is a compact external status record. Markdown files under `generated/` are reproducible views over the database. They can be deleted and rebuilt.
