# Index schema

The local database is `.project-cognition/cache/index.sqlite3`.

## Tables

### `meta`

Key-value metadata including schema version, snapshot, project root, Git HEAD, branch, and generation timestamps.

### `files`

One row per indexed file:

- relative path
- size and modification time
- SHA-256 content hash
- category and language
- line count
- top-level module
- text/binary eligibility
- extracted search terms
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

## Generated files

`manifest.json` is a compact external status record. Markdown files under `generated/` are reproducible views over the database. They can be deleted and rebuilt.
