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
3. Hash files whose metadata changed.
4. Reuse prior extracted structure when the content hash is unchanged.
5. Re-index only added or content-modified files.
6. Remove deleted files and detect renames by matching content hashes.
7. Atomically commit the new index snapshot.

## Consistency

The SQLite index uses transactions. Generated Markdown and JSON files are written atomically after the database commit. A lock file prevents concurrent writers. Readers see the last completed snapshot.

A task context pack records its snapshot number and current Git state. Agents should rerun `context` after major edits or a branch switch.

## Scope

The index is structural and lexical. It records files, symbols, headings, imports, top search terms, modules, Git state, and source excerpts. It does not claim full semantic understanding. The agent uses the compact map to select original files for deeper reading.
