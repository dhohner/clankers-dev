"""Tests for scripts/validate_tasks.py.

The suite runs on Python 3.9, the oldest interpreter the validator supports, so keep it
free of newer syntax.
"""

from __future__ import annotations

import importlib.util
import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPT = SKILL_DIR / "scripts" / "validate_tasks.py"
TEMPLATE = SKILL_DIR / "references" / "agent-task-template.md"
# `to-spec generate` wrote these from evals/inputs/spec-reading-log-tags.yaml, one with a
# multiline REQ-01 title and one with an `id:` line inside a multiline evidence item.
FIXTURES = Path(__file__).resolve().parent / "fixtures"

_module_spec = importlib.util.spec_from_file_location("validate_tasks", SCRIPT)
assert _module_spec is not None and _module_spec.loader is not None
validate_tasks = importlib.util.module_from_spec(_module_spec)
# dataclasses resolves the module through sys.modules while it builds each class.
sys.modules[_module_spec.name] = validate_tasks
_module_spec.loader.exec_module(validate_tasks)

EXECUTOR = "\n".join(validate_tasks.EXECUTOR_TEXT)

SPEC = """\
schema_version: 3
slug: "reading-log-tags"
title: "Reading Log Tags"
status: Accepted
blocks:
  requirements:
    - id: "REQ-01"
      title: Add a book entry
    - id: "REQ-02"
      title: Tag an existing entry
    - id: "REQ-03"
      title: List entries by tag
  design_tree:
    - id: NODE-01
      question: Should `Fantasy` and `fantasy` count as one tag?
  testing_strategy:
    - id: "TEST-01"
      validates:
        - "REQ-01"
"""

SHARED = """\
### Shared: Log file

The log is a JSON array of entries with `id`, `title`, `added`, and `tags`.
"""


def task(title: str, depends_on: str, needs_first: str = "", contract: str = SHARED) -> str:
    needs = "".join(f"- Needs first: {line}\n" for line in needs_first.splitlines() if line)
    return f"""\
---
{depends_on}
state: pending
---

# {title}

## Outcome

Readers can {title.lower()} from the terminal.

## Required behavior

- `reading-log add <title>` keeps its current behavior.

## Contract

{contract}
## Boundary

- May change: `src/cli.mjs` and its tests.
- Must preserve: the `help` command output.
{needs}
{EXECUTOR}

## Repository notes

`run(argv, {{ stdout, stderr, env }})` in `src/cli.mjs` is the entry point.

## Acceptance

- Running the command against an empty log file prints the expected output.

## Validation

- `npm test` passes with a new test for this command, as new-behavior coverage.
"""


SOURCE_MAP = """\
# Source map: Reading Log Tags

| Source item | Disposition | Tasks | Note |
| --- | --- | --- | --- |
| REQ-01 | implementation | `01-add-entries.md` | |
| REQ-02 | implementation | `02-tag-entries.md` | |
| REQ-03 | implementation | `03-list-by-tag.md` | |
| NODE-01 | implementation | `02-tag-entries.md`, `03-list-by-tag.md` | |
| TEST-01 | validation | `01-add-entries.md` | |
| scope.out: Sync between machines | no work | | Excluded from v1. |
"""


def valid_files() -> dict:
    return {
        "01-add-entries.md": task("Add entries", "depends_on: []"),
        "02-tag-entries.md": task(
            "Tag entries",
            "depends_on:\n  - 01-add-entries.md",
            "`01-add-entries.md` stores entries with integer ids in the log file.",
        ),
        "03-list-by-tag.md": task(
            "List by tag",
            "depends_on:\n  - 02-tag-entries.md",
            "`02-tag-entries.md` stores lowercase tags on each entry.",
        ),
        "source-map-reading-log-tags.md": SOURCE_MAP,
    }


VALID_TASKS = tuple(name for name in valid_files() if not name.startswith("source-map-"))


def two_predecessor_files(second_item: str = "  - 04-import-entries.md") -> dict:
    files = valid_files()
    files["04-import-entries.md"] = task("Import entries", "depends_on: []")
    files["05-export-tags.md"] = task(
        "Export tags",
        "depends_on:\n  - 03-list-by-tag.md\n" + second_item,
        "`03-list-by-tag.md` lists entries by tag.\n`04-import-entries.md` imports entries.",
    )
    files["source-map-reading-log-tags.md"] = SOURCE_MAP + (
        "| scope.in: Import | implementation | `04-import-entries.md`, `05-export-tags.md` | |\n"
    )
    return files


