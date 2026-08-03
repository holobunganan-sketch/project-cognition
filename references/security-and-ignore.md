# Security and ignore rules

The indexer never executes project code and makes no network requests.

## Exclusions

It excludes:

- Git-ignored files when Git is available
- dependency, cache, build, editor, and generated directories
- `.project-cognition` itself
- common secret-bearing filenames and private-key formats
- unsupported binary content
- files larger than the configured maximum, 2 MiB by default
- symbolic links that leave the project root

Users can add patterns to `.project-cognitionignore`. Patterns use a conservative subset of gitignore-style syntax: directory names, shell wildcards, anchored paths, and comments. Negation rules are intentionally unsupported.

## Sensitive values

Search terms exclude high-entropy tokens, long hexadecimal strings, JWT-like strings, and assignment values on lines whose keys resemble password, secret, token, API key, authorization, or credential fields.

Context excerpts redact:

- sensitive assignment lines
- common OpenAI-style `sk-` tokens
- common GitHub token formats
- common AWS access-key identifiers

The same redaction applies when durable knowledge notes are copied into a context pack. Project files and knowledge notes remain unchanged.

## Stored data

The tool stores hashes, structural metadata, symbols, headings, imports, selected normalized search terms, cached task-pack metadata, and local source excerpts. All generated data remains local to the project unless the user deliberately commits or shares it.
