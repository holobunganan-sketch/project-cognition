---
name: project-cognition
description: Build, refresh, and query a persistent structural index for the current project before repository analysis, multi-file editing, debugging, architecture review, onboarding, or any task that depends on understanding project files. Reuse prior cognition, detect file changes incrementally, and generate a compact task-specific context pack. Do not use for a single isolated file when no wider project context is needed.
---

# Project Cognition

Use this skill to establish a reusable, source-linked understanding of a project directory. Project files remain the source of truth. The generated cognition layer is a rebuildable local cache.

## Required workflow

### 1. Locate the bundled script

Resolve this skill directory from the loaded `SKILL.md` path. Run the script with the current Python interpreter:

```bash
python "<skill-directory>/scripts/project_cognition.py" prepare --project "<project-root>"
```

Use `python3` when `python` is unavailable. Do not install packages. The script uses only the Python standard library.

### 2. Read the prepare result

The command prints JSON. Handle these states:

- `initialized`: the cognition layer was created.
- `clean`: indexed source content did not change.
- `updated`: changed files were incrementally re-indexed.
- `rebuild_required`: run `rebuild` before continuing.
- `failed`: report the concrete failure and inspect project files directly.

Read `.project-cognition/START_HERE.md` after initialization or when the project overview changed.

### 3. Generate a task context pack

Before broad project analysis, run:

```bash
python "<skill-directory>/scripts/project_cognition.py" context \
  --project "<project-root>" \
  --task "<the user's current task>"
```

Read the returned context-pack path. Use it as navigation, then open the original source files that support important conclusions or edits.

### 4. Perform the task

Follow these rules:

- Verify important claims against original files before editing or reporting them.
- Never treat generated summaries as more authoritative than project files.
- Do not execute project code merely to build cognition.
- Do not index ignored files, secrets, credentials, private keys, build output, dependency directories, or binary content.
- Do not manually rewrite files under `.project-cognition/generated/` or `.project-cognition/cache/`.
- Human or agent notes belong under `.project-cognition/knowledge/`.

### 5. Refresh after modifications

After changing project files, run:

```bash
python "<skill-directory>/scripts/project_cognition.py" prepare --project "<project-root>"
```

This provides read-after-write consistency for later project queries. Refresh once after a coherent edit batch rather than after every individual write.

## Commands

### Status without changing the index

```bash
python "<skill-directory>/scripts/project_cognition.py" status --project "<project-root>"
```

### Validate cognition integrity

```bash
python "<skill-directory>/scripts/project_cognition.py" validate --project "<project-root>"
```

### Fully rebuild generated cognition

Use this when the schema changed, the cache is damaged, or validation requests a rebuild:

```bash
python "<skill-directory>/scripts/project_cognition.py" rebuild --project "<project-root>"
```

### Install an optional project entry instruction

Only do this when the user explicitly asks for automatic project-level activation. It adds an idempotent managed block to the repository's `AGENTS.md`:

```bash
python "<skill-directory>/scripts/project_cognition.py" install-entry --project "<project-root>"
```

### Remove that managed entry

```bash
python "<skill-directory>/scripts/project_cognition.py" remove-entry --project "<project-root>"
```

## Output layout

The script creates:

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

`START_HERE.md`, `manifest.json`, `generated/`, `context-packs/`, and `cache/` are machine maintained. The `knowledge/` directory is preserved across rebuilds.

## Retrieval limits

The context command defaults to a compact pack. Increase limits only when the task genuinely needs broader context:

```bash
python "<skill-directory>/scripts/project_cognition.py" context \
  --project "<project-root>" \
  --task "<task>" \
  --max-files 12 \
  --max-chars 36000
```

Do not paste an entire context pack back to the user. Use it internally to navigate the project and cite concrete source paths in the final work.

## Reference material

Read these only when needed:

- `references/operating-model.md`: ownership, synchronization, and consistency model.
- `references/index-schema.md`: generated data and SQLite schema.
- `references/security-and-ignore.md`: exclusion and secret-handling rules.
