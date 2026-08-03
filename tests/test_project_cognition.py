from __future__ import annotations

import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "project_cognition.py"
SPEC = importlib.util.spec_from_file_location("project_cognition", MODULE_PATH)
assert SPEC and SPEC.loader
pc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pc)


class ProjectCognitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        (self.root / "src").mkdir()
        (self.root / "tests").mkdir()
        (self.root / "README.md").write_text(
            "# Demo\n\n## Architecture\n\nThe parser calls the formatter.\n",
            encoding="utf-8",
        )
        (self.root / "src" / "parser.py").write_text(
            "from .formatter import format_value\n\n"
            "def parse_value(value: str) -> str:\n"
            "    return format_value(value.strip())\n",
            encoding="utf-8",
        )
        (self.root / "src" / "formatter.py").write_text(
            "def format_value(value: str) -> str:\n"
            "    return value.upper()\n",
            encoding="utf-8",
        )
        (self.root / "tests" / "test_parser.py").write_text(
            "from src.parser import parse_value\n\n"
            "def test_parse_value():\n"
            "    assert parse_value(' x ') == 'X'\n",
            encoding="utf-8",
        )
        (self.root / ".env").write_text("API_KEY=top-secret\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _db_paths(self):
        db = self.root / ".project-cognition" / "cache" / "index.sqlite3"
        conn = sqlite3.connect(db)
        try:
            return {row[0] for row in conn.execute("SELECT path FROM files")}
        finally:
            conn.close()

    def test_prepare_incremental_rename_context_and_validate(self) -> None:
        first = pc.prepare_project(self.root)
        self.assertEqual(first["state"], "initialized")
        self.assertEqual(first["indexed_files"], 4)
        self.assertNotIn(".env", self._db_paths())
        snapshot1 = first["snapshot"]

        second = pc.prepare_project(self.root)
        self.assertEqual(second["state"], "clean")
        self.assertEqual(second["snapshot"], snapshot1)

        formatter = self.root / "src" / "formatter.py"
        formatter.write_text(
            "def format_value(value: str) -> str:\n"
            "    return value.casefold()\n",
            encoding="utf-8",
        )
        third = pc.prepare_project(self.root)
        self.assertEqual(third["state"], "updated")
        self.assertEqual(third["changes"]["modified"], 1)
        self.assertGreater(third["snapshot"], snapshot1)

        renamed = self.root / "src" / "text_formatter.py"
        formatter.rename(renamed)
        fourth = pc.prepare_project(self.root)
        self.assertEqual(fourth["changes"]["renamed"], 1)
        self.assertIn("src/text_formatter.py", self._db_paths())
        self.assertNotIn("src/formatter.py", self._db_paths())

        context = pc.generate_context_pack(
            self.root,
            task="Fix text formatter and parser integration",
            max_files=6,
            max_chars=20_000,
            max_file_size=pc.DEFAULT_MAX_FILE_SIZE,
        )
        selected = [item["path"] for item in context["selected_files"]]
        self.assertIn("src/text_formatter.py", selected)
        self.assertTrue(Path(context["context_path"]).exists())

        validation = pc.validate_project(self.root, deep=True)
        self.assertEqual(validation["state"], "valid")

    def test_status_detects_stale_metadata(self) -> None:
        pc.prepare_project(self.root)
        status = pc.inspect_status(self.root, pc.DEFAULT_MAX_FILE_SIZE)
        self.assertEqual(status["state"], "clean_by_metadata")
        (self.root / "src" / "parser.py").write_text("def changed():\n    return True\n", encoding="utf-8")
        stale = pc.inspect_status(self.root, pc.DEFAULT_MAX_FILE_SIZE)
        self.assertEqual(stale["state"], "stale_by_metadata")
        self.assertIn("src/parser.py", stale["possible_modified"])

    def test_rebuild_preserves_knowledge(self) -> None:
        pc.prepare_project(self.root)
        note = self.root / ".project-cognition" / "knowledge" / "notes" / "architecture.md"
        note.write_text("# Decision\n\nParser owns normalization.\n", encoding="utf-8")
        rebuilt = pc.rebuild_project(self.root, pc.DEFAULT_MAX_FILE_SIZE)
        self.assertEqual(rebuilt["state"], "rebuilt")
        self.assertTrue(note.exists())
        self.assertIn("Parser owns normalization", note.read_text(encoding="utf-8"))

    def test_agents_entry_is_idempotent_and_removable(self) -> None:
        agents = self.root / "AGENTS.md"
        agents.write_text("# Existing instructions\n", encoding="utf-8")
        first = pc.install_entry(self.root)
        second = pc.install_entry(self.root)
        self.assertEqual(first["state"], "installed")
        self.assertEqual(second["state"], "updated")
        text = agents.read_text(encoding="utf-8")
        self.assertEqual(text.count(pc.MANAGED_ENTRY_START), 1)
        removed = pc.remove_entry(self.root)
        self.assertEqual(removed["state"], "removed")
        self.assertNotIn(pc.MANAGED_ENTRY_START, agents.read_text(encoding="utf-8"))
        self.assertIn("Existing instructions", agents.read_text(encoding="utf-8"))

    def test_manifest_retains_latest_content_changes_after_clean_prepare(self) -> None:
        first = pc.prepare_project(self.root)
        self.assertEqual(first["changes"]["added"], 4)
        pc.prepare_project(self.root)
        manifest = json.loads((self.root / ".project-cognition" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["last_changes"]), 4)
        start = (self.root / ".project-cognition" / "START_HERE.md").read_text(encoding="utf-8")
        self.assertIn("added 4", start)


if __name__ == "__main__":
    unittest.main()
