#!/usr/bin/env python3
"""Persistent, incremental structural cognition for arbitrary project directories.

This script intentionally uses only the Python standard library. It does not execute
project code and does not make network requests.
"""

from __future__ import annotations

import argparse
import collections
import contextlib
import datetime as dt
import fnmatch
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Set, Tuple

TOOL_VERSION = "1.0.0"
SCHEMA_VERSION = 1
COGNITION_DIRNAME = ".project-cognition"
DB_RELATIVE = Path("cache") / "index.sqlite3"
DEFAULT_MAX_FILE_SIZE = 2 * 1024 * 1024
DEFAULT_MAX_INDEX_CHARS = 300_000
DEFAULT_CONTEXT_FILES = 8
DEFAULT_CONTEXT_CHARS = 24_000
LOCK_TIMEOUT_SECONDS = 15.0
LOCK_STALE_SECONDS = 15 * 60
MAX_SYMBOLS_PER_FILE = 500
MAX_IMPORTS_PER_FILE = 500
MAX_HEADINGS_PER_FILE = 500
MAX_SEARCH_TERMS = 120
MAX_GENERATED_FILE_LIST = 600
MAX_CONTEXT_PACKS = 20

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
DEFAULT_IGNORE_FILE = SKILL_DIR / "assets" / "default-ignore.txt"

TEXT_EXTENSIONS: Set[str] = {
    ".py", ".pyi", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx",
    ".java", ".kt", ".kts", ".scala", ".go", ".rs", ".c", ".h", ".cc",
    ".cpp", ".cxx", ".hpp", ".cs", ".fs", ".fsx", ".rb", ".php", ".swift",
    ".dart", ".lua", ".r", ".R", ".jl", ".sh", ".bash", ".zsh", ".fish",
    ".ps1", ".psm1", ".bat", ".cmd", ".sql", ".graphql", ".gql",
    ".md", ".mdx", ".rst", ".adoc", ".asciidoc", ".txt", ".tex",
    ".json", ".jsonc", ".json5", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".conf", ".properties", ".xml", ".html", ".htm", ".css", ".scss",
    ".sass", ".less", ".vue", ".svelte", ".astro", ".env.example",
    ".dockerfile", ".makefile", ".gradle", ".cmake", ".proto", ".thrift",
    ".csv", ".tsv"
}

SPECIAL_TEXT_FILENAMES: Set[str] = {
    "readme", "license", "copying", "notice", "changelog", "authors",
    "contributing", "code_of_conduct", "security", "dockerfile", "makefile",
    "rakefile", "gemfile", "procfile", "justfile", "cmakelists.txt",
    "package.json", "tsconfig.json", "pyproject.toml", "setup.py", "setup.cfg",
    "requirements.txt", "cargo.toml", "go.mod", "go.sum", "composer.json",
    "build.gradle", "settings.gradle", "pom.xml", "agents.md", "claude.md"
}

LANGUAGE_BY_EXT: Dict[str, str] = {
    ".py": "Python", ".pyi": "Python", ".js": "JavaScript", ".jsx": "JavaScript",
    ".mjs": "JavaScript", ".cjs": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript",
    ".java": "Java", ".kt": "Kotlin", ".kts": "Kotlin", ".scala": "Scala",
    ".go": "Go", ".rs": "Rust", ".c": "C", ".h": "C/C++", ".cc": "C++",
    ".cpp": "C++", ".cxx": "C++", ".hpp": "C++", ".cs": "C#", ".fs": "F#",
    ".fsx": "F#", ".rb": "Ruby", ".php": "PHP", ".swift": "Swift",
    ".dart": "Dart", ".lua": "Lua", ".r": "R", ".R": "R", ".jl": "Julia",
    ".sh": "Shell", ".bash": "Shell", ".zsh": "Shell", ".fish": "Shell",
    ".ps1": "PowerShell", ".psm1": "PowerShell", ".bat": "Batch", ".cmd": "Batch",
    ".sql": "SQL", ".graphql": "GraphQL", ".gql": "GraphQL", ".md": "Markdown",
    ".mdx": "MDX", ".rst": "reStructuredText", ".adoc": "AsciiDoc",
    ".asciidoc": "AsciiDoc", ".txt": "Text", ".tex": "TeX", ".json": "JSON",
    ".jsonc": "JSONC", ".json5": "JSON5", ".yaml": "YAML", ".yml": "YAML",
    ".toml": "TOML", ".ini": "INI", ".cfg": "Config", ".conf": "Config",
    ".properties": "Properties", ".xml": "XML", ".html": "HTML", ".htm": "HTML",
    ".css": "CSS", ".scss": "SCSS", ".sass": "Sass", ".less": "Less",
    ".vue": "Vue", ".svelte": "Svelte", ".astro": "Astro", ".proto": "Protocol Buffers",
    ".thrift": "Thrift", ".csv": "CSV", ".tsv": "TSV"
}

ENTRYPOINT_NAMES: Set[str] = {
    "main.py", "app.py", "server.py", "manage.py", "cli.py", "__main__.py",
    "index.js", "index.ts", "main.js", "main.ts", "app.js", "app.ts", "server.js",
    "server.ts", "index.tsx", "main.tsx", "app.tsx", "main.rs", "lib.rs", "main.go",
    "program.cs", "application.java", "dockerfile", "makefile", "package.json",
    "pyproject.toml", "cargo.toml", "go.mod", "pom.xml", "build.gradle"
}

CATEGORY_BY_EXT: Dict[str, str] = {
    ".md": "documentation", ".mdx": "documentation", ".rst": "documentation",
    ".adoc": "documentation", ".asciidoc": "documentation", ".txt": "documentation",
    ".json": "configuration", ".jsonc": "configuration", ".json5": "configuration",
    ".yaml": "configuration", ".yml": "configuration", ".toml": "configuration",
    ".ini": "configuration", ".cfg": "configuration", ".conf": "configuration",
    ".properties": "configuration", ".xml": "configuration", ".env.example": "configuration",
    ".csv": "data", ".tsv": "data", ".sql": "data"
}

STOPWORDS: Set[str] = {
    "the", "and", "for", "with", "from", "this", "that", "then", "than", "into", "onto",
    "are", "was", "were", "will", "would", "could", "should", "can", "may", "might", "must",
    "not", "but", "all", "any", "some", "each", "other", "more", "most", "less", "use", "using",
    "used", "return", "returns", "true", "false", "null", "none", "self", "class", "function",
    "def", "const", "let", "var", "public", "private", "protected", "static", "async", "await",
    "import", "export", "default", "new", "get", "set", "type", "interface", "string", "number",
    "void", "object", "data", "value", "values", "file", "files", "path", "name", "main",
    "一个", "一种", "这个", "那个", "这些", "那些", "以及", "或者", "进行", "使用", "可以",
    "需要", "项目", "文件", "内容", "相关", "当前", "通过", "实现", "用于", "包括", "如果"
}

SENSITIVE_BASENAME_PATTERNS: Tuple[str, ...] = (
    ".env", ".env.*", ".npmrc", ".pypirc", ".netrc", "id_rsa", "id_rsa.*",
    "id_ed25519", "id_ed25519.*", "credentials.json", "credentials.yml",
    "service-account*.json", "service_account*.json", "secrets.json", "secrets.yml",
    "secrets.yaml", "secret.json", "secret.yml", "secret.yaml", "token.json",
    "auth.json", "*.pem", "*.key", "*.p12", "*.pfx", "*.jks", "*.keystore"
)

SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?i)(password|passwd|pwd|secret|token|api[_-]?key|authorization|credential|private[_-]?key)\s*[:=]"
)
HIGH_ENTROPY_RE = re.compile(r"^(?:[A-Fa-f0-9]{24,}|[A-Za-z0-9+/=_-]{40,}|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)$")
EN_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.$:/-]{1,80}")
ZH_SEQUENCE_RE = re.compile(r"[\u3400-\u9fff]{2,24}")

MANAGED_ENTRY_START = "<!-- project-cognition:start -->"
MANAGED_ENTRY_END = "<!-- project-cognition:end -->"
MANAGED_ENTRY = f"""{MANAGED_ENTRY_START}
## Project cognition

Before repository-wide analysis, multi-file edits, debugging, architecture review, or project onboarding:

1. Invoke `$project-cognition` for the current task.
2. Read `.project-cognition/START_HERE.md` and the generated task context pack.
3. Verify important conclusions against original project files.
4. Refresh project cognition after a coherent batch of file changes.
{MANAGED_ENTRY_END}"""


class CognitionError(RuntimeError):
    """Expected operational error with a user-readable message."""


class ProjectLock:
    def __init__(self, lock_path: Path, timeout: float = LOCK_TIMEOUT_SECONDS) -> None:
        self.lock_path = lock_path
        self.timeout = timeout
        self.acquired = False

    def __enter__(self) -> "ProjectLock":
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                payload = json.dumps({
                    "pid": os.getpid(),
                    "created_at": utc_now(),
                    "epoch": time.time(),
                }).encode("utf-8")
                os.write(fd, payload)
                os.close(fd)
                self.acquired = True
                return self
            except FileExistsError:
                if self._is_stale():
                    with contextlib.suppress(OSError):
                        self.lock_path.unlink()
                    continue
                if time.monotonic() >= deadline:
                    raise CognitionError(
                        f"Timed out waiting for cognition lock: {self.lock_path}. "
                        "Another agent may be updating this project."
                    )
                time.sleep(0.15)

    def _is_stale(self) -> bool:
        try:
            stat = self.lock_path.stat()
        except FileNotFoundError:
            return False
        return (time.time() - stat.st_mtime) > LOCK_STALE_SECONDS

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        if self.acquired:
            with contextlib.suppress(OSError):
                self.lock_path.unlink()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def local_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def json_dumps(data: object, pretty: bool = True) -> str:
    if pretty:
        return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise


def atomic_write_json(path: Path, data: object) -> None:
    atomic_write_text(path, json_dumps(data) + "\n")


def safe_relative(path: Path, root: Path) -> Optional[str]:
    try:
        rel = path.resolve().relative_to(root.resolve())
    except (ValueError, OSError):
        return None
    return rel.as_posix()


