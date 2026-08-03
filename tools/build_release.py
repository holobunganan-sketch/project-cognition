#!/usr/bin/env python3
"""Build reproducible standalone-skill and skills-only-plugin release archives."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SKILL_FILES = [
    "SKILL.md",
    "README.md",
    "README.zh-CN.md",
    "INSTALL.zh-CN.md",
    "CHANGELOG.md",
    "LICENSE",
    "VERSION",
]
SKILL_DIRS = ["agents", "assets", "references", "scripts", "tests"]


def copy_tree_contents(source: Path, destination: Path) -> None:
    for item in sorted(source.iterdir(), key=lambda path: path.name):
        target = destination / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)


def copy_skill(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for relative in SKILL_FILES:
        shutil.copy2(ROOT / relative, destination / relative)
    for relative in SKILL_DIRS:
        shutil.copytree(ROOT / relative, destination / relative)


def write_zip(source_parent: Path, root_name: str, output_path: Path) -> None:
    root = source_parent / root_name
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(root.rglob("*")):
            if path.is_dir():
                continue
            arcname = path.relative_to(source_parent).as_posix()
            info = zipfile.ZipInfo(arcname, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build(output_dir: Path) -> list[Path]:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if not version:
        raise ValueError("VERSION is empty")

    output_dir.mkdir(parents=True, exist_ok=True)
    for old in output_dir.glob("project-cognition-*.zip"):
        old.unlink()

    standalone = output_dir / f"project-cognition-skill-v{version}.zip"
    plugin = output_dir / f"project-cognition-plugin-v{version}.zip"

    with tempfile.TemporaryDirectory(prefix="project-cognition-release-") as temp_value:
        temp = Path(temp_value)

        copy_skill(temp / "project-cognition")
        write_zip(temp, "project-cognition", standalone)

        plugin_root = temp / "project-cognition-plugin"
        metadata_dir = plugin_root / ".codex-plugin"
        metadata_dir.mkdir(parents=True, exist_ok=True)
        template = (ROOT / "packaging/plugin/plugin.json").read_text(encoding="utf-8")
        metadata = json.loads(template.replace("__VERSION__", version))
        (metadata_dir / "plugin.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        shutil.copy2(ROOT / "packaging/plugin/README.md", plugin_root / "README.md")
        shutil.copy2(ROOT / "packaging/plugin/README.zh-CN.md", plugin_root / "README.zh-CN.md")
        shutil.copytree(ROOT / "packaging/plugin/assets", plugin_root / "assets")
        copy_skill(plugin_root / "skills/project-cognition")
        write_zip(temp, "project-cognition-plugin", plugin)

    checksum_file = output_dir / "SHA256SUMS.txt"
    artifacts = [standalone, plugin]
    checksum_file.write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in artifacts), encoding="utf-8"
    )
    return [*artifacts, checksum_file]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="dist", help="Output directory")
    args = parser.parse_args()
    output = Path(args.output).resolve()
    for artifact in build(output):
        print(artifact)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
