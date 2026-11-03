from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PREPARE = ROOT / "tools/release/prepare.py"


class PreparationTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source"
        self.distribution = self.root / "distribution"
        self.output = self.root / "output"
        self.message = self.root / "message"
        self.outputs = self.root / "github-output"
        self.summary = self.root / "summary"
        self.env = {
            **os.environ,
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
            "GITHUB_OUTPUT": str(self.outputs),
            "GITHUB_STEP_SUMMARY": str(self.summary),
        }
        for repository in (self.source, self.distribution):
            self.git(self.root, "init", "--quiet", str(repository))
        for name, content in {
            "README.md": "Runtime documentation\n",
            "LICENSE": "License\n",
            "package.json": json.dumps({"name": "example", "scripts": {}}),
            ".claude-plugin/marketplace.json": '{"plugins": []}',
            ".agents/plugins/marketplace.json": '{"plugins": []}',
            "plugins/demo/README.md": "Old plugin documentation\n",
        }.items():
            self.write(name, content)
        self.base = self.commit("feat: initial runtime")
        initial = self.root / "initial"
        self.run_command(
            sys.executable,
            str(ROOT / "tools/release/build.py"),
            "--source",
            str(self.source),
            "--output",
            str(initial),
        )
        self.run_command(
            "bash",
            str(ROOT / "tools/release/replace.sh"),
            str(initial),
            str(self.distribution),
        )
        self.git(self.distribution, "commit", "--quiet", "-m", "release")
        self.previous_commit = self.git(self.distribution, "rev-parse", "HEAD")

    def run_command(self, *args: str) -> str:
        return subprocess.run(
            args,
            env=self.env,
            text=True,
            capture_output=True,
            check=True,
            timeout=30,
        ).stdout.strip()

    def git(self, repository: Path, *args: str) -> str:
        return self.run_command("git", "-C", str(repository), *args)

    def write(self, name: str, content: str) -> None:
        path = self.source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def commit(self, message: str) -> str:
        self.git(self.source, "add", "--all")
        self.git(self.source, "commit", "--quiet", "--allow-empty", "-m", message)
        return self.git(self.source, "rev-parse", "HEAD")

    def prepare(self, revision: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(PREPARE),
                "--source",
                str(self.source),
                "--distribution",
                str(self.distribution),
                "--revision=" + revision,
                "--output",
                str(self.output),
                "--message",
                str(self.message),
            ],
            env=self.env,
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )

    def decision(self) -> dict[str, str]:
        return dict(
            line.split("=", 1) for line in self.outputs.read_text().splitlines()
        )

    def assert_unpublished(self) -> None:
        self.assertEqual(
            self.git(self.distribution, "rev-parse", "HEAD"), self.previous_commit
        )
        self.assertEqual(
            self.git(self.distribution, "show", "HEAD:SOURCE_REVISION"), self.base
        )
        self.assertFalse(self.message.exists())
        self.assertEqual(self.git(self.distribution, "status", "--porcelain"), "")

    def test_prepares_runtime_changes_with_counts_message_and_summary(self) -> None:
        self.write("tests/example.py", "development only")
        self.commit("test: cover the next change")
        self.write("README.md", "Updated runtime documentation\n")
        (self.source / "plugins/demo/README.md").unlink()
        self.write("plugins/new/README.md", "New plugin documentation\n")
        revision = self.commit("feat: update runtime\n\nUseful description.")
        result = self.prepare(revision)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.decision()["publish"], "true")
        summary = self.summary.read_text()
        self.assertIn(f"{self.base[:7]}..{revision[:7]}", summary)
        # The generated root package also changes its list of distributed files.
        self.assertIn("1 added, 2 modified, 1 deleted", summary)
        self.assertIn("Publication required", summary)
        self.assertIn("Useful description.", self.message.read_text())
        self.assertIn("test: cover the next change", self.message.read_text())
        self.assertFalse((self.distribution / "tests").exists())
        self.assertEqual(
            self.git(self.distribution, "show", ":SOURCE_REVISION"), revision
        )
        self.assertEqual(
            self.git(self.distribution, "rev-parse", "HEAD"), self.previous_commit
        )

    def test_skips_development_changes_and_manifest_fields_removed_by_builder(
        self,
    ) -> None:
        self.write("tests/example.py", "development only")
        self.write(
            "package.json",
            json.dumps({"name": "example", "scripts": {"test": "example"}}),
        )
        revision = self.commit("test: improve development tooling")
        result = self.prepare(revision)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.decision()["publish"], "false")
        self.assertIn("Runtime files are unchanged", self.summary.read_text())
        self.assertIn("0 added, 0 modified, 0 deleted", self.summary.read_text())
        self.assert_unpublished()

    def test_next_publication_includes_commits_from_a_skipped_run(self) -> None:
        self.write("tests/example.py", "development only")
        skipped = self.commit("test: skipped development change")
        result = self.prepare(skipped)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.decision()["publish"], "false")
        next_output = self.root / "next-output"
        self.output = next_output
        self.outputs.unlink()
        self.summary.unlink()
        self.write("README.md", "Next runtime change\n")
        revision = self.commit("feat: next runtime")
        result = self.prepare(revision)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.decision()["publish"], "true")
        self.assertIn("test: skipped development change", self.message.read_text())
        self.assertIn("feat: next runtime", self.message.read_text())
        self.assertIn(
            f"Source: {self.base[:7]}..{revision[:7]}", self.message.read_text()
        )

    def test_executable_mode_change_requires_publication(self) -> None:
        (self.source / "README.md").chmod(0o755)
        revision = self.commit("fix: executable mode")
        result = self.prepare(revision)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.decision()["publish"], "true")
        self.assertIn("0 added, 1 modified, 0 deleted", self.summary.read_text())

    def test_skips_already_published_revision_before_building(self) -> None:
        result = self.prepare(self.base)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.decision()["publish"], "false")
        self.assertIn("already published", self.summary.read_text())
        self.assertFalse(self.output.exists())
        self.assert_unpublished()

    def test_skips_superseded_run_instead_of_rolling_back(self) -> None:
        self.write("README.md", "New runtime\n")
        newer = self.commit("feat: newer runtime")
        (self.distribution / "SOURCE_REVISION").write_text(newer + "\n")
        self.git(self.distribution, "add", "--all")
        self.git(self.distribution, "commit", "--quiet", "-m", "newer release")
        before = self.git(self.distribution, "rev-parse", "HEAD")
        self.git(self.source, "checkout", "--quiet", "--detach", self.base)
        result = self.prepare(self.base)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.decision()["publish"], "false")
        self.assertIn("superseded", self.summary.read_text())
        self.assertFalse(self.output.exists())
        self.assertFalse(self.message.exists())
        self.assertEqual(self.git(self.distribution, "rev-parse", "HEAD"), before)
        self.assertEqual(self.git(self.distribution, "status", "--porcelain"), "")

    def test_rejects_diverged_or_unrelated_history(self) -> None:
        newer = self.commit("feat: published branch")
        (self.distribution / "SOURCE_REVISION").write_text(newer + "\n")
        self.git(self.distribution, "add", "--all")
        self.git(self.distribution, "commit", "--quiet", "-m", "newer release")
        self.git(self.source, "checkout", "--quiet", "--detach", self.base)
        diverged = self.commit("feat: different branch")
        self.git(self.source, "checkout", "--quiet", "--orphan", "unrelated")
        unrelated = self.commit("feat: unrelated history")
        for revision in (diverged, unrelated):
            with self.subTest(revision=revision):
                self.git(self.source, "checkout", "--quiet", "--detach", revision)
                result = self.prepare(revision)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Could not prepare distribution", result.stderr)
                self.assertFalse(self.outputs.exists())
                self.assertFalse(self.message.exists())
                self.assertFalse(self.output.exists())

    def test_rejects_missing_invalid_or_unknown_committed_revision(self) -> None:
        for previous in (None, "main", "f" * 40):
            with self.subTest(previous=previous):
                marker = self.distribution / "SOURCE_REVISION"
                if previous is None:
                    marker.unlink()
                else:
                    marker.write_text(previous + "\n")
                self.git(self.distribution, "add", "--all")
                self.git(self.distribution, "commit", "--quiet", "-m", "invalid marker")
                result = self.prepare(self.base)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Could not prepare distribution", result.stderr)
                self.assertFalse(self.outputs.exists())
                self.assertFalse(self.output.exists())

    def test_rejects_checkout_that_does_not_match_tested_revision(self) -> None:
        self.commit("feat: untested runtime")
        result = self.prepare(self.base)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not match", result.stderr)
        self.assertFalse(self.outputs.exists())
        self.assert_unpublished()


if __name__ == "__main__":
    unittest.main()
