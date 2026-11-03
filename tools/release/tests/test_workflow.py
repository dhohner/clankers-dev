from __future__ import annotations

import os
import re
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github/workflows/release.yml"


def context(
    *,
    event_name: str = "workflow_run",
    repository: str = "dhohner/clankers-dev",
    ref: str = "refs/heads/main",
    conclusion: str = "success",
    event: str = "push",
    branch: str = "main",
    source_repository: str = "dhohner/clankers-dev",
) -> SimpleNamespace:
    return SimpleNamespace(
        event_name=event_name,
        repository=repository,
        ref=ref,
        sha="1" * 40,
        event=SimpleNamespace(
            workflow_run=SimpleNamespace(
                conclusion=conclusion,
                event=event,
                head_branch=branch,
                head_repository=SimpleNamespace(full_name=source_repository),
                head_sha="2" * 40 if event_name == "workflow_run" else "",
            )
        ),
    )


def evaluate(expression: str, **context: SimpleNamespace) -> object:
    # These workflow expressions use only property access, equality, and boolean operators.
    return eval(
        expression.replace("&&", " and ").replace("||", " or "),
        {"__builtins__": {}, **context},
    )


class WorkflowTests(unittest.TestCase):
    def test_only_eligible_jobs_enter_the_queue_without_replacing_pending_jobs(
        self,
    ) -> None:
        workflow = WORKFLOW.read_text()
        self.assertNotRegex(workflow, r"(?m)^concurrency:")
        concurrency = re.search(
            r"^    concurrency:\n((?:      .+\n)+)", workflow, re.MULTILINE
        )
        self.assertIsNotNone(concurrency)
        self.assertIn("group: release-clankers", concurrency[1])
        self.assertIn("queue: max", concurrency[1])
        self.assertIn("cancel-in-progress: false", concurrency[1])

    def test_publication_guard(self) -> None:
        workflow = WORKFLOW.read_text()
        guard = re.search(r"^    if: >-\n((?:      .+\n)+)", workflow, re.MULTILINE)
        self.assertIsNotNone(guard)
        expression = " ".join(guard[1].splitlines())
        cases = [
            ({}, True),
            ({"event_name": "workflow_dispatch"}, True),
            ({"conclusion": "failure"}, False),
            ({"conclusion": "cancelled"}, False),
            ({"conclusion": "skipped"}, False),
            ({"conclusion": ""}, False),
            ({"event": "pull_request"}, False),
            ({"event": "workflow_dispatch"}, False),
            ({"branch": "feature"}, False),
            ({"source_repository": "someone/clankers-dev"}, False),
            ({"repository": "someone/clankers-dev"}, False),
            ({"ref": "refs/heads/feature"}, False),
            ({"event_name": "workflow_dispatch", "ref": "refs/heads/feature"}, False),
        ]
        for values, expected in cases:
            with self.subTest(values=values):
                self.assertEqual(
                    bool(evaluate(expression, github=context(**values))), expected
                )

    def test_checkout_and_preparation_use_the_tested_commit(self) -> None:
        workflow = WORKFLOW.read_text()
        checkout = re.search(
            r"^          ref: \$\{\{ (.+) \}\}", workflow, re.MULTILINE
        )
        prepare = workflow.split("      - name: Prepare distribution\n", 1)[1]
        revision = re.search(r"SOURCE_REVISION: \$\{\{ (.+) \}\}", prepare)
        self.assertIsNotNone(checkout)
        self.assertIsNotNone(revision)
        for event_name, expected in (
            ("workflow_run", "2" * 40),
            ("workflow_dispatch", "1" * 40),
        ):
            with self.subTest(event=event_name):
                github = context(event_name=event_name)
                self.assertEqual(evaluate(checkout[1], github=github), expected)
                self.assertEqual(evaluate(revision[1], github=github), expected)

    def test_signing_and_push_require_a_publication_decision(self) -> None:
        workflow = WORKFLOW.read_text()
        for step in ("Sign distribution commit", "Publish distribution"):
            block = workflow.split(f"      - name: {step}\n", 1)[1]
            block = block.split("\n      - ", 1)[0]
            condition = re.search(r"^        if: (.+)", block, re.MULTILINE)
            self.assertIsNotNone(condition)
            for decision, expected in (("true", True), ("false", False), ("", False)):
                with self.subTest(step=step, decision=decision):
                    steps = SimpleNamespace(
                        prepare=SimpleNamespace(
                            outputs=SimpleNamespace(publish=decision)
                        )
                    )
                    self.assertEqual(evaluate(condition[1], steps=steps), expected)

    def test_publication_summary(self) -> None:
        step = WORKFLOW.read_text().split("      - name: Summarize publication\n", 1)[1]
        step = step.split("\n      - ", 1)[0]
        script = textwrap.dedent(step.split("        run: |\n", 1)[1])
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            checkout = directory / "distribution"
            checkout.mkdir()
            env = {
                **os.environ,
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_AUTHOR_NAME": "Test",
                "GIT_AUTHOR_EMAIL": "test@example.com",
                "GIT_COMMITTER_NAME": "Test",
                "GIT_COMMITTER_EMAIL": "test@example.com",
            }
            for args in (
                ("init", "--quiet"),
                ("commit", "--quiet", "--allow-empty", "-m", "release"),
            ):
                subprocess.run(["git", "-C", str(checkout), *args], env=env, check=True)
            commit = subprocess.check_output(
                ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
            ).strip()
            cases = [
                (
                    "success",
                    "true",
                    "success",
                    f"https://github.com/dhohner/clankers/commit/{commit}",
                ),
                ("success", "false", "skipped", ""),
                ("failure", "", "skipped", "Publication failed"),
                ("success", "true", "failure", "Publication failed"),
                ("success", "true", "skipped", "Publication failed"),
            ]
            for prepared, publish, published, expected in cases:
                with self.subTest(
                    prepared=prepared, publish=publish, published=published
                ):
                    summary = directory / "summary"
                    summary.write_text("")
                    subprocess.run(
                        ["bash", "-euo", "pipefail", "-c", script],
                        cwd=directory,
                        env={
                            **env,
                            "PREPARE_OUTCOME": prepared,
                            "SHOULD_PUBLISH": publish,
                            "PUBLISH_OUTCOME": published,
                            "GITHUB_STEP_SUMMARY": str(summary),
                        },
                        check=True,
                        capture_output=True,
                    )
                    if expected:
                        self.assertIn(expected, summary.read_text())
                    else:
                        self.assertEqual(summary.read_text(), "")


if __name__ == "__main__":
    unittest.main()
