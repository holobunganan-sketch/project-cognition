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

The tool stores hashes, structural metadata, symbols, headings, imports, and selected normalized search terms. Context packs contain source excerpts from selected eligible files. They remain local to the project.
