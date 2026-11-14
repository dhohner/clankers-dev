from __future__ import annotations

import argparse
import contextlib
import tempfile
import unittest
from pathlib import Path

from support import BUNDLE, SKILL_DIR, base_manifest, dump_yaml, load_yaml, run_cli

from scripts.advisories import MAX_SENTENCE_WORDS, manifest_warnings
from scripts.cli import bundle_commands

RESEARCH_NODE = {
    "id": "NODE-01",
    "label": "Bundle format",
    "question": "Which format does the bundle use?",
    "status": "settled",
    "answer": "Static HTML.",
    "source": "research",
    "rationale": "The bundle must open without a server.",
}


def words(count: int) -> str:
    return " ".join(["word"] * count) + "."


def research_manifest(*evidence: str) -> dict:
    manifest = base_manifest()
    manifest["schema_version"] = 2
    manifest["blocks"] = {"design_tree": [{**RESEARCH_NODE, "evidence": list(evidence)}]}
    return manifest


def warnings_for(manifest: dict, workspace: Path = SKILL_DIR) -> list[str]:
    return manifest_warnings(BUNDLE.validate_manifest(manifest), workspace)


class SentenceLengthTests(unittest.TestCase):
    def test_sentence_over_the_limit_warns_with_its_path_and_word_count(self) -> None:
        cases = {
            "at the limit": (words(MAX_SENTENCE_WORDS), []),
            "one word over": (
                words(MAX_SENTENCE_WORDS + 1),
                [f"summary: sentence has {MAX_SENTENCE_WORDS + 1} words"],
            ),
            "two short sentences": (
                f"{words(MAX_SENTENCE_WORDS)} {words(MAX_SENTENCE_WORDS)}",
                [],
            ),
        }
        for name, (summary, expected) in cases.items():
            with self.subTest(name):
                manifest = base_manifest()
                manifest["summary"] = summary
                manifest["blocks"] = {"non_goals": ["An excluded outcome."]}

                found = warnings_for(manifest)

                self.assertEqual([warning.split(",")[0] for warning in found], expected)

    def test_nested_prose_warns_and_non_prose_fields_do_not(self) -> None:
        manifest = base_manifest()
        manifest["blocks"] = {
            "requirements": [
                {
                    "title": "Readable requirement",
                    "description": words(MAX_SENTENCE_WORDS + 5),
                    "exception": "No test yet.",
                    "evidence": [words(MAX_SENTENCE_WORDS + 5)],
                }
            ],
            "workflow_diagram": {
                "description": "The flow.",
                "source": "flowchart TB\n  a[" + words(MAX_SENTENCE_WORDS + 5) + "] --> b",
            },
        }

        found = warnings_for(manifest)

        self.assertEqual(len(found), 1, found)
        self.assertTrue(found[0].startswith("blocks.requirements[0].description:"), found)