class ValidatorCase(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.task_dir = self.root / "agent-tasks"
        self.task_dir.mkdir()
        self.spec = self.root / "spec.yaml"
        self.spec.write_text(SPEC, encoding="utf-8")

    def write(self, files: dict) -> None:
        """Write each file; a None value leaves that file absent."""
        for name, text in files.items():
            if text is not None:
                (self.task_dir / name).write_text(text, encoding="utf-8")

    def run_validator(self, *extra: str):
        output = io.StringIO()
        with redirect_stdout(output):
            code = validate_tasks.main([str(self.task_dir), "--spec", str(self.spec), *extra])
        return code, output.getvalue()


class ValidTaskSetTest(ValidatorCase):
    def test_valid_task_set_passes(self) -> None:
        self.write(valid_files())
        code, output = self.run_validator()
        self.assertEqual(code, 0, output)
        self.assertIn("ok: 3 task file(s) and 6 source item(s)", output)
        self.assertIn("not checked:", output)

    def test_flow_list_and_quoted_names_are_accepted(self) -> None:
        files = valid_files()
        replace(
            "02-tag-entries.md",
            "depends_on:\n  - 01-add-entries.md",
            'depends_on: ["01-add-entries.md"]',
        )(files)
        self.write(files)
        code, output = self.run_validator()
        self.assertEqual(code, 0, output)

    def test_placeholder_syntax_inside_code_is_not_a_placeholder(self) -> None:
        files = valid_files()
        replace(
            "01-add-entries.md",
            "## Repository notes\n",
            "## Repository notes\n\n```text\n<Task title> inside a fence\n```\n",
        )(files)
        self.write(files)
        code, output = self.run_validator()
        self.assertEqual(code, 0, output)

    def test_a_sibling_heading_ends_the_shared_block(self) -> None:
        files = valid_files()
        replace(
            "01-add-entries.md",
            "`added`, and `tags`.\n",
            "`added`, and `tags`.\n\n### Entry ids\n\nIds start at 1.\n",
        )(files)
        self.write(files)
        code, output = self.run_validator()
        self.assertEqual(code, 0, output)

    def test_only_a_matching_fence_closes_a_code_block(self) -> None:
        examples = {
            "shorter fence": "````markdown\n```sh\ncat <<EOF\n## Sample output\nEOF\n```\n````\n",
            "other marker": "```text\n~~~\n## Sample output\n```\n",
            "fence with an info string": "```text\n```sh\n## Sample output\n```\n",
        }
        for label, example in examples.items():
            with self.subTest(label):
                files = valid_files()
                replace(
                    "01-add-entries.md",
                    "## Repository notes\n",
                    "## Repository notes\n\n" + example,
                )(files)
                self.write(files)
                code, output = self.run_validator()
                self.assertEqual(code, 0, output)

    def test_a_task_may_need_two_independent_predecessors(self) -> None:
        self.write(two_predecessor_files())
        code, output = self.run_validator()
        self.assertEqual(code, 0, output)

    def test_depends_on_items_share_one_indentation(self) -> None:
        # YAML folds a more deeply indented item into the item before it.
        files = two_predecessor_files("    - 04-import-entries.md")
        self.write(files)
        code, output = self.run_validator()
        self.assertEqual(code, 1, output)
        self.assertIn("05-export-tags.md:4: indent each `depends_on` item like the first", output)

    def test_an_id_line_inside_a_block_scalar_is_text(self) -> None:
        files = valid_files()
        files["source-map-reading-log-tags.md"] += "| NODE-02 | no work | | Settled by NODE-01. |\n"
        self.write(files)
        self.spec.write_text(
            SPEC.replace(
                "      question: Should `Fantasy` and `fantasy` count as one tag?\n",
                "      question: Should `Fantasy` and `fantasy` count as one tag?\n"
                "      answer: |-\n"
                "        Yes. Store each tag as YAML, such as:\n"
                "\n"
                "        - id: REQ-EXAMPLE\n"
                "      children:\n"
                "        - id: NODE-02\n",
            ),
            encoding="utf-8",
        )
        code, output = self.run_validator()
        self.assertEqual(code, 0, output)

    def test_runs_as_a_script_with_python3_9_compatible_code(self) -> None:
        self.write(valid_files())
        result = subprocess.run(
            [sys.executable, "-I", str(SCRIPT), str(self.task_dir), "--spec", str(self.spec)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_directory_is_a_usage_error(self) -> None:
        errors = io.StringIO()
        with redirect_stderr(errors), self.assertRaises(SystemExit) as raised:
            validate_tasks.main([str(self.root / "missing"), "--spec", str(self.spec)])
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("is not a directory", errors.getvalue())


class TemplateAgreementTest(unittest.TestCase):
    def test_template_holds_the_executor_text(self) -> None:
        lines = TEMPLATE.read_text(encoding="utf-8").splitlines()
        self.assertIsNotNone(validate_tasks.find_run(lines, validate_tasks.EXECUTOR_TEXT))

    def test_template_frontmatter_guidance_names_every_state(self) -> None:
        guidance = TEMPLATE.read_text(encoding="utf-8").split("\n# ", 1)[0]
        missing = [state for state in validate_tasks.STATES if f"`{state}`" not in guidance]
        self.assertEqual(missing, [])

    def test_template_sections_match_the_validator(self) -> None:
        sections = [
            line[3:].strip()
            for line in TEMPLATE.read_text(encoding="utf-8").splitlines()
            if line.startswith("## ")
        ]
        self.assertEqual(tuple(sections), validate_tasks.SECTIONS)

    def test_template_boundary_labels_match_the_validator(self) -> None:
        text = TEMPLATE.read_text(encoding="utf-8")
        boundary = text.split("## Boundary", 1)[1].split("\n## ", 1)[0]
        labels = [
            line[2:].split(":", 1)[0] for line in boundary.splitlines() if line.startswith("- ")
        ]
        self.assertEqual(tuple(labels), validate_tasks.BOUNDARY_LABELS)


def replace(name: str, old: str, new: str):
    def change(files: dict) -> None:
        if old not in files[name]:
            raise AssertionError(f"{old!r} is not in {name}")
        files[name] = files[name].replace(old, new, 1)

    return change


def put(name: str, text):
    def change(files: dict) -> None:
        files[name] = text

    return change


# Each case changes the valid task set and names the file and the message it must report.
FAILURES = [
    (
        "frontmatter missing",
        replace("01-add-entries.md", "---\ndepends_on: []\nstate: pending\n---\n\n", ""),
        "01-add-entries.md:1: line 1 must be `---`",
    ),
    (
        "frontmatter not closed",
        replace("01-add-entries.md", "state: pending\n---\n", "state: pending\n"),
        "01-add-entries.md:1: the frontmatter block has no closing `---` line",
    ),
    (
        "extra frontmatter key",
        replace("01-add-entries.md", "state: pending\n", "state: pending\nowner: me\n"),
        (
            "01-add-entries.md:4: frontmatter holds only the keys `depends_on`, `state`, "
            "and `failure` for a failed task"
        ),
    ),
    (
        "no space after the key colon",
        replace("01-add-entries.md", "state: pending", "state:pending"),
        "01-add-entries.md:3: put a space between `state:` and its value",
    ),
    (
        "tab before a depends_on item",
        replace("02-tag-entries.md", "  - 01-add-entries.md", "\t- 01-add-entries.md"),
        "02-tag-entries.md:3: indent frontmatter with spaces, not tabs",
    ),
    (
        "unknown state",
        replace("01-add-entries.md", "state: pending", "state: started"),
        "01-add-entries.md:3: `state` must be `pending`, `running`, `failed`, or `done`",
    ),
    (
        "missing state",
        replace("01-add-entries.md", "state: pending\n", ""),
        "01-add-entries.md:1: frontmatter lacks `state`",
    ),
    (
        "empty depends_on",
        replace("01-add-entries.md", "depends_on: []", "depends_on:"),
        "01-add-entries.md:2: write `depends_on: []` for a task without predecessors",
    ),
    (
        "dependency is a path",
        replace(
            "02-tag-entries.md",
            "  - 01-add-entries.md",
            "  - agent-tasks/01-add-entries.md",
        ),
        (
            "02-tag-entries.md:3: `depends_on` entry agent-tasks/01-add-entries.md "
            "must be a bare file name"
        ),
    ),
    (
        "dependency does not exist",
        replace("02-tag-entries.md", "  - 01-add-entries.md", "  - 01-add-entry.md"),
        "02-tag-entries.md:3: `depends_on` entry 01-add-entry.md does not exist",
    ),
    (
        "dependency has a higher prefix",
        replace(
            "01-add-entries.md",
            "depends_on: []",
            "depends_on:\n  - 03-list-by-tag.md",
        ),
        "01-add-entries.md:3: `depends_on` entry 03-list-by-tag.md needs a lower numeric prefix",
    ),
    (
        "transitive predecessor listed",
        replace(
            "03-list-by-tag.md",
            "  - 02-tag-entries.md",
            "  - 01-add-entries.md\n  - 02-tag-entries.md",
        ),
        (
            "03-list-by-tag.md:3: `depends_on` lists 01-add-entries.md, which 02-tag-entries.md "
            "already requires"
        ),
    ),
    (
        "dependency without a Needs first line",
        replace(
            "02-tag-entries.md",
            "- Needs first: `01-add-entries.md` stores entries with integer ids in the log file.\n",
            "",
        ),
        (
            "02-tag-entries.md:3: `depends_on` lists 01-add-entries.md, "
            "but no `Needs first` line names it"
        ),
    ),
    (
        "Needs first line without a dependency",
        replace("02-tag-entries.md", "depends_on:\n  - 01-add-entries.md", "depends_on: []"),
        "`Needs first` names 01-add-entries.md, which `depends_on` does not list",
    ),
    (
        "two Needs first lines for one predecessor",
        replace(
            "02-tag-entries.md",
            "in the log file.\n",
            "in the log file.\n- Needs first: `01-add-entries.md` keeps the log path.\n",
        ),
        "02-tag-entries.md:28: a second `Needs first` line names 01-add-entries.md",
    ),
    (
        "Needs first line without a file name",
        replace("02-tag-entries.md", "`01-add-entries.md` stores", "The add command stores"),
        "start each `Needs first` line with the predecessor file name",
    ),
    (
        "Needs first line without a contract",
        replace(
            "02-tag-entries.md",
            "`01-add-entries.md` stores entries with integer ids in the log file.",
            "`01-add-entries.md`.",
        ),
        "`Needs first` names no prerequisite capability contract",
    ),
    (
        "required section missing",
        replace(
            "01-add-entries.md",
            "## Repository notes\n\n"
            "`run(argv, { stdout, stderr, env })` in `src/cli.mjs` is the entry point.\n\n",
            "",
        ),
        "01-add-entries.md: required section `## Repository notes` is missing",
    ),
    (
        "unknown section",
        replace("01-add-entries.md", "## Acceptance", "## Notes\n\nMore.\n\n## Acceptance"),
        "unknown section `## Notes`",
    ),
    (
        "empty section",
        replace(
            "01-add-entries.md",
            "Readers can add entries from the terminal.\n",
            "",
        ),
        "section `## Outcome` is empty",
    ),
    (
        "title missing",
        replace("01-add-entries.md", "# Add entries\n", ""),
        "the `# <Task title>` heading must follow the frontmatter",
    ),
    (
        "placeholder left",
        replace(
            "01-add-entries.md",
            "- Must preserve: the `help` command output.",
            "- Must preserve: <Name specific properties that callers or users require.>",
        ),
        "template placeholder left in place: <Name specific properties",
    ),
    (
        "executor text changed",
        replace("01-add-entries.md", "Record material choices.", "Record all choices."),
        "Boundary lacks the executor text",
    ),
    (
        "prose in Boundary",
        replace("01-add-entries.md", EXECUTOR, EXECUTOR + "\nAlso keep it short."),
        "Boundary holds only labelled lines and the executor text",
    ),
    (
        "unknown Boundary label",
        replace("01-add-entries.md", "- May change:", "- Owns:"),
        "Boundary lines start with one of:",
    ),
    (
        "repeated Boundary label",
        replace(
            "01-add-entries.md",
            "- May change: `src/cli.mjs` and its tests.",
            "- May change: `src/cli.mjs`.\n- May change: its tests.",
        ),
        "Boundary repeats `May change`",
    ),
    (
        "validation without coverage type",
        replace("01-add-entries.md", ", as new-behavior coverage", ""),
        "name the coverage type",
    ),
    (
        "validation check written as a paragraph",
        replace(
            "01-add-entries.md",
            "- `npm test` passes with a new test for this command, as new-behavior coverage.",
            "Run `npm test`.",
        ),
        "01-add-entries.md:42: write each Validation check as a bullet",
    ),
    (
        "validation with only a fenced command",
        replace(
            "01-add-entries.md",
            "- `npm test` passes with a new test for this command, as new-behavior coverage.",
            "```sh\nnpm test\n```",
        ),
        "01-add-entries.md:40: `## Validation` lists no check as a bullet",
    ),
    (
        "shared contract drift",
        replace("03-list-by-tag.md", "`added`, and `tags`", "`added`, `tags`, and `rating`"),
        (
            "03-list-by-tag.md:19: shared contract `Log file` "
            "differs from the copy in 01-add-entries.md"
        ),
    ),
    (
        "shared contract drift below a nested heading",
        replace(
            "03-list-by-tag.md",
            "`added`, and `tags`.\n",
            "`added`, and `tags`.\n\n#### Retry policy\n\nNever retry.\n",
        ),
        (
            "03-list-by-tag.md:19: shared contract `Log file` "
            "differs from the copy in 01-add-entries.md"
        ),
    ),
    (
        "shared block outside Contract",
        replace("01-add-entries.md", "## Acceptance\n", "## Acceptance\n\n### Shared: Other\n"),
        "`### Shared:` blocks belong under `## Contract`",
    ),
    (
        "duplicate numeric prefix",
        put("01-other-task.md", task("Other task", "depends_on: []")),
        "01-add-entries.md: numeric prefix is also used by 01-other-task.md",
    ),
    (
        "misnamed task file",
        put("4-export.md", "# Export\n"),
        "4-export.md: task files are named like 01-short-task-title.md",
    ),
    (
        "source map missing",
        put("source-map-reading-log-tags.md", None),
        "source-map-reading-log-tags.md: the source map does not exist",
    ),
    (
        "source id without a row",
        replace(
            "source-map-reading-log-tags.md",
            "| TEST-01 | validation | `01-add-entries.md` | |\n",
            "",
        ),
        "TEST-01 from",
    ),
    (
        "unknown source id",
        replace("source-map-reading-log-tags.md", "| TEST-01 |", "| TEST-09 |"),
        "TEST-09 is not an `id` in",
    ),
    (
        "duplicate source row",
        replace(
            "source-map-reading-log-tags.md",
            "| TEST-01 | validation",
            "| REQ-01 | validation | `01-add-entries.md` | |\n| TEST-01 | validation",
        ),
        "REQ-01 already has a row on line 5",
    ),
    (
        "unknown disposition",
        replace("source-map-reading-log-tags.md", "| TEST-01 | validation", "| TEST-01 | tested"),
        "TEST-01: disposition must be one of",
    ),
    (
        "implementation without a task",
        replace(
            "source-map-reading-log-tags.md",
            "| REQ-01 | implementation | `01-add-entries.md` |",
            "| REQ-01 | implementation | |",
        ),
        "REQ-01: an implementation item names at least one task",
    ),
    (
        "row names a missing task",
        replace(
            "source-map-reading-log-tags.md",
            "| TEST-01 | validation | `01-add-entries.md`",
            "| TEST-01 | validation | `05-gone.md`",
        ),
        "TEST-01: 05-gone.md is not a task file",
    ),
    (
        "blocker on a task without Blockers",
        replace(
            "source-map-reading-log-tags.md",
            "| NODE-01 | implementation | `02-tag-entries.md`, `03-list-by-tag.md` | |",
            "| NODE-01 | blocker | `02-tag-entries.md` | Case rule open. |\n"
            "| NODE-01b | implementation | `03-list-by-tag.md` | |",
        ),
        "NODE-01: 02-tag-entries.md has no `Blockers` line",
    ),
    (
        "no work without a reason",
        replace("source-map-reading-log-tags.md", "Excluded from v1.", ""),
        "scope.out: Sync between machines: give the reason for `no work` in the Note cell",
    ),
    (
        "source map table inside a code fence",
        put(
            "source-map-reading-log-tags.md",
            SOURCE_MAP.replace("| Source item", "```markdown\n| Source item") + "```\n",
        ),
        "source-map-reading-log-tags.md: the source map has no table",
    ),
    (
        "separator row with too few cells",
        replace("source-map-reading-log-tags.md", "| --- | --- | --- | --- |", "| --- |"),
        "source-map-reading-log-tags.md:4: the header must be followed by a `|---|` separator row",
    ),
    (
        "blank line between header and separator",
        replace("source-map-reading-log-tags.md", "| Note |\n", "| Note |\n\n"),
        "source-map-reading-log-tags.md:4: the header must be followed by a `|---|` separator row",
    ),
    (
        "row after a gap in the table",
        replace("source-map-reading-log-tags.md", "| scope.out:", "\n| scope.out:"),
        "source-map-reading-log-tags.md:11: this row is outside the table",
    ),
    (
        "wrong table header",
        replace(
            "source-map-reading-log-tags.md",
            "| Source item | Disposition | Tasks | Note |",
            "| Item | Status | Tasks | Note |",
        ),
        "the table header must be",
    ),
    (
        "section out of order",
        put(
            "01-add-entries.md",
            task("Add entries", "depends_on: []")
            .replace("## Outcome\n\nReaders can add entries from the terminal.\n\n", "")
            .replace("## Validation", "## Outcome\n\nReaders can add entries.\n\n## Validation"),
        ),
        "section `## Outcome` must come before `## Acceptance`",
    ),
    (
        "task without a source row",
        put(
            "source-map-reading-log-tags.md",
            SOURCE_MAP.replace(
                "| REQ-03 | implementation | `03-list-by-tag.md` | |",
                "| REQ-03 | implementation | `02-tag-entries.md` | |",
            ).replace("`02-tag-entries.md`, `03-list-by-tag.md`", "`02-tag-entries.md`"),
        ),
        "03-list-by-tag.md: no row in source-map-reading-log-tags.md names this task",
    ),
]


GENERATED_SOURCE_MAP = SOURCE_MAP + (
    "| TEST-02 | validation | `02-tag-entries.md` | |\n"
    "| TEST-03 | validation | `03-list-by-tag.md` | |\n"
)


class GeneratedSpecTest(ValidatorCase):
    def use_spec(self, fixture: str, source_map: str = GENERATED_SOURCE_MAP) -> None:
        files = valid_files()
        files["source-map-reading-log-tags.md"] = source_map
        self.write(files)
        self.spec.write_text((FIXTURES / fixture).read_text(encoding="utf-8"), encoding="utf-8")

    def test_a_multiline_title_keeps_the_requirement_id(self) -> None:
        self.use_spec(
            "spec-multiline-title.yaml",
            GENERATED_SOURCE_MAP.replace(
                "| REQ-01 | implementation | `01-add-entries.md` | |\n", ""
            ),
        )
        code, output = self.run_validator()
        self.assertEqual(code, 1, output)
        self.assertIn("REQ-01 from", output)

    def test_both_generated_specs_pass_with_a_complete_map(self) -> None:
        for fixture in ("spec-multiline-title.yaml", "spec-multiline-evidence.yaml"):
            with self.subTest(fixture):
                self.use_spec(fixture)
                code, output = self.run_validator()
                self.assertEqual(code, 0, output)
                self.assertIn("ok: 3 task file(s) and 8 source item(s)", output)


class FailureTest(ValidatorCase):
    def test_each_defect_is_reported(self) -> None:
        for label, change, expected in FAILURES:
            with self.subTest(label):
                for path in self.task_dir.iterdir():
                    path.unlink()
                files = valid_files()
                change(files)
                self.write(files)
                code, output = self.run_validator()
                self.assertEqual(code, 1, output)
                self.assertIn(expected, output)
                self.assertIn("failed:", output)


class SelectedFilesTest(ValidatorCase):
    def test_files_limits_reports_to_the_named_tasks(self) -> None:
        files = valid_files()
        files["00-kept-old-task.md"] = "# Old task without frontmatter\n"
        self.write(files)
        code, output = self.run_validator("--files", *VALID_TASKS)
        self.assertEqual(code, 0, output)

    def test_without_files_every_task_is_checked(self) -> None:
        files = valid_files()
        files["00-kept-old-task.md"] = "# Old task without frontmatter\n"
        self.write(files)
        code, output = self.run_validator()
        self.assertEqual(code, 1, output)
        self.assertIn("00-kept-old-task.md:1: line 1 must be `---`", output)

    def test_a_shared_contract_of_another_spec_may_differ(self) -> None:
        files = valid_files()
        files["00-old-export.md"] = task(
            "Old export",
            "depends_on: []",
            contract="### Shared: Log file\n\nThe log is one CSV line per entry.\n",
        )
        self.write(files)
        code, output = self.run_validator("--files", *VALID_TASKS)
        self.assertEqual(code, 0, output)

    def test_a_predecessor_of_another_spec_keeps_its_shared_contract(self) -> None:
        files = valid_files()
        files["00-export-log.md"] = task(
            "Export log",
            "depends_on: []",
            contract="### Shared: Log file\n\nThe log is one CSV line per entry.\n",
        )
        files["01-add-entries.md"] = task(
            "Add entries",
            "depends_on:\n  - 00-export-log.md",
            "`00-export-log.md` creates the log file.",
        )
        self.write(files)
        code, output = self.run_validator("--files", *VALID_TASKS)
        self.assertEqual(code, 1, output)
        self.assertIn(
            "01-add-entries.md:19: shared contract `Log file` differs from the copy in "
            "00-export-log.md",
            output,
        )
        # Task 03 needs the producer only through 02 and 01, which still binds it.
        self.assertIn(
            "03-list-by-tag.md:19: shared contract `Log file` differs from the copy in "
            "00-export-log.md",
            output,
        )

    def test_a_predecessor_of_another_spec_binds_only_the_tasks_that_need_it(self) -> None:
        report = "### Shared: Report command\n\n`reading-log report` prints one line per entry.\n"
        files = valid_files()
        files["00-format-report.md"] = task(
            "Format report",
            "depends_on: []",
            contract=report + "\n### Shared: Log file\n\nThe log is one CSV line per entry.\n",
        )
        files["01-add-entries.md"] = task(
            "Add entries",
            "depends_on:\n  - 00-format-report.md",
            "`00-format-report.md` provides `reading-log report`.",
            contract=report,
        )
        # Tasks 02 and 03 form a separate branch that never needs the CSV producer.
        files["02-tag-entries.md"] = task("Tag entries", "depends_on: []")
        self.write(files)
        code, output = self.run_validator("--files", *VALID_TASKS)
        self.assertEqual(code, 0, output)

    def test_a_kept_task_of_this_spec_keeps_its_shared_contract(self) -> None:
        files = valid_files()
        files["00-seed-log.md"] = task(
            "Seed log",
            "depends_on: []",
            contract="### Shared: Log file\n\nThe log is one CSV line per entry.\n",
        )
        files["source-map-reading-log-tags.md"] = SOURCE_MAP + (
            "| scope.in: Seed data | implementation | `00-seed-log.md` | |\n"
        )
        self.write(files)
        code, output = self.run_validator("--files", *VALID_TASKS)
        self.assertEqual(code, 1, output)
        self.assertIn(
            "01-add-entries.md:18: shared contract `Log file` differs from the copy in "
            "00-seed-log.md",
            output,
        )

    def test_a_selected_task_is_compared_with_every_kept_copy(self) -> None:
        files = valid_files()
        replace("02-tag-entries.md", "The log is a JSON array", "The log is a CSV file")(files)
        self.write(files)
        code, output = self.run_validator("--files", "03-list-by-tag.md")
        self.assertEqual(code, 1, output)
        self.assertIn(
            "03-list-by-tag.md:19: shared contract `Log file` differs from the copy in "
            "02-tag-entries.md",
            output,
        )

    def test_a_kept_predecessor_with_a_missing_predecessor_is_reported(self) -> None:
        files = valid_files()
        replace("02-tag-entries.md", "01-add-entries.md", "00-gone.md")(files)
        self.write(files)
        code, output = self.run_validator("--files", "03-list-by-tag.md")
        self.assertEqual(code, 1, output)
        self.assertIn("02-tag-entries.md:3: `depends_on` entry 00-gone.md does not exist", output)

    def test_a_kept_predecessor_keeps_its_older_prose(self) -> None:
        files = valid_files()
        replace(
            "02-tag-entries.md",
            "- Needs first: `01-add-entries.md` stores",
            "- Needs first: The add command stores",
        )(files)
        self.write(files)
        code, output = self.run_validator("--files", "03-list-by-tag.md")
        self.assertEqual(code, 0, output)

    def test_a_kept_predecessor_without_frontmatter_is_reported(self) -> None:
        files = valid_files()
        replace("02-tag-entries.md", "state: pending\n---\n", "")(files)
        self.write(files)
        code, output = self.run_validator("--files", "03-list-by-tag.md")
        self.assertEqual(code, 1, output)
        self.assertIn(
            "02-tag-entries.md:1: the frontmatter block has no closing `---` line", output
        )

    def test_kept_tasks_still_count_for_transitive_edges(self) -> None:
        files = valid_files()
        files["03-list-by-tag.md"] = (
            files["03-list-by-tag.md"]
            .replace(
                "depends_on:\n  - 02-tag-entries.md",
                "depends_on:\n  - 01-add-entries.md\n  - 02-tag-entries.md",
            )
            .replace(
                "- Needs first: `02",
                "- Needs first: `01-add-entries.md` stores entries.\n- Needs first: `02",
            )
        )
        self.write(files)
        code, output = self.run_validator("--files", "03-list-by-tag.md")
        self.assertEqual(code, 1, output)
        self.assertIn("which 02-tag-entries.md already requires", output)

    def test_a_task_of_this_run_is_pending_without_a_failure_list(self) -> None:
        gap = '\nfailure:\n  - "Acceptance 2: no test"'
        pending = "03-list-by-tag.md:4: a task written in this run has `state: pending`"
        for label, frontmatter, expected in (
            ("done", "state: done", pending),
            ("running", "state: running", pending),
            ("failed", "state: failed" + gap, pending),
            (
                "pending with a failure list",
                "state: pending" + gap,
                "03-list-by-tag.md:5: only a task with `state: failed` has a `failure` list",
            ),
        ):
            with self.subTest(label):
                files = valid_files()
                replace("03-list-by-tag.md", "state: pending", frontmatter)(files)
                self.write(files)
                code, output = self.run_validator("--files", "03-list-by-tag.md")
                self.assertEqual(code, 1, output)
                self.assertIn(expected, output)

    def test_an_unknown_state_names_the_four_states(self) -> None:
        # The kept predecessor 01 and the task 03 of this run each get one report.
        files = valid_files()
        replace("01-add-entries.md", "state: pending", "state: blocked")(files)
        replace("03-list-by-tag.md", "state: pending", "state: blocked")(files)
        self.write(files)
        code, output = self.run_validator("--files", "03-list-by-tag.md")
        self.assertEqual(code, 1, output)
        message = "`state` must be `pending`, `running`, `failed`, or `done`"
        self.assertIn(f"01-add-entries.md:3: {message}", output)
        self.assertIn(f"03-list-by-tag.md:4: {message}", output)
        self.assertIn("failed: 2 problem(s)", output)

    def test_a_kept_predecessor_may_be_past_pending(self) -> None:
        # 01 is a direct predecessor of 02 and an indirect predecessor of 03.
        for label, frontmatter in (
            ("done", "state: done\n"),
            ("running", "state: running\n"),
            (
                "failed with one gap",
                'state: failed\nfailure:\n  - "Acceptance 2: no test covers an empty tag list"\n',
            ),
            (
                "failed with an escaped quote and backslash",
                'state: failed\nfailure:\n  - "Acceptance 3: `\\"a\\\\b\\"` is not parsed"\n',
            ),
            (
                "failed with two gaps",
                (
                    'state: failed\nfailure:\n  - "Acceptance 1: no test"\n'
                    '  - "Acceptance 2: no test"\n'
                ),
            ),
        ):
            for selection in (("02-tag-entries.md", "03-list-by-tag.md"), ("03-list-by-tag.md",)):
                with self.subTest(label, selection=selection):
                    files = valid_files()
                    replace("01-add-entries.md", "state: pending\n", frontmatter)(files)
                    self.write(files)
                    code, output = self.run_validator("--files", *selection)
                    self.assertEqual(code, 0, output)

    def test_a_kept_predecessor_with_a_bad_failure_list_is_reported(self) -> None:
        empty = "01-add-entries.md:4: `failure` lists at least one verifier gap"
        block = "01-add-entries.md:4: write `failure` as a block list, one gap per line"
        item = "01-add-entries.md:5: each `failure` item is `- ` and one double-quoted string"
        not_failed = "01-add-entries.md:4: only a task with `state: failed` has a `failure` list"
        failed = "state: failed\nfailure:"
        for label, frontmatter, expected in (
            (
                "no failure key",
                "state: failed\n",
                (
                    "01-add-entries.md:3: a task with `state: failed` lists its verifier gaps "
                    "under `failure`"
                ),
            ),
            ("empty flow list", failed + " []\n", empty),
            ("no items", failed + "\n", empty),
            ("flow list", failed + ' ["Acceptance 2: no test"]\n', block),
            ("inline string", failed + ' "Acceptance 2: no test"\n', block),
            ("unquoted item", failed + "\n  - Acceptance 2: no test\n", item),
            ("single-quoted item", failed + "\n  - 'Acceptance 2: no test'\n", item),
            ("item indented four spaces", failed + '\n    - "Acceptance 2: no test"\n', item),
            ("item indented with a tab", failed + '\n\t- "Acceptance 2: no test"\n', item),
            ("unescaped quote", failed + '\n  - "Acceptance 2: "tag" is empty"\n', item),
            ("unknown escape", failed + '\n  - "Acceptance 2: no test\\n"\n', item),
            ("escaped closing quote", failed + '\n  - "Acceptance 2: no test\\"\n', item),
            ("text after the string", failed + '\n  - "Acceptance 2: no test" # gap\n', item),
            ("empty string", failed + '\n  - ""\n', item),
            ("blank string", failed + '\n  - "  "\n', item),
            (
                "second item malformed",
                failed + '\n  - "Acceptance 1: no test"\n  - Acceptance 2\n',
                item.replace(":5:", ":6:"),
            ),
            *(
                (
                    f"{state} with a failure list",
                    f'state: {state}\nfailure:\n  - "Acceptance 2: no test"\n',
                    not_failed,
                )
                for state in ("done", "running", "pending")
            ),
        ):
            with self.subTest(label):
                files = valid_files()
                replace("01-add-entries.md", "state: pending\n", frontmatter)(files)
                self.write(files)
                code, output = self.run_validator("--files", "03-list-by-tag.md")
                self.assertEqual(code, 1, output)
                self.assertIn(expected, output)

    def test_a_kept_task_that_is_not_utf8_is_ignored(self) -> None:
        self.write(valid_files())
        (self.task_dir / "00-kept-binary.md").write_bytes(b"---\n\xff\n")
        code, output = self.run_validator("--files", *VALID_TASKS)
        self.assertEqual(code, 0, output)

    def test_a_task_that_is_not_utf8_is_reported(self) -> None:
        self.write(valid_files())
        (self.task_dir / "00-kept-binary.md").write_bytes(b"---\n\xff\n")
        code, output = self.run_validator()
        self.assertEqual(code, 1, output)
        self.assertIn("00-kept-binary.md: the file is not UTF-8 text", output)

    def test_an_empty_selection_audits_the_map_of_done_tasks(self) -> None:
        files = valid_files()
        for name in VALID_TASKS:
            replace(name, "state: pending", "state: done")(files)
        self.write(files)
        code, output = self.run_validator("--files")
        self.assertEqual(code, 0, output)
        self.assertIn("ok: 0 task file(s) and 6 source item(s)", output)

    def test_an_empty_selection_still_checks_the_map(self) -> None:
        files = valid_files()
        files["source-map-reading-log-tags.md"] = SOURCE_MAP.replace("| TEST-01 |", "| TEST-09 |")
        self.write(files)
        code, output = self.run_validator("--files")
        self.assertEqual(code, 1, output)
        self.assertIn("TEST-09 is not an `id` in", output)

    def test_a_source_map_or_spec_that_is_not_utf8_is_reported(self) -> None:
        for label, path in (
            ("source map", self.task_dir / "source-map-reading-log-tags.md"),
            ("spec", self.spec),
        ):
            with self.subTest(label):
                self.spec.write_text(SPEC, encoding="utf-8")
                self.write(valid_files())
                path.write_bytes(b"# Source\n\xff\n")
                code, output = self.run_validator()
                self.assertEqual(code, 1, output)
                self.assertIn(f"{path.name}: the file is not UTF-8 text", output)

    def test_unknown_selected_file_is_reported(self) -> None:
        self.write(valid_files())
        code, output = self.run_validator("--files", "07-missing.md")
        self.assertEqual(code, 1, output)
        self.assertIn("07-missing.md: not a task file", output)


if __name__ == "__main__":
    unittest.main()
