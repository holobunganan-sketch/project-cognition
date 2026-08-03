# Project Cognition

[简体中文](README.zh-CN.md) | English

A standalone Codex skill that builds a persistent, source-linked, incrementally refreshed understanding of a project directory. It reuses previous indexing, detects changed files, and generates compact task-specific context packs so agents can begin project work with less repeated scanning and fewer input tokens.

## Highlights in v1.1.0

- Detects Git-reported changes even when file size and modification time were preserved.
- Runs a configurable periodic full SHA-256 verification and supports an explicit `--verify-hashes` check.
- Uses SQLite FTS5 to narrow retrieval candidates when available, with a deterministic fallback on standard SQLite builds.
- Expands task context with direct dependencies and importers, including relevant tests and callers.
- Reuses stable context packs when the task, project snapshot, limits, selected paths, and durable notes are unchanged.
- Supports package-level indexing inside monorepos through `--exact-root`.
- Redacts common provider tokens and sensitive assignment lines from generated excerpts.

## Core capabilities

- Builds a reusable structural index for a project directory.
- Detects additions, modifications, deletions, and renames incrementally.
- Records paths, metadata, SHA-256 hashes, symbols, headings, imports, modules, and entrypoint candidates.
- Generates human-readable project maps and task-specific context packs.
- Revalidates project state before context retrieval.
- Preserves manually maintained project knowledge across rebuilds.
- Excludes common dependency, build, binary, credential, and secret-bearing paths.
- Runs with the Python standard library and no network access.

## Synchronization model

Project files remain the source of truth. The generated cognition layer is a rebuildable cache.

Every `prepare` or `context` invocation performs the following sequence:

1. Discover eligible files through Git when available or a guarded filesystem walk.
2. Compare paths, file size, and nanosecond modification time with the previous snapshot.
3. Force hash checks for paths reported by Git and files changed between the indexed and current Git HEAD.
4. Run a full hash verification when requested or when the periodic verification interval expires.
5. Re-index only added or content-modified files and remove deleted entries.
6. Detect renames by matching deleted and added content hashes.
7. Refresh the SQLite snapshot and generated views atomically.
8. Build or reuse a context pack only after synchronization completes.

The default full-hash interval is 24 hours. Git projects remain responsive between full checks because Git-reported paths are always hashed. Use `--verify-hashes` for an immediate complete verification.

No persistent background service is required. Run `prepare` once after a coherent edit batch to provide read-after-write consistency.

## Installation

### Download a release

Download `project-cognition-skill-vX.Y.Z.zip` from the [Releases](../../releases) page and extract it so the final path is:

```text
~/.agents/skills/project-cognition/SKILL.md
```

On Windows:

```text
%USERPROFILE%\.agents\skills\project-cognition\SKILL.md
```

The release also includes a skills-only plugin package.

### Repository-local installation

Copy the `project-cognition` directory to:

```text
<repository>/.agents/skills/project-cognition/SKILL.md
```

### Install from source

```bash
git clone https://github.com/holobunganan-sketch/project-cognition.git
mkdir -p ~/.agents/skills
cp -R project-cognition ~/.agents/skills/project-cognition
```

Restart Codex when the skill does not appear immediately.

## Usage

Explicit invocation:

```text
$project-cognition Build or refresh project cognition, then explain this repository's architecture.
```

The skill description also supports implicit invocation for repository-wide analysis, debugging, multi-file editing, architecture review, and onboarding.

## Commands

```bash
python scripts/project_cognition.py prepare --project .
python scripts/project_cognition.py context --project . --task "your task"
python scripts/project_cognition.py status --project .
python scripts/project_cognition.py validate --project .
python scripts/project_cognition.py validate --project . --deep
python scripts/project_cognition.py rebuild --project .
```

Force a complete hash verification:

```bash
python scripts/project_cognition.py prepare --project . --verify-hashes
```

Index only a package or subproject inside a Git monorepo:

```bash
python scripts/project_cognition.py context \
  --project ./packages/example \
  --exact-root \
  --task "trace the package initialization flow"
```

Disable one-hop dependency expansion for a strictly lexical context pack:

```bash
python scripts/project_cognition.py context \
  --project . \
  --task "find configuration references" \
  --no-related
```

Optional project-level activation entry:

```bash
python scripts/project_cognition.py install-entry --project .
python scripts/project_cognition.py remove-entry --project .
```

Use `--help` for complete options.

## Generated project data

The skill creates `.project-cognition/` in the indexed project:

```text
.project-cognition/
├── START_HERE.md
├── manifest.json
├── generated/
│   ├── architecture.md
│   ├── current-state.md
│   ├── file-map.md
│   └── modules/
├── knowledge/
│   ├── README.md
│   ├── decisions/
│   └── notes/
├── context-packs/
└── cache/
    └── index.sqlite3
```

Machine-maintained data can remain local by adding `.project-cognition/` to `.gitignore`. The `knowledge/` directory is preserved across rebuilds and can be shared intentionally when a team wants durable project knowledge.

## Retrieval behavior

Task retrieval combines:

- exact filename and path matches;
- weighted indexed terms;
- symbols and document headings;
- import/include targets;
- optional SQLite FTS5 candidate filtering;
- latest-snapshot changes;
- entrypoint scores;
- one-hop dependency and importer expansion.

Context packs are cached by project snapshot, task, limits, related-file mode, selected paths, and the content hash of durable notes. A cache hit reuses the existing pack and updates `context-packs/current.md`.

## Runtime requirements

- Python 3.9 or later
- Git is optional
- No third-party Python packages
- Windows, macOS, and Linux
- SQLite FTS5 is optional; retrieval falls back automatically when unavailable

## Security model

- Project files remain authoritative.
- Generated summaries are navigation aids and must be verified against source files before important edits or conclusions.
- Common credential, private-key, environment, dependency, build, cache, and binary paths are excluded.
- Sensitive assignment values and known provider-token formats are redacted from source and durable-note excerpts.
- High-entropy tokens are excluded from search terms.
- The indexer does not execute project code and does not access the network.

Review [security and ignore rules](references/security-and-ignore.md) for details.

## Development

Run tests:

```bash
python tests/run_tests.py
```

Build release packages:

```bash
python tools/build_release.py --output dist
```

The release builder creates reproducible archives:

- `project-cognition-skill-vX.Y.Z.zip`
- `project-cognition-plugin-vX.Y.Z.zip`
- `SHA256SUMS.txt`

## Current limitations and roadmap

- Automatic activation still depends on the host selecting the skill or the user invoking `$project-cognition` explicitly.
- Structural extraction uses lightweight language-specific patterns. Tree-sitter or language-server adapters would improve symbol and reference precision.
- Dependency expansion currently resolves one hop and focuses on common relative/module import forms.
- The index does not parse PDF, Word, PowerPoint, spreadsheet, or image content.
- Very large repositories can benefit from sharded indexes and background worker support in a later version.
- Shared multi-agent writes across separate machines require an external synchronization layer; the current lock protects one local project directory.

## License

MIT License. See [LICENSE](LICENSE).