class ResearchEvidenceTests(unittest.TestCase):
    def test_evidence_that_names_an_existing_path_or_url_passes(self) -> None:
        for evidence in (
            "scripts/bundle.py::generate_bundle",
            "scripts/bundle.py:12 publishes the bundle.",
            "The check lives in `scripts/validation.py#L40-L60`.",
            "SKILL.md states the review gate.",
            "https://example.com/spec says so.",
        ):
            with self.subTest(evidence):
                self.assertEqual(warnings_for(research_manifest(evidence)), [])

    def test_evidence_without_a_checkable_source_warns(self) -> None:
        cases = {
            "The repository has no tests yet.": "names no repository path or URL",
            "Interview notes, e.g. the stakeholder call.": "names no repository path or URL",
            "The stakeholder call, i.e. the kickoff.": "names no repository path or URL",
            "Python 3.14 and release 1.2.3 add it.": "names no repository path or URL",
            "scripts/missing.py holds the check.": "names scripts/missing.py, which does not exist",
        }
        for evidence, problem in cases.items():
            with self.subTest(evidence):
                found = warnings_for(research_manifest(evidence))

                self.assertEqual(len(found), 1, found)
                self.assertIn(f'blocks.design_tree NODE-01: evidence "{evidence}" ', found[0])
                self.assertIn(problem, found[0])

    def test_only_research_answers_need_checkable_evidence(self) -> None:
        manifest = research_manifest("Quoted from the request.")
        manifest["blocks"]["design_tree"][0]["source"] = "request"

        self.assertEqual(warnings_for(manifest), [])

    def test_paths_resolve_against_the_workspace(self) -> None:
        manifest = research_manifest("notes/finding.md records it.")
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            self.assertEqual(len(warnings_for(manifest, workspace)), 1)

            (workspace / "notes").mkdir()
            (workspace / "notes" / "finding.md").write_text("finding\n", encoding="utf-8")
            self.assertEqual(warnings_for(manifest, workspace), [])

    def test_existing_root_files_without_an_extension_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            for name in ("LICENSE", "Makefile", ".gitignore"):
                (workspace / name).write_text("content\n", encoding="utf-8")
            (workspace / "tests").mkdir()
            for evidence in ("LICENSE", "Makefile:3 builds it.", "The `.gitignore` skips it."):
                with self.subTest(evidence):
                    self.assertEqual(warnings_for(research_manifest(evidence), workspace), [])
            # A root directory, a missing file, or a case-only match is not a named file.
            for evidence in (
                "The tests show it.",
                "Dockerfile builds it.",
                "The license allows it.",
            ):
                with self.subTest(evidence):
                    found = warnings_for(research_manifest(evidence), workspace)

                    self.assertEqual(len(found), 1, found)
                    self.assertIn("names no repository path or URL", found[0])

    def test_existing_paths_outside_the_workspace_warn(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            workspace = root / "repo"
            (workspace / "notes").mkdir(parents=True)
            (workspace / "notes" / "inside.md").write_text("inside\n", encoding="utf-8")
            outside = root / "finding.md"
            outside.write_text("finding\n", encoding="utf-8")
            (workspace / "notes" / "link.md").symlink_to(outside)
            cases = {
                "absolute": f"{outside} records it.",
                "traversal": "../finding.md records it.",
                "nested traversal": "notes/../../finding.md records it.",
                "symlink": "notes/link.md records it.",
            }
            for case, evidence in cases.items():
                with self.subTest(case):
                    found = warnings_for(research_manifest(evidence), workspace)

                    self.assertEqual(len(found), 1, found)
                    self.assertIn("outside", found[0])
            for evidence in (
                f"{workspace / 'notes' / 'inside.md'} records it.",
                "notes/../notes/inside.md records it.",
            ):
                with self.subTest(evidence):
                    self.assertEqual(warnings_for(research_manifest(evidence), workspace), [])


class AdvisoryCommandTests(unittest.TestCase):
    def test_validate_reports_warnings_and_truncates_them_without_full(self) -> None:
        manifest = base_manifest()
        manifest["blocks"] = {"non_goals": [words(MAX_SENTENCE_WORDS + 1) for _ in range(25)]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prd.yaml"
            path.write_text(dump_yaml(manifest), encoding="utf-8")

            short = load_yaml(run_cli("validate", str(path)).stdout)
            full = load_yaml(run_cli("validate", str(path), "--full").stdout)

        self.assertEqual(short["status"], "ok")
        self.assertEqual(short["total_warnings"], "25")
        self.assertEqual(len(short["warnings"]), 20)
        self.assertIs(short["warnings_truncated"], True)
        self.assertIn("--full", short["next"][0])
        self.assertEqual(len(full["warnings"]), 25)
        self.assertNotIn("warnings_truncated", full)

    def test_validate_warns_about_evidence_paths_the_filesystem_rejects(self) -> None:
        manifest = research_manifest("notes/\x00.md holds the decision.")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prd.yaml"
            path.write_text(dump_yaml(manifest), encoding="utf-8")

            result = run_cli("validate", str(path))

        self.assertEqual(result.returncode, 0, result.stderr)
        report = load_yaml(result.stdout)
        self.assertEqual(len(report["warnings"]), 1, report["warnings"])
        self.assertIn("which does not exist under", report["warnings"][0])

    def test_inspect_reports_the_warnings_of_the_published_manifest(self) -> None:
        manifest = research_manifest("The repository has no tests yet.")
        with tempfile.TemporaryDirectory() as directory:
            bundle = BUNDLE.generate_bundle(
                BUNDLE.validate_manifest(manifest), Path(directory), False
            )
            with contextlib.chdir(SKILL_DIR):
                result = bundle_commands.command_inspect(
                    argparse.Namespace(bundle=bundle, full=False)
                )

        self.assertEqual(len(result["warnings"]), 1, result["warnings"])
        self.assertIn("names no repository path or URL", result["warnings"][0])

    def test_inspect_counts_all_warnings_when_it_truncates_them(self) -> None:
        manifest = base_manifest()
        manifest["blocks"] = {"non_goals": [words(MAX_SENTENCE_WORDS + 1) for _ in range(25)]}
        with tempfile.TemporaryDirectory() as directory:
            bundle = BUNDLE.generate_bundle(
                BUNDLE.validate_manifest(manifest), Path(directory), False
            )
            with contextlib.chdir(SKILL_DIR):
                result = bundle_commands.command_inspect(
                    argparse.Namespace(bundle=bundle, full=False)
                )

        self.assertEqual(
            (result["total_warnings"], len(result["warnings"]), result["warnings_truncated"]),
            (25, 20, True),
        )

    def test_inspect_warns_about_evidence_paths_the_filesystem_rejects(self) -> None:
        manifest = research_manifest("notes/\x00.md holds the decision.")
        with tempfile.TemporaryDirectory() as directory:
            bundle = BUNDLE.generate_bundle(
                BUNDLE.validate_manifest(manifest), Path(directory), False
            )
            with contextlib.chdir(SKILL_DIR):
                result = bundle_commands.command_inspect(
                    argparse.Namespace(bundle=bundle, full=False)
                )

        self.assertEqual(len(result["warnings"]), 1, result["warnings"])
        self.assertIn("which does not exist under", result["warnings"][0])


if __name__ == "__main__":
    unittest.main()