def run_git(root: Path, args: Sequence[str], timeout: float = 20.0) -> Optional[bytes]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def resolve_project_root(project: str) -> Path:
    candidate = Path(project).expanduser().resolve()
    if not candidate.exists():
        raise CognitionError(f"Project path does not exist: {candidate}")
    if candidate.is_file():
        candidate = candidate.parent
    git_root_bytes = run_git(candidate, ["rev-parse", "--show-toplevel"])
    if git_root_bytes:
        try:
            git_root = Path(git_root_bytes.decode("utf-8", "replace").strip()).resolve()
            candidate.relative_to(git_root)
            return git_root
        except (ValueError, OSError):
            pass
    return candidate


def git_info(root: Path) -> Dict[str, object]:
    inside = run_git(root, ["rev-parse", "--is-inside-work-tree"])
    if not inside or inside.strip() != b"true":
        return {
            "is_git": False,
            "head": None,
            "branch": None,
            "dirty": False,
            "status_counts": {},
        }
    head_raw = run_git(root, ["rev-parse", "HEAD"])
    branch_raw = run_git(root, ["rev-parse", "--abbrev-ref", "HEAD"])
    status_raw = run_git(root, ["status", "--porcelain=v1", "--untracked-files=all"], timeout=30.0) or b""
    counts: collections.Counter[str] = collections.Counter()
    relevant_entries = 0
    for raw_line in status_raw.decode("utf-8", "replace").splitlines():
        if len(raw_line) < 3:
            continue
        code = raw_line[:2]
        path_text = raw_line[3:].strip().strip('"').replace("\\", "/")
        path_candidates = [part.strip().strip('"') for part in path_text.split(" -> ")]
        if path_candidates and all(
            candidate == COGNITION_DIRNAME or candidate.startswith(COGNITION_DIRNAME + "/")
            for candidate in path_candidates
        ):
            continue
        relevant_entries += 1
        if "?" in code:
            counts["untracked"] += 1
        if "M" in code:
            counts["modified"] += 1
        if "A" in code:
            counts["added"] += 1
        if "D" in code:
            counts["deleted"] += 1
        if "R" in code:
            counts["renamed"] += 1
        if "U" in code:
            counts["unmerged"] += 1
    return {
        "is_git": True,
        "head": head_raw.decode("utf-8", "replace").strip() if head_raw else None,
        "branch": branch_raw.decode("utf-8", "replace").strip() if branch_raw else None,
        "dirty": relevant_entries > 0,
        "status_counts": dict(sorted(counts.items())),
    }


def load_ignore_patterns() -> List[str]:
    patterns: List[str] = []
    if DEFAULT_IGNORE_FILE.exists():
        patterns.extend(parse_ignore_file(DEFAULT_IGNORE_FILE))
    return patterns


