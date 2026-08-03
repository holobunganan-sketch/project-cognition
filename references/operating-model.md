# Operating model

## Ownership

Project files are authoritative. `.project-cognition` contains derived information.

Machine-owned paths:

- `START_HERE.md`
- `manifest.json`
- `generated/`
- `context-packs/`
- `cache/`

Human/agent-owned paths:

- `knowledge/decisions/`
- `knowledge/notes/`

A rebuild deletes and regenerates only machine-owned paths. It preserves `knowledge/`.

## Synchronization

Every `context` command calls the same preparation routine used by `prepare` before retrieval. Synchronization therefore occurs at the point of use.

Change detection follows this order:

1. Discover eligible files. Git repositories use `git ls-files --cached --others --exclude-standard`; other directories use a guarded filesystem walk.
2. Compare path, file size, and nanosecond modification time.
3. Force SHA-256 checks for paths reported by Git and paths changed between the indexed and current Git HEAD.
4. Run a full SHA-256 verification when requested or when the configurable periodic interval expires.
5. Reuse prior extracted structure when the content hash is unchanged.
6. Re-index only added or content-modified files.
7. Remove deleted files and detect renames by matching content hashes.
8. Atomically commit the new index snapshot and generated views.

The default full-hash verification interval is 24 hours. `--verify-hashes` requests an immediate complete check. `--hash-verify-interval-hours` changes the periodic interval.

## Retrieval and caching

Task retrieval combines lexical terms, paths, symbols, headings, imports, recent changes, entrypoint scores, and optional SQLite FTS5 candidate filtering. The selected lexical seeds are expanded with one-hop dependencies and importers unless `--no-related` is used.

A context pack is cached by:

- tool version
- cognition snapshot
- task text
- file and character limits
- dependency-expansion mode
- selected paths
- durable-knowledge content hash

A cache hit reuses the stable pack and updates `context-packs/current.md`.

## Consistency

The SQLite index uses transactions. Generated Markdown and JSON files are written atomically after the database commit. A lock file prevents concurrent writers. A lock older than the stale threshold is removed only when its recorded process is no longer alive or cannot be identified.

A task context pack records its snapshot number and current Git state. Agents should rerun `context` after major edits or a branch switch.

## Scope

The index is structural and lexical. It records files, symbols, headings, imports, top search terms, modules, Git state, and source excerpts. It does not claim complete semantic understanding. The agent uses the compact map to select original files for deeper reading.

`--exact-root` keeps a supplied package or subdirectory as the index root instead of ascending to the containing Git root. This supports independent package cognition inside monorepos.
