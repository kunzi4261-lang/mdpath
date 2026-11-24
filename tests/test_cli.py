import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from mdpath import Report, check_link


CLI = Path(__file__).resolve().parents[1] / "mdpath.py"


class CliTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "repo"
        self.root.mkdir()

    def write(self, name, content=""):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(CLI), *args], cwd=self.root,
            capture_output=True, text=True, encoding="utf-8",
        )

    def report(self, code, *args):
        result = self.run_cli("--json", *args)
        self.assertEqual(result.returncode, code, result.stderr)
        return json.loads(result.stdout)

    def test_resolves_source_and_repo_relative_paths(self):
        self.write("docs/资料 一.txt")
        self.write("README.md", "[dir](docs/)")
        self.write(
            "docs/notes.MARKDOWN",
            "[home](/README.md#example) [asset](资料%20一.txt?download=1)\n"
            "[parent](../README.md) [self](#section) [query](?plain=1)\n"
            "[web](https://example.org/a) [host](//example.org/a) [mail](mailto:a@b.c)",
        )
        self.assertEqual(self.report(0), {"files": 2, "links": 4, "broken": [], "errors": []})

    def test_reports_missing_and_outside_paths_in_order(self):
        (self.root.parent / "secret.txt").write_text("example", encoding="utf-8")
        self.write("z.md", "[outside](%2E%2E/secret.txt)")
        self.write("a.md", "# Links\n\n![image](gone.png)")
        result = self.report(1, ".")
        self.assertEqual(result["broken"], [
            {"file": "a.md", "line": 3, "target": "gone.png", "reason": "missing"},
            {"file": "z.md", "line": 1, "target": "%2E%2E/secret.txt", "reason": "outside-root"},
        ])
        human = self.run_cli()
        self.assertEqual(human.returncode, 1)
        self.assertIn("a.md:3: missing: gone.png", human.stdout)

    def test_ignores_generated_files_but_scans_github_docs(self):
        for folder in ("node_modules", "docs/build", ".git", ".venv"):
            self.write(folder + "/README.md", "[bad](nonexistent)")
        self.write(".github/contributing.md")
        self.write("notes.txt", "[ignored](missing)")
        self.assertEqual(self.report(0)["files"], 1)

    def test_decoded_absolute_paths_are_rejected_before_lookup(self):
        report = Report()
        targets = ["%2F%2Fserver/share/doc.md", "%5C%5Cserver%5Cshare", "D%3A/notes"]
        with patch.object(Path, "resolve", side_effect=AssertionError("unexpected lookup")):
            for target in targets:
                check_link(self.root, self.root / "doc.md", 1, target, report)
        self.assertEqual([item["reason"] for item in report.broken], ["outside-root"] * 3)

    def test_reports_invalid_input_alongside_broken_links(self):
        (self.root / "bad.md").write_bytes(b"\xff")
        self.write("good.md", "[bad](absent)")
        result = self.report(2)
        self.assertEqual(result["files"], 1)
        self.assertEqual(result["errors"][0]["file"], "bad.md")
        self.assertEqual(len(result["broken"]), 1)

    def test_invalid_roots(self):
        self.write("file.md")
        for root in ("file.md", "does-not-exist"):
            with self.subTest(root=root):
                result = self.report(2, root)
                self.assertEqual(result["errors"][0]["file"], ".")

    def test_file_symlinks_are_skipped_and_external_target_is_flagged(self):
        external = self.root.parent / "external.md"
        external.write_text("[unread](missing)", encoding="utf-8")
        try:
            (self.root / "alias.md").symlink_to(external)
        except OSError as error:
            self.skipTest(f"symlink unavailable: {error}")
        self.write("README.md", "[external](alias.md)")
        result = self.report(1)
        self.assertEqual(result["files"], 1)
        self.assertEqual(result["broken"][0]["reason"], "outside-root")


if __name__ == "__main__":
    unittest.main()