def parse_ignore_file(path: Path) -> List[str]:
    patterns: List[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return patterns
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        line = line.replace("\\", "/")
        if line.startswith("./"):
            line = line[2:]
        patterns.append(line)
    return patterns


def matches_ignore(rel_path: str, patterns: Sequence[str], is_dir: bool = False) -> bool:
    rel = rel_path.strip("/")
    base = rel.rsplit("/", 1)[-1]
    parts = rel.split("/") if rel else []
    for pattern in patterns:
        p = pattern.strip().replace("\\", "/")
        if not p:
            continue
        directory_only = p.endswith("/")
        p = p.rstrip("/")
        anchored = p.startswith("/")
        p = p.lstrip("/")
        if directory_only:
            if anchored:
                if rel == p or rel.startswith(p + "/"):
                    return True
            elif p in parts or rel == p or rel.startswith(p + "/"):
                return True
            continue
        if "/" in p:
            if anchored and fnmatch.fnmatch(rel, p):
                return True
            if fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(rel, f"*/{p}"):
                return True
        else:
            if fnmatch.fnmatch(base, p) or any(fnmatch.fnmatch(part, p) for part in parts):
                return True
        if is_dir and fnmatch.fnmatch(rel + "/", p + "/"):
            return True
    return False


def is_sensitive_path(rel_path: str) -> bool:
    base = rel_path.rsplit("/", 1)[-1].lower()
    for pattern in SENSITIVE_BASENAME_PATTERNS:
        if fnmatch.fnmatch(base, pattern.lower()):
            return True
    return False


def normalize_extension(path: Path) -> str:
    lower_name = path.name.lower()
    if lower_name.endswith(".env.example"):
        return ".env.example"
    if lower_name == "dockerfile":
        return ".dockerfile"
    if lower_name == "makefile":
        return ".makefile"
    return path.suffix.lower()


def is_text_candidate(path: Path) -> bool:
    ext = normalize_extension(path)
    name = path.name.lower()
    stem = path.stem.lower()
    if ext in TEXT_EXTENSIONS:
        return True
    if name in SPECIAL_TEXT_FILENAMES or stem in SPECIAL_TEXT_FILENAMES:
        return True
    if not path.suffix and len(name) <= 64:
        return True
    return False


def is_probably_binary(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            chunk = handle.read(8192)
    except OSError:
        return True
    if b"\x00" in chunk:
        if chunk.startswith((b"\xff\xfe", b"\xfe\xff")):
            return False
        return True
    return False


def discover_files(root: Path, patterns: Sequence[str], max_size: int) -> Tuple[List[Path], Dict[str, int]]:
    stats = collections.Counter()
    custom_patterns = list(patterns)
    custom_ignore = root / ".project-cognitionignore"
    if custom_ignore.exists():
        custom_patterns.extend(parse_ignore_file(custom_ignore))

    candidates: List[Path] = []
    git_paths = run_git(root, ["ls-files", "--cached", "--others", "--exclude-standard", "-z"], timeout=60.0)
    if git_paths is not None:
        raw_paths = [p for p in git_paths.split(b"\0") if p]
        for raw in raw_paths:
            rel = raw.decode("utf-8", "surrogateescape").replace("\\", "/")
            path = root / Path(rel)
            if matches_ignore(rel, custom_patterns) or is_sensitive_path(rel):
                stats["ignored"] += 1
                continue
            if path.is_symlink():
                resolved_rel = safe_relative(path, root)
                if resolved_rel is None:
                    stats["external_symlink"] += 1
                    continue
            if not path.is_file():
                continue
            try:
                size = path.stat().st_size
            except OSError:
                stats["unreadable"] += 1
                continue
            if size > max_size:
                stats["oversize"] += 1
                continue
            if not is_text_candidate(path) or is_probably_binary(path):
                stats["binary_or_unsupported"] += 1
                continue
            candidates.append(path)
        stats["discovery_mode_git"] = 1
    else:
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            current = Path(dirpath)
            rel_dir = safe_relative(current, root) or ""
            kept_dirs: List[str] = []
            for dirname in dirnames:
                child_rel = f"{rel_dir}/{dirname}".strip("/").replace("\\", "/")
                child = current / dirname
                if child.is_symlink():
                    stats["symlink_dir"] += 1
                    continue
                if matches_ignore(child_rel, custom_patterns, is_dir=True):
                    stats["ignored_dir"] += 1
                    continue
                kept_dirs.append(dirname)
            dirnames[:] = kept_dirs
            for filename in filenames:
                path = current / filename
                rel = safe_relative(path, root)
                if rel is None:
                    stats["external_path"] += 1
                    continue
                if matches_ignore(rel, custom_patterns) or is_sensitive_path(rel):
                    stats["ignored"] += 1
                    continue
                if path.is_symlink():
                    stats["symlink_file"] += 1
                    continue
                try:
                    size = path.stat().st_size
                except OSError:
                    stats["unreadable"] += 1
                    continue
                if size > max_size:
                    stats["oversize"] += 1
                    continue
                if not is_text_candidate(path) or is_probably_binary(path):
                    stats["binary_or_unsupported"] += 1
                    continue
                candidates.append(path)
        stats["discovery_mode_walk"] = 1
    candidates.sort(key=lambda p: (safe_relative(p, root) or "").lower())
    stats["eligible"] = len(candidates)
    return candidates, dict(stats)


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_text_safely(path: Path, max_chars: int = DEFAULT_MAX_INDEX_CHARS) -> str:
    data = path.read_bytes()
    encodings = []
    if data.startswith(b"\xef\xbb\xbf"):
        encodings.append("utf-8-sig")
    elif data.startswith(b"\xff\xfe"):
        encodings.append("utf-16-le")
    elif data.startswith(b"\xfe\xff"):
        encodings.append("utf-16-be")
    encodings.extend(["utf-8", "utf-16", "latin-1"])
    text = ""
    for encoding in encodings:
        try:
            text = data.decode(encoding)
            break
        except UnicodeError:
            continue
    if not text:
        text = data.decode("utf-8", "replace")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text[:max_chars]


def classify_file(path: Path, rel_path: str) -> Tuple[str, str]:
    ext = normalize_extension(path)
    lower = rel_path.lower()
    name = path.name.lower()
    language = LANGUAGE_BY_EXT.get(ext, "Text")
    if name == "dockerfile":
        language = "Dockerfile"
    elif name == "makefile":
        language = "Makefile"
    if any(part in lower.split("/") for part in ("test", "tests", "spec", "specs", "__tests__")) or re.search(r"(?:^|[._-])(test|spec)(?:[._-]|$)", name):
        category = "test"
    elif any(part in lower.split("/") for part in ("docs", "doc", "documentation")):
        category = "documentation"
    elif ext in CATEGORY_BY_EXT:
        category = CATEGORY_BY_EXT[ext]
    elif name in {"dockerfile", "makefile", "package.json", "pyproject.toml", "cargo.toml", "go.mod", "pom.xml", "build.gradle"}:
        category = "build/configuration"
    else:
        category = "source"
    return category, language


def top_module(rel_path: str) -> str:
    parts = rel_path.split("/")
    return parts[0] if len(parts) > 1 else "root"


def split_identifier(token: str) -> List[str]:
    token = token.replace("\\", "/")
    chunks: List[str] = []
    for part in re.split(r"[\s_.$:/\-]+", token):
        if not part:
            continue
        camel = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", part)
        camel = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", camel)
        chunks.extend(camel.split())
    return [chunk.lower() for chunk in chunks if 2 <= len(chunk) <= 64]


def task_terms(text: str) -> Set[str]:
    terms: Set[str] = set()
    for match in EN_TOKEN_RE.findall(text):
        for token in split_identifier(match):
            if token not in STOPWORDS and not HIGH_ENTROPY_RE.match(token):
                terms.add(token)
    for seq in ZH_SEQUENCE_RE.findall(text):
        if seq not in STOPWORDS:
            terms.add(seq)
        for n in (2, 3):
            if len(seq) >= n:
                terms.update(seq[i:i + n] for i in range(len(seq) - n + 1))
    return terms


def redact_sensitive_lines(text: str) -> str:
    output: List[str] = []
    for line in text.splitlines():
        if SENSITIVE_ASSIGNMENT_RE.search(line):
            key = re.split(r"[:=]", line, maxsplit=1)[0]
            output.append(f"{key}=<redacted>")
        else:
            output.append(line)
    return "\n".join(output)


def extract_search_terms(
    text: str,
    rel_path: str,
    symbols: Sequence[Mapping[str, object]],
    headings: Sequence[Mapping[str, object]],
    imports: Sequence[Mapping[str, object]],
) -> List[Tuple[str, int]]:
    counts: collections.Counter[str] = collections.Counter()

    def add_token(raw: str, weight: int = 1) -> None:
        for token in split_identifier(raw):
            if token in STOPWORDS or HIGH_ENTROPY_RE.match(token):
                continue
            counts[token] += weight
        for seq in ZH_SEQUENCE_RE.findall(raw):
            if seq in STOPWORDS:
                continue
            counts[seq] += weight
            for n in (2, 3):
                if len(seq) >= n:
                    for i in range(len(seq) - n + 1):
                        counts[seq[i:i + n]] += max(1, weight // 2)

    for part in rel_path.split("/"):
        add_token(part, 8)
    for symbol in symbols:
        add_token(str(symbol.get("name", "")), 10)
        add_token(str(symbol.get("kind", "")), 2)
    for heading in headings:
        add_token(str(heading.get("title", "")), 8)
    for imp in imports:
        add_token(str(imp.get("target", "")), 4)

    safe_text = redact_sensitive_lines(text)
    for match in EN_TOKEN_RE.findall(safe_text):
        add_token(match, 1)
    for seq in ZH_SEQUENCE_RE.findall(safe_text):
        add_token(seq, 1)

    return counts.most_common(MAX_SEARCH_TERMS)


def extract_symbols(text: str, language: str) -> List[Dict[str, object]]:
    lines = text.splitlines()
    results: List[Dict[str, object]] = []

    patterns: List[Tuple[str, re.Pattern[str]]] = []
    if language == "Python":
        patterns = [
            ("class", re.compile(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)\b[^:]*:?")),
            ("function", re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\([^)]*\)")),
        ]
    elif language in {"JavaScript", "TypeScript", "Vue", "Svelte", "Astro"}:
        patterns = [
            ("class", re.compile(r"^\s*(?:export\s+)?(?:default\s+)?class\s+([A-Za-z_$][\w$]*)")),
            ("interface", re.compile(r"^\s*(?:export\s+)?interface\s+([A-Za-z_$][\w$]*)")),
            ("type", re.compile(r"^\s*(?:export\s+)?type\s+([A-Za-z_$][\w$]*)\s*=")),
            ("enum", re.compile(r"^\s*(?:export\s+)?enum\s+([A-Za-z_$][\w$]*)")),
            ("function", re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(")),
            ("function", re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>")),
        ]
    elif language == "Rust":
        patterns = [
            ("function", re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?fn\s+([A-Za-z_][A-Za-z0-9_]*)")),
            ("struct", re.compile(r"^\s*(?:pub\s+)?struct\s+([A-Za-z_][A-Za-z0-9_]*)")),
            ("enum", re.compile(r"^\s*(?:pub\s+)?enum\s+([A-Za-z_][A-Za-z0-9_]*)")),
            ("trait", re.compile(r"^\s*(?:pub\s+)?trait\s+([A-Za-z_][A-Za-z0-9_]*)")),
            ("module", re.compile(r"^\s*(?:pub\s+)?mod\s+([A-Za-z_][A-Za-z0-9_]*)")),
        ]
    elif language == "Go":
        patterns = [
            ("function", re.compile(r"^\s*func\s+(?:\([^)]*\)\s*)?([A-Za-z_][A-Za-z0-9_]*)\s*\(")),
            ("type", re.compile(r"^\s*type\s+([A-Za-z_][A-Za-z0-9_]*)\s+(?:struct|interface|\w+)")),
        ]
    elif language in {"Java", "Kotlin", "Scala", "C#", "C++", "C", "Swift", "Dart", "PHP"}:
        patterns = [
            ("class", re.compile(r"^\s*(?:(?:public|private|protected|internal|open|final|abstract|sealed|static)\s+)*(?:class|record)\s+([A-Za-z_][A-Za-z0-9_]*)")),
            ("interface", re.compile(r"^\s*(?:(?:public|private|protected|internal)\s+)*interface\s+([A-Za-z_][A-Za-z0-9_]*)")),
            ("enum", re.compile(r"^\s*(?:(?:public|private|protected|internal)\s+)*enum\s+([A-Za-z_][A-Za-z0-9_]*)")),
            ("function", re.compile(r"^\s*(?:(?:public|private|protected|internal|static|virtual|override|async|final|inline|extern)\s+)+[\w:<>,\[\]?*&~]+\s+([A-Za-z_~][A-Za-z0-9_]*)\s*\(")),
        ]
    elif language in {"Ruby", "Lua", "Shell", "PowerShell"}:
        patterns = [
            ("class", re.compile(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_:]*)")),
            ("module", re.compile(r"^\s*module\s+([A-Za-z_][A-Za-z0-9_:]*)")),
            ("function", re.compile(r"^\s*(?:def|function)\s+([A-Za-z_][A-Za-z0-9_!?-]*)")),
        ]

    for lineno, line in enumerate(lines, start=1):
        if len(results) >= MAX_SYMBOLS_PER_FILE:
            break
        for kind, pattern in patterns:
            match = pattern.search(line)
            if match:
                signature = line.strip()
                if len(signature) > 240:
                    signature = signature[:237] + "..."
                results.append({
                    "kind": kind,
                    "name": match.group(1),
                    "line": lineno,
                    "signature": signature,
                })
                break
    return results


def extract_headings(text: str, language: str) -> List[Dict[str, object]]:
    if language not in {"Markdown", "MDX", "reStructuredText", "AsciiDoc", "HTML"}:
        return []
    lines = text.splitlines()
    results: List[Dict[str, object]] = []
    for i, line in enumerate(lines, start=1):
        if len(results) >= MAX_HEADINGS_PER_FILE:
            break
        title = ""
        level = 0
        if language in {"Markdown", "MDX"}:
            match = re.match(r"^\s*(#{1,6})\s+(.+?)\s*#*\s*$", line)
            if match:
                level = len(match.group(1))
                title = match.group(2).strip()
        elif language == "AsciiDoc":
            match = re.match(r"^\s*(={1,6})\s+(.+?)\s*$", line)
            if match:
                level = len(match.group(1))
                title = match.group(2).strip()
        elif language == "HTML":
            match = re.search(r"<h([1-6])[^>]*>(.*?)</h\1>", line, re.IGNORECASE)
            if match:
                level = int(match.group(1))
                title = re.sub(r"<[^>]+>", "", match.group(2)).strip()
        elif language == "reStructuredText" and i < len(lines):
            next_line = lines[i]
            if line.strip() and re.match(r"^[=\-~^\"`:+*#]{3,}\s*$", next_line):
                char = next_line.strip()[0]
                level = {"=": 1, "-": 2, "~": 3, "^": 4}.get(char, 5)
                title = line.strip()
        if title:
            results.append({"level": level, "title": title[:240], "line": i})
    return results


def extract_imports(text: str, language: str) -> List[Dict[str, object]]:
    results: List[Dict[str, object]] = []
    patterns: List[re.Pattern[str]] = []
    if language == "Python":
        patterns = [
            re.compile(r"^\s*from\s+([A-Za-z0-9_\.]+)\s+import\b"),
            re.compile(r"^\s*import\s+([A-Za-z0-9_\.]+)"),
        ]
    elif language in {"JavaScript", "TypeScript", "Vue", "Svelte", "Astro"}:
        patterns = [
            re.compile(r"\bfrom\s+['\"]([^'\"]+)['\"]"),
            re.compile(r"\brequire\(\s*['\"]([^'\"]+)['\"]\s*\)"),
            re.compile(r"\bimport\(\s*['\"]([^'\"]+)['\"]\s*\)"),
            re.compile(r"^\s*import\s+['\"]([^'\"]+)['\"]"),
        ]
    elif language == "Rust":
        patterns = [
            re.compile(r"^\s*use\s+([^;]+);"),
            re.compile(r"^\s*(?:pub\s+)?mod\s+([A-Za-z_][A-Za-z0-9_]*)\s*;"),
        ]
    elif language == "Go":
        patterns = [
            re.compile(r"^\s*import\s+(?:[A-Za-z_][A-Za-z0-9_]*\s+)?\"([^\"]+)\""),
            re.compile(r"^\s*(?:[A-Za-z_][A-Za-z0-9_]*\s+)?\"([^\"]+)\"\s*$"),
        ]
    elif language in {"Java", "Kotlin", "Scala"}:
        patterns = [re.compile(r"^\s*import\s+([^;\s]+)")]
    elif language in {"C", "C++"}:
        patterns = [re.compile(r"^\s*#\s*include\s*[<\"]([^>\"]+)[>\"]")]
    elif language == "C#":
        patterns = [re.compile(r"^\s*using\s+([^;]+);")]
    elif language == "PHP":
        patterns = [
            re.compile(r"^\s*(?:require|require_once|include|include_once)\s*\(?\s*['\"]([^'\"]+)['\"]"),
            re.compile(r"^\s*use\s+([^;]+);")
        ]

    for lineno, line in enumerate(text.splitlines(), start=1):
        if len(results) >= MAX_IMPORTS_PER_FILE:
            break
        for pattern in patterns:
            match = pattern.search(line)
            if match:
                target = match.group(1).strip()
                if len(target) > 240:
                    target = target[:237] + "..."
                results.append({"target": target, "line": lineno})
                break
    return results


def entrypoint_score(rel_path: str, text: str, symbols: Sequence[Mapping[str, object]]) -> float:
    name = rel_path.rsplit("/", 1)[-1].lower()
    score = 0.0
    if name in ENTRYPOINT_NAMES:
        score += 10.0
    if rel_path.count("/") == 0:
        score += 1.0
    lower_text = text.lower()
    if "if __name__ == \"__main__\"" in lower_text or "if __name__ == '__main__'" in lower_text:
        score += 8.0
    if re.search(r"\bfunc\s+main\s*\(", text):
        score += 8.0
    if re.search(r"\bstatic\s+void\s+main\s*\(", text, re.IGNORECASE):
        score += 8.0
    if any(str(s.get("name", "")).lower() in {"main", "app", "server", "run", "cli"} for s in symbols):
        score += 4.0
    if name.startswith("readme"):
        score += 6.0
    return score


def connect_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    initialize_schema(conn)
    return conn


def initialize_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS files (
            path TEXT PRIMARY KEY,
            size INTEGER NOT NULL,
            mtime_ns INTEGER NOT NULL,
            sha256 TEXT NOT NULL,
            extension TEXT NOT NULL,
            category TEXT NOT NULL,
            language TEXT NOT NULL,
            line_count INTEGER NOT NULL,
            module TEXT NOT NULL,
            search_terms TEXT NOT NULL,
            entrypoint_score REAL NOT NULL,
            indexed_snapshot INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS symbols (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL,
            kind TEXT NOT NULL,
            name TEXT NOT NULL,
            line INTEGER NOT NULL,
            signature TEXT NOT NULL,
            FOREIGN KEY(file_path) REFERENCES files(path) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file_path);
        CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
        CREATE TABLE IF NOT EXISTS headings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL,
            level INTEGER NOT NULL,
            title TEXT NOT NULL,
            line INTEGER NOT NULL,
            FOREIGN KEY(file_path) REFERENCES files(path) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_headings_file ON headings(file_path);
        CREATE TABLE IF NOT EXISTS imports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL,
            target TEXT NOT NULL,
            line INTEGER NOT NULL,
            FOREIGN KEY(file_path) REFERENCES files(path) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_imports_file ON imports(file_path);
        CREATE TABLE IF NOT EXISTS changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot INTEGER NOT NULL,
            change_type TEXT NOT NULL,
            path TEXT NOT NULL,
            old_path TEXT,
            sha256 TEXT,
            changed_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_changes_snapshot ON changes(snapshot);
        """
    )
    current_schema = get_meta(conn, "schema_version")
    if current_schema is None:
        set_meta(conn, "schema_version", str(SCHEMA_VERSION))
    elif int(current_schema) != SCHEMA_VERSION:
        raise CognitionError(
            f"Index schema {current_schema} is incompatible with tool schema {SCHEMA_VERSION}. "
            "Run the rebuild command."
        )


def get_meta(conn: sqlite3.Connection, key: str) -> Optional[str]:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return str(row[0]) if row else None


def set_meta(conn: sqlite3.Connection, key: str, value: object) -> None:
    conn.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)),
    )


def load_existing_files(conn: sqlite3.Connection) -> Dict[str, sqlite3.Row]:
    return {str(row["path"]): row for row in conn.execute("SELECT * FROM files")}


def upsert_file(
    conn: sqlite3.Connection,
    path: str,
    stat: os.stat_result,
    digest: str,
    extension: str,
    category: str,
    language: str,
    line_count: int,
    module: str,
    search_terms_json: str,
    entry_score: float,
    snapshot: int,
    symbols: Sequence[Mapping[str, object]],
    headings: Sequence[Mapping[str, object]],
    imports: Sequence[Mapping[str, object]],
) -> None:
    conn.execute(
        """
        INSERT INTO files(path, size, mtime_ns, sha256, extension, category, language,
                          line_count, module, search_terms, entrypoint_score, indexed_snapshot)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(path) DO UPDATE SET
            size=excluded.size,
            mtime_ns=excluded.mtime_ns,
            sha256=excluded.sha256,
            extension=excluded.extension,
            category=excluded.category,
            language=excluded.language,
            line_count=excluded.line_count,
            module=excluded.module,
            search_terms=excluded.search_terms,
            entrypoint_score=excluded.entrypoint_score,
            indexed_snapshot=excluded.indexed_snapshot
        """,
        (
            path, stat.st_size, stat.st_mtime_ns, digest, extension, category, language,
            line_count, module, search_terms_json, entry_score, snapshot,
        ),
    )
    conn.execute("DELETE FROM symbols WHERE file_path = ?", (path,))
    conn.execute("DELETE FROM headings WHERE file_path = ?", (path,))
    conn.execute("DELETE FROM imports WHERE file_path = ?", (path,))
    conn.executemany(
        "INSERT INTO symbols(file_path, kind, name, line, signature) VALUES(?, ?, ?, ?, ?)",
        [(path, str(s["kind"]), str(s["name"]), int(s["line"]), str(s["signature"])) for s in symbols],
    )
    conn.executemany(
        "INSERT INTO headings(file_path, level, title, line) VALUES(?, ?, ?, ?)",
        [(path, int(h["level"]), str(h["title"]), int(h["line"])) for h in headings],
    )
    conn.executemany(
        "INSERT INTO imports(file_path, target, line) VALUES(?, ?, ?)",
        [(path, str(i["target"]), int(i["line"])) for i in imports],
    )


def ensure_output_layout(cognition_dir: Path) -> None:
    (cognition_dir / "generated" / "modules").mkdir(parents=True, exist_ok=True)
    (cognition_dir / "context-packs").mkdir(parents=True, exist_ok=True)
    (cognition_dir / "cache").mkdir(parents=True, exist_ok=True)
    (cognition_dir / "knowledge" / "decisions").mkdir(parents=True, exist_ok=True)
    (cognition_dir / "knowledge" / "notes").mkdir(parents=True, exist_ok=True)
    knowledge_readme = cognition_dir / "knowledge" / "README.md"
    if not knowledge_readme.exists():
        atomic_write_text(
            knowledge_readme,
            """# Project knowledge\n\nThis directory is preserved across cognition rebuilds.\n\n- Put durable architecture or operational notes in `notes/`.\n- Put accepted decisions in `decisions/`.\n- Include source paths and dates in every note.\n- Generated files elsewhere in `.project-cognition` remain the authoritative index of current file structure.\n""",
        )


def prepare_project(root: Path, max_file_size: int = DEFAULT_MAX_FILE_SIZE, force: bool = False) -> Dict[str, object]:
    cognition_dir = root / COGNITION_DIRNAME
    ensure_output_layout(cognition_dir)
    lock_path = cognition_dir / ".write.lock"
    with ProjectLock(lock_path):
        db_path = cognition_dir / DB_RELATIVE
        initialized_before = db_path.exists()
        conn = connect_db(db_path)
        try:
            prior_root = get_meta(conn, "project_root")
            if prior_root and Path(prior_root).resolve() != root.resolve():
                raise CognitionError(
                    f"Cognition index belongs to a different project root: {prior_root}. Run rebuild."
                )
            patterns = load_ignore_patterns()
            discovered, discovery_stats = discover_files(root, patterns, max_file_size)
            existing = load_existing_files(conn)
            discovered_map: Dict[str, Path] = {}
            for path in discovered:
                rel = safe_relative(path, root)
                if rel is not None:
                    discovered_map[rel] = path

            old_paths = set(existing)
            new_paths = set(discovered_map)
            deleted_paths = sorted(old_paths - new_paths)
            added_paths = sorted(new_paths - old_paths)
            possibly_changed = sorted(old_paths & new_paths)

            prior_snapshot = int(get_meta(conn, "snapshot") or "0")
            candidate_snapshot = prior_snapshot + 1
            changes: List[Dict[str, object]] = []
            parsed_count = 0
            metadata_only_count = 0
            unchanged_count = 0
            errors: List[Dict[str, str]] = []
            deleted_hashes: Dict[str, List[str]] = collections.defaultdict(list)
            for rel in deleted_paths:
                deleted_hashes[str(existing[rel]["sha256"])].append(rel)

            with conn:
                for rel in deleted_paths:
                    conn.execute("DELETE FROM files WHERE path = ?", (rel,))

                for rel in sorted(new_paths):
                    path = discovered_map[rel]
                    try:
                        stat = path.stat()
                    except OSError as exc:
                        errors.append({"path": rel, "error": str(exc)})
                        continue
                    old = existing.get(rel)
                    if not force and old and int(old["size"]) == stat.st_size and int(old["mtime_ns"]) == stat.st_mtime_ns:
                        unchanged_count += 1
                        continue
                    try:
                        digest = hash_file(path)
                    except OSError as exc:
                        errors.append({"path": rel, "error": str(exc)})
                        continue
                    if not force and old and str(old["sha256"]) == digest:
                        conn.execute(
                            "UPDATE files SET size = ?, mtime_ns = ? WHERE path = ?",
                            (stat.st_size, stat.st_mtime_ns, rel),
                        )
                        metadata_only_count += 1
                        continue
                    try:
                        text = read_text_safely(path)
                    except OSError as exc:
                        errors.append({"path": rel, "error": str(exc)})
                        continue
                    category, language = classify_file(path, rel)
                    symbols = extract_symbols(text, language)
                    headings = extract_headings(text, language)
                    imports = extract_imports(text, language)
                    terms = extract_search_terms(text, rel, symbols, headings, imports)
                    score = entrypoint_score(rel, text, symbols)
                    upsert_file(
                        conn=conn,
                        path=rel,
                        stat=stat,
                        digest=digest,
                        extension=normalize_extension(path),
                        category=category,
                        language=language,
                        line_count=text.count("\n") + (1 if text else 0),
                        module=top_module(rel),
                        search_terms_json=json.dumps(terms, ensure_ascii=False, separators=(",", ":")),
                        entry_score=score,
                        snapshot=candidate_snapshot,
                        symbols=symbols,
                        headings=headings,
                        imports=imports,
                    )
                    parsed_count += 1
                    change_type = "added" if old is None else "modified"
                    changes.append({"type": change_type, "path": rel, "sha256": digest})

                for rel in deleted_paths:
                    changes.append({"type": "deleted", "path": rel, "sha256": str(existing[rel]["sha256"])})

                # Convert matching add/delete pairs into renames for the change report.
                added_by_hash: Dict[str, List[str]] = collections.defaultdict(list)
                for item in changes:
                    if item["type"] == "added":
                        added_by_hash[str(item["sha256"])].append(str(item["path"]))
                rename_pairs: List[Tuple[str, str, str]] = []
                used_added: Set[str] = set()
                used_deleted: Set[str] = set()
                for digest, old_list in deleted_hashes.items():
                    new_list = added_by_hash.get(digest, [])
                    for old_rel, new_rel in zip(sorted(old_list), sorted(new_list)):
                        rename_pairs.append((old_rel, new_rel, digest))
                        used_deleted.add(old_rel)
                        used_added.add(new_rel)
                if rename_pairs:
                    filtered: List[Dict[str, object]] = []
                    for item in changes:
                        if item["type"] == "added" and str(item["path"]) in used_added:
                            continue
                        if item["type"] == "deleted" and str(item["path"]) in used_deleted:
                            continue
                        filtered.append(item)
                    for old_rel, new_rel, digest in rename_pairs:
                        filtered.append({"type": "renamed", "path": new_rel, "old_path": old_rel, "sha256": digest})
                    changes = filtered

                content_changed = bool(changes or force)
                snapshot = candidate_snapshot if content_changed or prior_snapshot == 0 else prior_snapshot
                now = utc_now()
                git = git_info(root)
                set_meta(conn, "schema_version", SCHEMA_VERSION)
                set_meta(conn, "tool_version", TOOL_VERSION)
                set_meta(conn, "project_root", str(root.resolve()))
                set_meta(conn, "snapshot", snapshot)
                set_meta(conn, "last_prepared_at", now)
                set_meta(conn, "git_head", git.get("head") or "")
                set_meta(conn, "git_branch", git.get("branch") or "")
                set_meta(conn, "max_file_size", max_file_size)
                if content_changed or prior_snapshot == 0:
                    set_meta(conn, "last_content_change_at", now)
                if changes:
                    conn.executemany(
                        "INSERT INTO changes(snapshot, change_type, path, old_path, sha256, changed_at) VALUES(?, ?, ?, ?, ?, ?)",
                        [
                            (
                                snapshot,
                                str(item["type"]),
                                str(item["path"]),
                                str(item.get("old_path")) if item.get("old_path") else None,
                                str(item.get("sha256")) if item.get("sha256") else None,
                                now,
                            )
                            for item in changes
                        ],
                    )
                # Keep a bounded change history.
                conn.execute(
                    "DELETE FROM changes WHERE snapshot < ?",
                    (max(0, snapshot - 100),),
                )

            snapshot = int(get_meta(conn, "snapshot") or "0")
            generate_views(root, cognition_dir, conn, changes, discovery_stats, errors)
            conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
            state = "initialized" if not initialized_before or prior_snapshot == 0 else ("updated" if changes or force else "clean")
            result: Dict[str, object] = {
                "command": "prepare",
                "state": state,
                "project_root": str(root),
                "cognition_dir": str(cognition_dir),
                "snapshot": snapshot,
                "changes": summarize_changes(changes),
                "changed_files": changes[:100],
                "indexed_files": int(conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]),
                "parsed_files": parsed_count,
                "metadata_only_updates": metadata_only_count,
                "unchanged_files": unchanged_count,
                "discovery": discovery_stats,
                "errors": errors,
                "start_here": str(cognition_dir / "START_HERE.md"),
            }
            return result
        finally:
            conn.close()


def summarize_changes(changes: Sequence[Mapping[str, object]]) -> Dict[str, int]:
    counter: collections.Counter[str] = collections.Counter(str(c["type"]) for c in changes)
    return {key: counter.get(key, 0) for key in ("added", "modified", "deleted", "renamed")}


def db_stats(conn: sqlite3.Connection) -> Dict[str, object]:
    file_count = int(conn.execute("SELECT COUNT(*) FROM files").fetchone()[0])
    symbol_count = int(conn.execute("SELECT COUNT(*) FROM symbols").fetchone()[0])
    heading_count = int(conn.execute("SELECT COUNT(*) FROM headings").fetchone()[0])
    import_count = int(conn.execute("SELECT COUNT(*) FROM imports").fetchone()[0])
    languages = [
        {"language": str(row[0]), "files": int(row[1]), "lines": int(row[2] or 0)}
        for row in conn.execute(
            "SELECT language, COUNT(*), SUM(line_count) FROM files GROUP BY language ORDER BY COUNT(*) DESC, language"
        )
    ]
    categories = [
        {"category": str(row[0]), "files": int(row[1])}
        for row in conn.execute(
            "SELECT category, COUNT(*) FROM files GROUP BY category ORDER BY COUNT(*) DESC, category"
        )
    ]
    modules = [
        {"module": str(row[0]), "files": int(row[1]), "lines": int(row[2] or 0)}
        for row in conn.execute(
            "SELECT module, COUNT(*), SUM(line_count) FROM files GROUP BY module ORDER BY COUNT(*) DESC, module"
        )
    ]
    return {
        "files": file_count,
        "symbols": symbol_count,
        "headings": heading_count,
        "imports": import_count,
        "languages": languages,
        "categories": categories,
        "modules": modules,
    }



def latest_persisted_changes(conn: sqlite3.Connection) -> List[Dict[str, object]]:
    row = conn.execute("SELECT MAX(snapshot) FROM changes").fetchone()
    if not row or row[0] is None:
        return []
    snapshot = int(row[0])
    output: List[Dict[str, object]] = []
    for change in conn.execute(
        "SELECT change_type, path, old_path, sha256 FROM changes WHERE snapshot = ? ORDER BY id",
        (snapshot,),
    ):
        item: Dict[str, object] = {
            "type": str(change["change_type"]),
            "path": str(change["path"]),
        }
        if change["old_path"]:
            item["old_path"] = str(change["old_path"])
        if change["sha256"]:
            item["sha256"] = str(change["sha256"])
        output.append(item)
    return output

def generate_views(
    root: Path,
    cognition_dir: Path,
    conn: sqlite3.Connection,
    changes: Sequence[Mapping[str, object]],
    discovery_stats: Mapping[str, int],
    errors: Sequence[Mapping[str, str]],
) -> None:
    stats = db_stats(conn)
    snapshot = int(get_meta(conn, "snapshot") or "0")
    generated_at = get_meta(conn, "last_prepared_at") or utc_now()
    git = git_info(root)
    display_changes = list(changes) if changes else latest_persisted_changes(conn)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "tool_version": TOOL_VERSION,
        "project_name": root.name,
        "project_root": str(root.resolve()),
        "snapshot": snapshot,
        "generated_at": generated_at,
        "git": git,
        "stats": stats,
        "last_changes": display_changes[:200],
        "discovery": dict(discovery_stats),
        "errors": list(errors),
    }
    atomic_write_json(cognition_dir / "manifest.json", manifest)

    start_here = build_start_here(root, conn, stats, snapshot, generated_at, git, display_changes)
    atomic_write_text(cognition_dir / "START_HERE.md", start_here)
    atomic_write_text(cognition_dir / "generated" / "current-state.md", build_current_state(root, stats, snapshot, generated_at, git, display_changes, errors))
    atomic_write_text(cognition_dir / "generated" / "architecture.md", build_architecture(root, conn, stats, snapshot))
    atomic_write_text(cognition_dir / "generated" / "file-map.md", build_file_map(conn, stats, snapshot))
    generate_module_views(cognition_dir / "generated" / "modules", conn, snapshot)


def build_start_here(
    root: Path,
    conn: sqlite3.Connection,
    stats: Mapping[str, object],
    snapshot: int,
    generated_at: str,
    git: Mapping[str, object],
    changes: Sequence[Mapping[str, object]],
) -> str:
    languages = stats.get("languages", [])
    modules = stats.get("modules", [])
    top_languages = ", ".join(f"{item['language']} ({item['files']})" for item in list(languages)[:8]) or "No indexed text files"
    top_modules = ", ".join(f"`{item['module']}` ({item['files']})" for item in list(modules)[:10]) or "None"
    entries = list(conn.execute(
        "SELECT path, language, entrypoint_score FROM files WHERE entrypoint_score > 0 ORDER BY entrypoint_score DESC, path LIMIT 12"
    ))
    entry_lines = "\n".join(f"- `{row['path']}` — {row['language']}" for row in entries) or "- No strong entrypoint candidates detected."
    change_summary = summarize_changes(changes)
    git_line = "Not a Git worktree"
    if git.get("is_git"):
        head = str(git.get("head") or "")
        git_line = f"Branch `{git.get('branch')}` at `{head[:12]}`; working tree {'has changes' if git.get('dirty') else 'is clean'}"
    return f"""# {root.name}: project cognition

> Generated structural map. Project files remain the source of truth.

## Snapshot

- Cognition snapshot: **{snapshot}**
- Prepared: `{generated_at}`
- Git: {git_line}
- Indexed text files: **{stats.get('files', 0)}**
- Extracted symbols: **{stats.get('symbols', 0)}**
- Last content changes: added {change_summary['added']}, modified {change_summary['modified']}, deleted {change_summary['deleted']}, renamed {change_summary['renamed']}

## Project shape

- Main languages/formats: {top_languages}
- Top-level modules: {top_modules}

## Likely entrypoints and orientation files

{entry_lines}

## Navigation

- Structural architecture: `generated/architecture.md`
- Current Git and index state: `generated/current-state.md`
- Module and file map: `generated/file-map.md`
- Module-specific views: `generated/modules/`
- Durable human/agent notes: `knowledge/`
- Task-specific retrieval: run the skill's `context` command

## Usage rule

Use this map to choose relevant files. Open original project files before making important claims or edits. Run `prepare` after a coherent edit batch so later agents read the new snapshot.
"""


def build_current_state(
    root: Path,
    stats: Mapping[str, object],
    snapshot: int,
    generated_at: str,
    git: Mapping[str, object],
    changes: Sequence[Mapping[str, object]],
    errors: Sequence[Mapping[str, str]],
) -> str:
    lines = [
        f"# Current state: {root.name}",
        "",
        f"- Snapshot: **{snapshot}**",
        f"- Prepared: `{generated_at}`",
        f"- Indexed files: **{stats.get('files', 0)}**",
    ]
    if git.get("is_git"):
        lines.extend([
            f"- Branch: `{git.get('branch')}`",
            f"- HEAD: `{git.get('head')}`",
            f"- Working tree dirty: **{'yes' if git.get('dirty') else 'no'}**",
            f"- Working tree counts: `{json.dumps(git.get('status_counts', {}), ensure_ascii=False)}`",
        ])
    else:
        lines.append("- Git: not detected")
    lines.extend(["", "## Last indexed changes", ""])
    if changes:
        for item in changes[:100]:
            if item.get("type") == "renamed":
                lines.append(f"- renamed: `{item.get('old_path')}` → `{item.get('path')}`")
            else:
                lines.append(f"- {item.get('type')}: `{item.get('path')}`")
    else:
        lines.append("- No source-content changes detected during the latest preparation.")
    if errors:
        lines.extend(["", "## Indexing errors", ""])
        for item in errors[:50]:
            lines.append(f"- `{item.get('path')}`: {item.get('error')}")
    return "\n".join(lines) + "\n"


def build_architecture(root: Path, conn: sqlite3.Connection, stats: Mapping[str, object], snapshot: int) -> str:
    lines = [
        f"# Structural architecture: {root.name}",
        "",
        f"> Deterministic view generated from snapshot {snapshot}. Module responsibilities require confirmation from source files.",
        "",
        "## Top-level modules",
        "",
    ]
    modules = list(stats.get("modules", []))
    for item in modules:
        module = str(item["module"])
        language_rows = list(conn.execute(
            "SELECT language, COUNT(*) AS count FROM files WHERE module = ? GROUP BY language ORDER BY count DESC, language LIMIT 6",
            (module,),
        ))
        language_text = ", ".join(f"{row['language']} ({row['count']})" for row in language_rows)
        key_files = list(conn.execute(
            "SELECT path, entrypoint_score, line_count FROM files WHERE module = ? ORDER BY entrypoint_score DESC, line_count DESC, path LIMIT 6",
            (module,),
        ))
        lines.append(f"### `{module}`")
        lines.append("")
        lines.append(f"- Files: **{item['files']}**; lines: **{item['lines']}**")
        lines.append(f"- Languages/formats: {language_text or 'unknown'}")
        if key_files:
            lines.append("- Orientation files:")
            for row in key_files:
                lines.append(f"  - `{row['path']}`")
        lines.append("")
    lines.extend(["## Common import targets", ""])
    import_rows = list(conn.execute(
        "SELECT target, COUNT(*) AS count FROM imports GROUP BY target ORDER BY count DESC, target LIMIT 30"
    ))
    if import_rows:
        for row in import_rows:
            lines.append(f"- `{row['target']}` — referenced from {row['count']} indexed locations")
    else:
        lines.append("- No language imports were extracted.")
    lines.extend(["", "## Strong entrypoint candidates", ""])
    entries = list(conn.execute(
        "SELECT path, language, entrypoint_score FROM files WHERE entrypoint_score > 0 ORDER BY entrypoint_score DESC, path LIMIT 25"
    ))
    if entries:
        for row in entries:
            lines.append(f"- `{row['path']}` — {row['language']}, score {row['entrypoint_score']:.1f}")
    else:
        lines.append("- No strong entrypoint candidates detected.")
    return "\n".join(lines) + "\n"


def build_file_map(conn: sqlite3.Connection, stats: Mapping[str, object], snapshot: int) -> str:
    lines = [
        "# File map",
        "",
        f"> Snapshot {snapshot}. Full records are stored in `cache/index.sqlite3`.",
        "",
        "## Modules",
        "",
        "| Module | Files | Lines |",
        "|---|---:|---:|",
    ]
    for item in stats.get("modules", []):
        lines.append(f"| `{item['module']}` | {item['files']} | {item['lines']} |")
    lines.extend(["", "## Indexed files", ""])
    rows = list(conn.execute(
        "SELECT path, category, language, line_count FROM files ORDER BY module, path LIMIT ?",
        (MAX_GENERATED_FILE_LIST,),
    ))
    current_module: Optional[str] = None
    for row in rows:
        module = top_module(str(row["path"]))
        if module != current_module:
            lines.extend([f"### `{module}`", ""])
            current_module = module
        lines.append(f"- `{row['path']}` — {row['language']}; {row['category']}; {row['line_count']} lines")
    total = int(stats.get("files", 0))
    if total > len(rows):
        lines.extend(["", f"_The Markdown view is capped at {len(rows)} of {total} files. Query the SQLite index for the complete map._"])
    return "\n".join(lines) + "\n"


def safe_module_filename(module: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", module).strip(".-") or "root"
    digest = hashlib.sha1(module.encode("utf-8")).hexdigest()[:8]
    return f"{slug[:80]}-{digest}.md"


def generate_module_views(module_dir: Path, conn: sqlite3.Connection, snapshot: int) -> None:
    module_dir.mkdir(parents=True, exist_ok=True)
    expected: Set[str] = set()
    modules = [str(row[0]) for row in conn.execute("SELECT DISTINCT module FROM files ORDER BY module")]
    for module in modules:
        filename = safe_module_filename(module)
        expected.add(filename)
        file_rows = list(conn.execute(
            "SELECT path, language, category, line_count, entrypoint_score FROM files WHERE module = ? ORDER BY entrypoint_score DESC, line_count DESC, path LIMIT 80",
            (module,),
        ))
        symbol_rows = list(conn.execute(
            "SELECT s.file_path, s.kind, s.name, s.line FROM symbols s JOIN files f ON f.path = s.file_path WHERE f.module = ? ORDER BY s.file_path, s.line LIMIT 120",
            (module,),
        ))
        heading_rows = list(conn.execute(
            "SELECT h.file_path, h.level, h.title, h.line FROM headings h JOIN files f ON f.path = h.file_path WHERE f.module = ? ORDER BY h.file_path, h.line LIMIT 80",
            (module,),
        ))
        language_rows = list(conn.execute(
            "SELECT language, COUNT(*) AS count FROM files WHERE module = ? GROUP BY language ORDER BY count DESC, language",
            (module,),
        ))
        language_summary = ", ".join(f"{r['language']} ({r['count']})" for r in language_rows)
        lines = [
            f"# Module `{module}`",
            "",
            f"> Structural view from snapshot {snapshot}. Confirm responsibilities from source files.",
            "",
            f"- Indexed files: **{len(file_rows)}** shown",
            f"- Languages/formats: {language_summary}",
            "",
            "## Key files",
            "",
        ]
        for row in file_rows[:30]:
            lines.append(f"- `{row['path']}` — {row['language']}; {row['category']}; {row['line_count']} lines")
        lines.extend(["", "## Extracted symbols", ""])
        if symbol_rows:
            for row in symbol_rows:
                lines.append(f"- `{row['name']}` ({row['kind']}) — `{row['file_path']}:{row['line']}`")
        else:
            lines.append("- No symbols extracted.")
        lines.extend(["", "## Document headings", ""])
        if heading_rows:
            for row in heading_rows:
                lines.append(f"- {'#' * max(1, min(6, int(row['level'])))} {row['title']} — `{row['file_path']}:{row['line']}`")
        else:
            lines.append("- No document headings extracted.")
        atomic_write_text(module_dir / filename, "\n".join(lines) + "\n")
    for path in module_dir.glob("*.md"):
        if path.name not in expected:
            with contextlib.suppress(OSError):
                path.unlink()


def load_structural_maps(conn: sqlite3.Connection) -> Tuple[Dict[str, List[sqlite3.Row]], Dict[str, List[sqlite3.Row]], Dict[str, List[sqlite3.Row]]]:
    symbols: Dict[str, List[sqlite3.Row]] = collections.defaultdict(list)
    headings: Dict[str, List[sqlite3.Row]] = collections.defaultdict(list)
    imports: Dict[str, List[sqlite3.Row]] = collections.defaultdict(list)
    for row in conn.execute("SELECT file_path, kind, name, line, signature FROM symbols ORDER BY file_path, line"):
        symbols[str(row["file_path"])].append(row)
    for row in conn.execute("SELECT file_path, level, title, line FROM headings ORDER BY file_path, line"):
        headings[str(row["file_path"])].append(row)
    for row in conn.execute("SELECT file_path, target, line FROM imports ORDER BY file_path, line"):
        imports[str(row["file_path"])].append(row)
    return symbols, headings, imports


def score_files(conn: sqlite3.Connection, task: str) -> List[Dict[str, object]]:
    terms = task_terms(task)
    task_lower = task.casefold()
    symbols_map, headings_map, imports_map = load_structural_maps(conn)
    recent_changes = {
        str(row[0]) for row in conn.execute(
            "SELECT path FROM changes WHERE snapshot = (SELECT MAX(snapshot) FROM changes)"
        )
    }
    scored: List[Dict[str, object]] = []
    for row in conn.execute("SELECT * FROM files"):
        path = str(row["path"])
        path_lower = path.casefold()
        file_terms = {str(item[0]): int(item[1]) for item in json.loads(str(row["search_terms"]))}
        score = 0.0
        reasons: List[str] = []
        basename = path.rsplit("/", 1)[-1].casefold()
        stem = basename.rsplit(".", 1)[0]
        if basename and basename in task_lower:
            score += 18.0
            reasons.append("filename appears in task")
        if stem and len(stem) >= 3 and stem in task_lower:
            score += 10.0
            reasons.append("file stem appears in task")
        path_hits = [term for term in terms if term in path_lower]
        if path_hits:
            score += min(24.0, 7.0 * len(path_hits))
            reasons.append("path matches " + ", ".join(sorted(path_hits)[:4]))
        lexical_hits: List[Tuple[str, int]] = []
        for term in terms:
            if term in file_terms:
                lexical_hits.append((term, file_terms[term]))
                score += min(6.0, 1.0 + file_terms[term] ** 0.5)
        if lexical_hits:
            lexical_hits.sort(key=lambda x: (-x[1], x[0]))
            reasons.append("indexed terms match " + ", ".join(term for term, _ in lexical_hits[:5]))
        symbol_hits = [
            str(s["name"]) for s in symbols_map.get(path, [])
            if any(term in str(s["name"]).casefold() for term in terms)
        ]
        if symbol_hits:
            score += min(30.0, 10.0 * len(symbol_hits))
            reasons.append("symbols match " + ", ".join(symbol_hits[:4]))
        heading_hits = [
            str(h["title"]) for h in headings_map.get(path, [])
            if any(term in str(h["title"]).casefold() for term in terms)
        ]
        if heading_hits:
            score += min(20.0, 7.0 * len(heading_hits))
            reasons.append("headings match " + ", ".join(heading_hits[:3]))
        import_hits = [
            str(i["target"]) for i in imports_map.get(path, [])
            if any(term in str(i["target"]).casefold() for term in terms)
        ]
        if import_hits:
            score += min(12.0, 4.0 * len(import_hits))
            reasons.append("imports match " + ", ".join(import_hits[:3]))
        if path in recent_changes:
            score += 2.0
            reasons.append("changed in latest snapshot")
        score += min(2.0, float(row["entrypoint_score"]) * 0.1)
        if score > 0:
            scored.append({
                "path": path,
                "score": round(score, 3),
                "reasons": reasons,
                "language": str(row["language"]),
                "category": str(row["category"]),
                "line_count": int(row["line_count"]),
                "symbols": symbols_map.get(path, []),
                "headings": headings_map.get(path, []),
                "imports": imports_map.get(path, []),
                "entrypoint_score": float(row["entrypoint_score"]),
            })
    scored.sort(key=lambda item: (-float(item["score"]), -float(item["entrypoint_score"]), str(item["path"])))
    if not scored:
        for row in conn.execute(
            "SELECT * FROM files ORDER BY entrypoint_score DESC, CASE WHEN category='documentation' THEN 0 ELSE 1 END, line_count DESC, path LIMIT 20"
        ):
            path = str(row["path"])
            scored.append({
                "path": path,
                "score": round(float(row["entrypoint_score"]), 3),
                "reasons": ["orientation fallback"],
                "language": str(row["language"]),
                "category": str(row["category"]),
                "line_count": int(row["line_count"]),
                "symbols": symbols_map.get(path, []),
                "headings": headings_map.get(path, []),
                "imports": imports_map.get(path, []),
                "entrypoint_score": float(row["entrypoint_score"]),
            })
    return scored


def find_excerpt(text: str, terms: Set[str], preferred_lines: Sequence[int], max_lines: int = 26) -> Tuple[int, int, str]:
    lines = text.splitlines()
    if not lines:
        return 1, 1, ""
    hit_line: Optional[int] = None
    for i, line in enumerate(lines, start=1):
        lower = line.casefold()
        if any(term in lower for term in terms):
            hit_line = i
            break
    if hit_line is None and preferred_lines:
        hit_line = max(1, int(preferred_lines[0]))
    if hit_line is None:
        hit_line = 1
    half = max_lines // 2
    start = max(1, hit_line - half)
    end = min(len(lines), start + max_lines - 1)
    start = max(1, end - max_lines + 1)
    excerpt_lines = []
    for lineno in range(start, end + 1):
        line = lines[lineno - 1]
        if len(line) > 500:
            line = line[:497] + "..."
        excerpt_lines.append(f"{lineno:>5} | {line}")
    return start, end, "\n".join(excerpt_lines)


def relevant_knowledge_notes(cognition_dir: Path, task: str, max_notes: int = 3) -> List[Tuple[Path, str]]:
    terms = task_terms(task)
    scored: List[Tuple[float, Path, str]] = []
    knowledge_dir = cognition_dir / "knowledge"
    if not knowledge_dir.exists():
        return []
    for path in knowledge_dir.rglob("*.md"):
        if path.name == "README.md":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        lower = (path.as_posix() + "\n" + text[:50_000]).casefold()
        hits = sum(1 for term in terms if term in lower)
        if hits:
            scored.append((float(hits), path, text))
    scored.sort(key=lambda item: (-item[0], item[1].as_posix()))
    return [(path, text) for _, path, text in scored[:max_notes]]


def prune_context_packs(context_dir: Path) -> None:
    files = sorted(
        [p for p in context_dir.glob("*.md") if p.name != "current.md"],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for path in files[MAX_CONTEXT_PACKS:]:
        with contextlib.suppress(OSError):
            path.unlink()


def generate_context_pack(
    root: Path,
    task: str,
    max_files: int,
    max_chars: int,
    max_file_size: int,
) -> Dict[str, object]:
    max_chars = max(2000, max_chars)
    prepare_result = prepare_project(root, max_file_size=max_file_size)
    cognition_dir = root / COGNITION_DIRNAME
    conn = connect_db(cognition_dir / DB_RELATIVE)
    try:
        scored = score_files(conn, task)
        selected = scored[:max(1, max_files)]
        terms = task_terms(task)
        snapshot = int(get_meta(conn, "snapshot") or "0")
        git = git_info(root)
        lines: List[str] = [
            "# Task context pack",
            "",
            f"- Task: {task}",
            f"- Project: `{root}`",
            f"- Cognition snapshot: **{snapshot}**",
            f"- Generated: `{utc_now()}`",
        ]
        if git.get("is_git"):
            lines.append(f"- Git: `{git.get('branch')}` at `{str(git.get('head') or '')[:12]}`; dirty={str(bool(git.get('dirty'))).lower()}")
        lines.extend([
            "",
            "> Use this pack for navigation. Verify important claims and all edits against the original files.",
            "",
            "## Selected files",
            "",
        ])
        for item in selected:
            reasons = "; ".join(str(r) for r in item["reasons"])
            lines.append(f"- `{item['path']}` — score {item['score']}; {reasons}")

        char_budget = max_chars
        used = len("\n".join(lines))
        included_files: List[Dict[str, object]] = []
        for item in selected:
            path = root / Path(str(item["path"]))
            try:
                text = redact_sensitive_lines(
                    read_text_safely(path, max_chars=max(10_000, min(DEFAULT_MAX_INDEX_CHARS, max_chars)))
                )
            except OSError:
                continue
            preferred_lines = [int(s["line"]) for s in item["symbols"][:3]] + [int(h["line"]) for h in item["headings"][:3]]
            start, end, excerpt = find_excerpt(text, terms, preferred_lines)
            symbols = item["symbols"][:12]
            headings = item["headings"][:10]
            imports = item["imports"][:12]
            section_lines = [
                "",
                f"## `{item['path']}`",
                "",
                f"- Language/format: {item['language']}",
                f"- Category: {item['category']}",
                f"- Lines: {item['line_count']}",
                f"- Selection reason: {'; '.join(str(r) for r in item['reasons'])}",
            ]
            if symbols:
                section_lines.append("- Symbols: " + ", ".join(f"`{s['name']}`@{s['line']}" for s in symbols))
            if headings:
                section_lines.append("- Headings: " + "; ".join(f"{h['title']}@{h['line']}" for h in headings))
            if imports:
                section_lines.append("- Imports/includes: " + ", ".join(f"`{i['target']}`" for i in imports))
            fence = "text"
            section_lines.extend([
                "",
                f"Excerpt `{item['path']}:{start}-{end}`:",
                "",
                f"```{fence}",
                excerpt,
                "```",
            ])
            section = "\n".join(section_lines)
            remaining = char_budget - used
            if remaining <= 800:
                break
            if len(section) > remaining:
                section = section[: max(0, remaining - 80)] + "\n\n_[Context pack character limit reached.]_"
            lines.append(section)
            used += len(section)
            included_files.append({
                "path": item["path"],
                "score": item["score"],
                "excerpt": {"start": start, "end": end},
            })
            if used >= char_budget:
                break

        notes = relevant_knowledge_notes(cognition_dir, task)
        if notes and used < char_budget - 800:
            lines.extend(["", "## Relevant durable notes", ""])
            for note_path, note_text in notes:
                rel = note_path.relative_to(cognition_dir).as_posix()
                excerpt = note_text[:3000]
                section = f"### `{rel}`\n\n{excerpt}"
                if used + len(section) > char_budget:
                    break
                lines.append(section)
                used += len(section)

        lines.extend([
            "",
            "## Agent checklist",
            "",
            "- Open the original selected files before changing them.",
            "- Search beyond this pack when evidence points to unselected callers, tests, configuration, or documentation.",
            "- Refresh cognition after completing a coherent edit batch.",
        ])
        content = "\n".join(lines).rstrip() + "\n"
        if len(content) > max_chars:
            content = content[: max_chars - 80].rstrip() + "\n\n_[Context pack truncated at configured limit.]_\n"
        digest = hashlib.sha256(task.encode("utf-8")).hexdigest()[:10]
        context_dir = cognition_dir / "context-packs"
        context_dir.mkdir(parents=True, exist_ok=True)
        timestamped = context_dir / f"{local_stamp()}-{digest}.md"
        atomic_write_text(timestamped, content)
        atomic_write_text(context_dir / "current.md", content)
        prune_context_packs(context_dir)
        return {
            "command": "context",
            "state": "ready",
            "project_root": str(root),
            "snapshot": snapshot,
            "prepare_state": prepare_result.get("state"),
            "context_path": str(timestamped),
            "current_context_path": str(context_dir / "current.md"),
            "selected_files": included_files,
            "characters": len(content),
            "task_terms": sorted(terms)[:100],
        }
    finally:
        conn.close()


def inspect_status(root: Path, max_file_size: int) -> Dict[str, object]:
    cognition_dir = root / COGNITION_DIRNAME
    db_path = cognition_dir / DB_RELATIVE
    if not db_path.exists():
        return {
            "command": "status",
            "state": "not_initialized",
            "project_root": str(root),
            "cognition_dir": str(cognition_dir),
        }
    conn = connect_db(db_path)
    try:
        existing = load_existing_files(conn)
        discovered, discovery_stats = discover_files(root, load_ignore_patterns(), max_file_size)
        discovered_meta: Dict[str, Tuple[int, int]] = {}
        for path in discovered:
            rel = safe_relative(path, root)
            if rel is None:
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            discovered_meta[rel] = (stat.st_size, stat.st_mtime_ns)
        old_paths = set(existing)
        new_paths = set(discovered_meta)
        stale_paths: List[str] = []
        for rel in sorted(old_paths & new_paths):
            size, mtime_ns = discovered_meta[rel]
            row = existing[rel]
            if int(row["size"]) != size or int(row["mtime_ns"]) != mtime_ns:
                stale_paths.append(rel)
        added = sorted(new_paths - old_paths)
        deleted = sorted(old_paths - new_paths)
        stale = bool(stale_paths or added or deleted)
        return {
            "command": "status",
            "state": "stale_by_metadata" if stale else "clean_by_metadata",
            "project_root": str(root),
            "snapshot": int(get_meta(conn, "snapshot") or "0"),
            "indexed_files": len(existing),
            "possible_modified": stale_paths[:100],
            "possible_added": added[:100],
            "possible_deleted": deleted[:100],
            "git": git_info(root),
            "discovery": discovery_stats,
            "note": "Run prepare for content-hash verification." if stale else "No path, size, or mtime differences detected.",
        }
    finally:
        conn.close()


def validate_project(root: Path, deep: bool = False) -> Dict[str, object]:
    cognition_dir = root / COGNITION_DIRNAME
    db_path = cognition_dir / DB_RELATIVE
    issues: List[Dict[str, object]] = []
    if not db_path.exists():
        return {
            "command": "validate",
            "state": "not_initialized",
            "project_root": str(root),
            "issues": [{"type": "missing_index", "path": str(db_path)}],
        }
    conn = connect_db(db_path)
    try:
        integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
        if integrity.lower() != "ok":
            issues.append({"type": "sqlite_integrity", "detail": integrity})
        schema = int(get_meta(conn, "schema_version") or "-1")
        if schema != SCHEMA_VERSION:
            issues.append({"type": "schema_mismatch", "found": schema, "expected": SCHEMA_VERSION})
        stored_root = get_meta(conn, "project_root")
        if not stored_root or Path(stored_root).resolve() != root.resolve():
            issues.append({"type": "project_root_mismatch", "stored": stored_root, "current": str(root)})
        for required in (
            cognition_dir / "START_HERE.md",
            cognition_dir / "manifest.json",
            cognition_dir / "generated" / "architecture.md",
            cognition_dir / "generated" / "current-state.md",
            cognition_dir / "generated" / "file-map.md",
        ):
            if not required.exists():
                issues.append({"type": "missing_generated_file", "path": str(required)})
        missing_paths: List[str] = []
        hash_mismatches: List[str] = []
        for row in conn.execute("SELECT path, sha256 FROM files ORDER BY path"):
            rel = str(row["path"])
            path = root / Path(rel)
            if not path.exists():
                missing_paths.append(rel)
                continue
            if deep:
                try:
                    digest = hash_file(path)
                except OSError:
                    hash_mismatches.append(rel)
                    continue
                if digest != str(row["sha256"]):
                    hash_mismatches.append(rel)
        if missing_paths:
            issues.append({"type": "missing_source_files", "paths": missing_paths[:100]})
        if hash_mismatches:
            issues.append({"type": "hash_mismatch", "paths": hash_mismatches[:100]})
        state = "valid" if not issues else "invalid"
        return {
            "command": "validate",
            "state": state,
            "project_root": str(root),
            "snapshot": int(get_meta(conn, "snapshot") or "0"),
            "deep": deep,
            "sqlite_integrity": integrity,
            "issues": issues,
            "recommended_action": None if not issues else "Run prepare; use rebuild if issues remain.",
        }
    finally:
        conn.close()


def rebuild_project(root: Path, max_file_size: int) -> Dict[str, object]:
    cognition_dir = root / COGNITION_DIRNAME
    ensure_output_layout(cognition_dir)
    lock_path = cognition_dir / ".write.lock"
    with ProjectLock(lock_path):
        for target in (
            cognition_dir / "START_HERE.md",
            cognition_dir / "manifest.json",
            cognition_dir / "generated",
            cognition_dir / "context-packs",
            cognition_dir / "cache",
        ):
            if target.is_dir():
                shutil.rmtree(target, ignore_errors=False)
            elif target.exists():
                target.unlink()
        ensure_output_layout(cognition_dir)
    result = prepare_project(root, max_file_size=max_file_size, force=True)
    result["command"] = "rebuild"
    result["state"] = "rebuilt"
    return result


def install_entry(root: Path) -> Dict[str, object]:
    agents_path = root / "AGENTS.md"
    existing = ""
    if agents_path.exists():
        existing = agents_path.read_text(encoding="utf-8")
    pattern = re.compile(
        re.escape(MANAGED_ENTRY_START) + r".*?" + re.escape(MANAGED_ENTRY_END),
        re.DOTALL,
    )
    if pattern.search(existing):
        updated = pattern.sub(MANAGED_ENTRY, existing)
        action = "updated"
    else:
        separator = "\n\n" if existing.strip() else ""
        updated = existing.rstrip() + separator + MANAGED_ENTRY + "\n"
        action = "installed"
    atomic_write_text(agents_path, updated)
    return {
        "command": "install-entry",
        "state": action,
        "project_root": str(root),
        "agents_path": str(agents_path),
    }


def remove_entry(root: Path) -> Dict[str, object]:
    agents_path = root / "AGENTS.md"
    if not agents_path.exists():
        return {
            "command": "remove-entry",
            "state": "not_present",
            "project_root": str(root),
            "agents_path": str(agents_path),
        }
    existing = agents_path.read_text(encoding="utf-8")
    pattern = re.compile(
        r"\n*" + re.escape(MANAGED_ENTRY_START) + r".*?" + re.escape(MANAGED_ENTRY_END) + r"\n*",
        re.DOTALL,
    )
    updated, count = pattern.subn("\n", existing)
    if count:
        updated = updated.strip() + ("\n" if updated.strip() else "")
        atomic_write_text(agents_path, updated)
        state = "removed"
    else:
        state = "not_present"
    return {
        "command": "remove-entry",
        "state": state,
        "project_root": str(root),
        "agents_path": str(agents_path),
    }


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="project_cognition.py",
        description="Build and query a persistent incremental structural index for a project.",
    )
    parser.add_argument("--compact-json", action="store_true", help="Print compact JSON output.")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(command_parser: argparse.ArgumentParser) -> None:
        command_parser.add_argument("--project", default=".", help="Project path. Git root is used when detected.")
        command_parser.add_argument(
            "--max-file-size",
            type=positive_int,
            default=DEFAULT_MAX_FILE_SIZE,
            help=f"Maximum indexed file size in bytes (default: {DEFAULT_MAX_FILE_SIZE}).",
        )

    prepare_parser = sub.add_parser("prepare", help="Initialize or incrementally refresh project cognition.")
    common(prepare_parser)
    prepare_parser.add_argument("--force", action="store_true", help="Reparse all eligible files even when hashes match.")

    context_parser = sub.add_parser("context", help="Refresh cognition and build a task-specific context pack.")
    common(context_parser)
    context_parser.add_argument("--task", required=True, help="Current task used for retrieval.")
    context_parser.add_argument("--max-files", type=positive_int, default=DEFAULT_CONTEXT_FILES)
    context_parser.add_argument("--max-chars", type=positive_int, default=DEFAULT_CONTEXT_CHARS)

    status_parser = sub.add_parser("status", help="Check initialization and metadata-level staleness without updating.")
    common(status_parser)

    validate_parser = sub.add_parser("validate", help="Validate cognition database and generated views.")
    common(validate_parser)
    validate_parser.add_argument("--deep", action="store_true", help="Hash every indexed source file.")

    rebuild_parser = sub.add_parser("rebuild", help="Rebuild machine-owned cognition while preserving knowledge notes.")
    common(rebuild_parser)

    install_parser = sub.add_parser("install-entry", help="Add an idempotent project-cognition block to AGENTS.md.")
    install_parser.add_argument("--project", default=".")

    remove_parser = sub.add_parser("remove-entry", help="Remove the managed project-cognition block from AGENTS.md.")
    remove_parser.add_argument("--project", default=".")

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        root = resolve_project_root(args.project)
        if args.command == "prepare":
            result = prepare_project(root, max_file_size=args.max_file_size, force=args.force)
        elif args.command == "context":
            result = generate_context_pack(
                root,
                task=args.task,
                max_files=args.max_files,
                max_chars=args.max_chars,
                max_file_size=args.max_file_size,
            )
        elif args.command == "status":
            result = inspect_status(root, max_file_size=args.max_file_size)
        elif args.command == "validate":
            result = validate_project(root, deep=args.deep)
        elif args.command == "rebuild":
            result = rebuild_project(root, max_file_size=args.max_file_size)
        elif args.command == "install-entry":
            result = install_entry(root)
        elif args.command == "remove-entry":
            result = remove_entry(root)
        else:
            parser.error(f"Unknown command: {args.command}")
            return 2
        print(json_dumps(result, pretty=not args.compact_json))
        invalid_states = {"failed", "invalid", "rebuild_required"}
        return 1 if str(result.get("state")) in invalid_states else 0
    except (CognitionError, OSError, sqlite3.Error, ValueError) as exc:
        error = {
            "command": getattr(args, "command", None),
            "state": "failed",
            "error_type": exc.__class__.__name__,
            "error": str(exc),
        }
        print(json_dumps(error, pretty=not getattr(args, "compact_json", False)))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
