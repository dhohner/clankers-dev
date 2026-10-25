from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MESSAGE = ROOT / "tools/release/message.py"


class MessageTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source"
        self.distribution = self.root / "distribution"
        self.env = {
            **os.environ,
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
        }
        for repository in (self.source, self.distribution):
            self.git(repository, "init", "--quiet", str(repository))
        self.base = self.commit("chore: initial source")
        self.record_release(self.base)

    def git(self, repository: Path, *args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(repository), *args]
            if repository.exists()
            else ["git", *args],
            env=self.env,
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()

    def commit(self, message: str) -> str:
        self.git(self.source, "commit", "--allow-empty", "-m", message)
        return self.git(self.source, "rev-parse", "HEAD")

    def record_release(self, revision: str | None) -> None:
        if revision is not None:
            (self.distribution / "SOURCE_REVISION").write_text(revision + "\n")
            self.git(self.distribution, "add", "--all")
        self.git(self.distribution, "commit", "--allow-empty", "-m", "release")

    def generate(self, revision: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(MESSAGE),
                "--source",
                str(self.source),
                "--distribution",
                str(self.distribution),
                "--revision=" + revision,
                *args,
            ],
            env=self.env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_preserves_subjects_and_bodies_in_source_order_without_urls(self) -> None:
        self.commit(
            "feat: first feature\n\nExplain the user benefit.\n\nKeep this paragraph."
        )
        revision = self.commit("fix: second change")
        # The staged revision must not replace the previous release boundary.
        (self.distribution / "SOURCE_REVISION").write_text(revision + "\n")
        self.git(self.distribution, "add", "--all")
        result = self.generate(revision)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout,
            (
                f"release: clankers {revision[:7]}\n\n"
                "- feat: first feature\n\n  Explain the user benefit.\n\n"
                "  Keep this paragraph.\n\n- fix: second change\n\n"
                f"Source: {self.base[:7]}..{revision[:7]}\n"
            ),
        )

    def test_omits_signoffs_and_dependabot_bodies(self) -> None:
        self.commit(
            "feat: useful change\n\nUseful description.\n\nSigned-off-by: Test <test@example.com>"
        )
        revision = self.commit(
            "build(deps-dev): update tools\n\nBumps tools.\n\n---\nupdated-dependencies:\n- dependency-name: tool\n..."
        )
        result = self.generate(revision)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout,
            (
                f"release: clankers {revision[:7]}\n\n"
                "- feat: useful change\n\n  Useful description.\n\n"
                "- build(deps-dev): update tools\n\n"
                f"Source: {self.base[:7]}..{revision[:7]}\n"
            ),
        )

    def test_subject_only_changes_form_a_compact_list(self) -> None:
        self.commit("fix: first fix\n\nSigned-off-by: Test <test@example.com>")
        revision = self.commit("fix: second fix")
        result = self.generate(revision)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout,
            f"release: clankers {revision[:7]}\n\n"
            "- fix: first fix\n- fix: second fix\n\n"
            f"Source: {self.base[:7]}..{revision[:7]}\n",
        )

    def test_first_release_requires_an_explicit_starting_revision(self) -> None:
        self.git(self.distribution, "rm", "SOURCE_REVISION")
        self.record_release(None)
        revision = self.commit("feat: first published feature")
        missing = self.generate(revision)
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("--initial-base", missing.stderr)
        result = self.generate(revision, "--initial-base", self.base)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("feat: first published feature", result.stdout)
        self.assertNotIn("chore: initial source", result.stdout)

    def test_rejects_invalid_or_unrelated_release_boundaries(self) -> None:
        revision = self.commit("feat: next")
        self.git(self.source, "checkout", "--detach", self.base)
        diverged = self.commit("feat: different branch")
        self.git(self.source, "checkout", "--orphan", "unrelated")
        unrelated = self.commit("chore: unrelated history")
        for previous, target in (
            ("", revision),
            ("main", revision),
            ("f" * 40, revision),
            (unrelated, revision),
            (diverged, revision),
            (self.base, "--all"),
            (self.base, "f" * 40),
        ):
            with self.subTest(previous=previous, target=target):
                self.record_release(previous)
                result = self.generate(target)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Could not generate release message", result.stderr)
                self.assertEqual(result.stdout, "")

    def test_rollback_names_both_revisions_and_removed_changes(self) -> None:
        previous = self.commit("feat: reverted feature\n\nFeature description.")
        self.record_release(previous)
        result = self.generate(self.base)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout,
            (
                f"release: clankers {self.base[:7]}\n\n"
                f"Rollback from {previous[:7]} to {self.base[:7]}.\n\nRemoved changes:\n\n"
                "- feat: reverted feature\n\n  Feature description.\n\n"
                f"Source: {previous[:7]}..{self.base[:7]}\n"
            ),
        )


if __name__ == "__main__":
    unittest.main()
