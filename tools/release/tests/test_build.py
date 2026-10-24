from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "release_build", ROOT / "tools/release/build.py"
)
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)
REVISION = "1" * 40


class BuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.source = self.root / "source"
        self.source.mkdir()
        self.output = self.root / "output"
        self.git("init", "--quiet")

    def git(self, *args: str) -> str:
        return release.git(self.source, *args)

    def write(
        self, relative: str, content: str = "runtime", *, tracked: bool = True
    ) -> Path:
        path = self.source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        if tracked:
            self.git("add", "--", relative)
        return path

    def test_selects_only_tracked_allowlisted_files(self) -> None:
        self.write("runtime/entry.py")
        self.write("runtime/local.py", tracked=False)
        self.write("tests/test_entry.py")
        self.write(".github/workflows/ci.yml")
        self.assertEqual(
            release.runtime_files(self.source, ["runtime/**/*.py"]),
            [Path("runtime/entry.py")],
        )

    def test_rejects_development_files_even_if_allowlisted(self) -> None:
        for path in (
            "tests/test_entry.py",
            "test/example.ts",
            "evals/cases.json",
            ".github/workflows/ci.yml",
            "runtime/check.test.ts",
            "runtime/oracle.whl",
            "runtime/__pycache__/entry.pyc",
        ):
            with self.subTest(path=path):
                self.write(path)
                with self.assertRaisesRegex(ValueError, "Development file"):
                    release.runtime_files(self.source, [path])

    def test_rejects_symlinks_and_unsafe_patterns(self) -> None:
        target = self.write("entry.py")
        link = self.source / "link.py"
        link.symlink_to(target)
        self.git("add", "link.py")
        with self.assertRaisesRegex(ValueError, "regular file"):
            release.runtime_files(self.source, ["link.py"])
        for pattern in ("../outside/*", "/tmp/*"):
            with (
                self.subTest(pattern=pattern),
                self.assertRaisesRegex(ValueError, "Unsafe"),
            ):
                release.runtime_files(self.source, [pattern])

    def test_refuses_nonempty_or_overlapping_output_without_modifying_it(self) -> None:
        sentinel = self.write("keep.txt", "preserve")
        for output in (self.source, self.source / "dist", self.root):
            with (
                self.subTest(output=output),
                self.assertRaisesRegex(ValueError, "outside"),
            ):
                release.build(self.source, output, REVISION)
        self.output.mkdir()
        (self.output / "keep.txt").write_text("preserve", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "must be empty"):
            release.build(self.source, self.output, REVISION)
        self.assertEqual(sentinel.read_text(), "preserve")
        self.assertEqual((self.output / "keep.txt").read_text(), "preserve")

    def test_replacement_refuses_overlapping_paths_without_deleting_files(self) -> None:
        sentinel = self.write("keep.txt", "preserve")
        (self.root / "SOURCE_REVISION").write_text(REVISION, encoding="utf-8")
        result = subprocess.run(
            [
                "bash",
                str(ROOT / "tools/release/replace.sh"),
                str(self.root),
                str(self.source),
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must not overlap", result.stderr)
        self.assertEqual(sentinel.read_text(), "preserve")

    def test_replacement_refuses_a_destination_without_git_metadata(self) -> None:
        sentinel = self.write("keep.txt", "preserve")
        self.output.mkdir()
        (self.output / "SOURCE_REVISION").write_text(REVISION, encoding="utf-8")
        destination = self.root / "not-a-checkout"
        destination.mkdir()
        result = subprocess.run(
            [
                "bash",
                str(ROOT / "tools/release/replace.sh"),
                str(self.output),
                str(destination),
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("disposable Git checkout", result.stderr)
        self.assertEqual(sentinel.read_text(), "preserve")

    def test_rejects_empty_selection_and_invalid_revision(self) -> None:
        with self.assertRaisesRegex(ValueError, "No tracked runtime"):
            release.build(self.source, self.output, REVISION, ["missing/*"])
        with self.assertRaisesRegex(ValueError, "full Git commit SHA"):
            release.build(self.source, self.output, "main", ["missing/*"])
        self.assertFalse(self.output.exists())


class RepositoryDistributionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name).resolve()
        cls.output = cls.root / "output"
        cls.revision = release.git(ROOT, "rev-parse", "HEAD").strip()
        release.build(ROOT, cls.output, cls.revision)

    def test_has_no_tests_evaluations_workflows_or_development_dependencies(
        self,
    ) -> None:
        release.validate_distribution(self.output)
        for path in [
            self.output / "package.json",
            *self.output.glob("plugins/*/package.json"),
        ]:
            with self.subTest(package=path.relative_to(self.output)):
                data = json.loads(path.read_text())
                self.assertNotIn("devDependencies", data)
                self.assertNotIn("scripts", data)
                for relative in data["files"]:
                    self.assertTrue((path.parent / relative).is_file(), relative)
        self.assertEqual(
            (self.output / "SOURCE_REVISION").read_text(), self.revision + "\n"
        )
        self.assertFalse((self.output / "tools").exists())
        self.assertFalse((self.output / "action-items").exists())

    def test_preserves_runtime_assets_examples_and_executable_modes(self) -> None:
        for relative in (
            "plugins/project-advisor/skills/to-prd/bundle/assets/fonts/manrope.woff2",
            "plugins/project-advisor/skills/to-prd/examples/fixtures/document-only.yaml",
            "plugins/security-guard/src/shell/command-parser.ts",
            "plugins/output-styles/styles/unslop.md",
            "plugins/task-executor/skills/implement/SKILL.md",
            "plugins/refactor-tools/skills/review-changes/references/verification.md",
        ):
            with self.subTest(path=relative):
                self.assertEqual(
                    (self.output / relative).read_bytes(),
                    (ROOT / relative).read_bytes(),
                )
        relative = "plugins/insomniac/scripts/statusline.sh"
        self.assertEqual(
            (self.output / relative).stat().st_mode, (ROOT / relative).stat().st_mode
        )

    def test_distribution_cli_runs_without_production_packages(self) -> None:
        skill = self.output / "plugins/project-advisor/skills/to-prd"
        for args in (("schema",), ("validate", "examples/basic-prd.yaml", "--full")):
            with self.subTest(args=args):
                result = subprocess.run(
                    [sys.executable, "-I", "-S", "-B", "scripts/__main__.py", *args],
                    cwd=skill,
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                self.assertTrue(result.stdout.strip())

    def test_build_is_deterministic_and_does_not_modify_source(self) -> None:
        before = release.git(ROOT, "status", "--porcelain=v1", "--untracked-files=all")
        second = self.root / "second"
        release.build(ROOT, second, self.revision)
        for path in self.output.rglob("*"):
            if path.is_file():
                self.assertEqual(
                    path.read_bytes(),
                    (second / path.relative_to(self.output)).read_bytes(),
                )
        self.assertEqual(
            release.git(ROOT, "status", "--porcelain=v1", "--untracked-files=all"),
            before,
        )

    def test_replacement_removes_preexisting_tests_workflows_and_stale_files(
        self,
    ) -> None:
        checkout = self.root / "distribution"
        subprocess.run(
            [
                "git",
                "clone",
                "--quiet",
                "--no-hardlinks",
                "--local",
                str(ROOT),
                str(checkout),
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        self.assertTrue((checkout / ".github/workflows/ci.yml").exists())
        self.assertTrue(
            (checkout / "plugins/project-advisor/skills/to-prd/tests").exists()
        )
        subprocess.run(
            [
                "bash",
                str(ROOT / "tools/release/replace.sh"),
                str(self.output),
                str(checkout),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertFalse((checkout / ".github").exists())
        self.assertFalse(
            (checkout / "plugins/project-advisor/skills/to-prd/tests").exists()
        )
        self.assertFalse((checkout / "plugins/security-guard/test").exists())
        self.assertFalse((checkout / "vitest.config.mts").exists())
        expected = {
            p.relative_to(self.output).as_posix()
            for p in self.output.rglob("*")
            if p.is_file()
        }
        actual = set(release.git(checkout, "ls-files", "-z").rstrip("\0").split("\0"))
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
