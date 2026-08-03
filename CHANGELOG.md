# Changelog

## 1.1.0 — 2026-08-03

- Added Git-status and Git-HEAD-aware hash verification so content changes are detected even when size and modification time are preserved.
- Added configurable periodic full-hash verification, plus explicit `--verify-hashes` controls.
- Added optional SQLite FTS5 candidate filtering with automatic fallback when FTS5 is unavailable.
- Added one-hop dependency and importer expansion for task context packs.
- Added stable context-pack caching keyed by snapshot, task, limits, selected paths, and durable-note content.
- Added `--exact-root` for package-level indexing inside monorepos.
- Added known provider-token redaction and durable-note excerpt redaction.
- Improved stale-lock handling by checking whether the recorded process is still alive.
- Prevented large initial snapshots from polluting task retrieval with every newly indexed file.
- Excluded bytecode, backup files, and cache directories from release archives, and added version-consistency checks.
- Accepted `--compact-json` both before and after the subcommand for easier CLI use.
- Expanded automated coverage from 5 to 12 tests.

## 1.0.0 — 2026-08-03

- Added deterministic project discovery with Git-aware ignore handling.
- Added incremental path, metadata, SHA-256, symbol, heading, and import indexing.
- Added rename detection and bounded change history.
- Added persistent SQLite snapshots and atomic generated views.
- Added task-specific hybrid retrieval and source excerpts.
- Added status, validation, deep validation, rebuild, and AGENTS.md entry commands.
- Added secret-bearing path exclusions, sensitive assignment redaction, and no-network operation.
- Added cross-platform standard-library implementation and automated tests.
