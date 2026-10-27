from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from interview_support import InterviewHarness, wait_for_exit

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("promotion_eval", ROOT / "evals/toon-cli/evaluate.py")


@contextmanager
def interview_commands(test, run):
    owner = unittest.TestCase()
    test.addCleanup(owner.doCleanups)
    owner.enterContext(
        mock.patch.dict("os.environ", {"TO_PRD_INTERVIEW_REGISTRY": run["registry"]})
    )
    commands = InterviewHarness(owner, Path(run["transport"]).parent, Path(run["session_dir"]))
    try:
        yield commands
    finally:
        if not owner.doCleanups():
            raise AssertionError("interview cleanup failed")


class PromotionEvaluationTests(unittest.TestCase):
    def load_tool(self):
        module = importlib.util.module_from_spec(SPEC)
        SPEC.loader.exec_module(module)
        return module

    def test_gate_rejects_each_invalid_or_incomplete_evidence_state(self):
        # Bypassing any derived check would admit the corresponding invalid evidence.
        tool = self.load_tool()
        fixture = tool.synthetic_results()
        fixture["provenance"] = "observed"
        self.assertTrue(tool.build_report(fixture)["promotion_eligible"])
        changes = [
            ("tie", lambda d: d["trials"][0]["candidate"].update(input_tokens=1000)),
            ("increase", lambda d: d["trials"][0]["candidate"].update(input_tokens=1001)),
            ("lost success", lambda d: d["trials"][0]["candidate"].update(outcome="failure")),
            ("timeout", lambda d: d["trials"][0]["candidate"].update(outcome="timeout")),
            ("repetitions", lambda d: d["trials"].pop()),
            ("missing tests", lambda d: d.pop("contract_tests")),
            ("failed tests", lambda d: d["contract_tests"].update(outcome="failure")),
            ("source mismatch", lambda d: d["trials"][0]["candidate"].update(source="f" * 64)),
            ("boolean", lambda d: d["trials"][0]["candidate"].update(input_tokens=True)),
            ("negative", lambda d: d["trials"][0]["candidate"].update(retries=-1)),
            ("arithmetic", lambda d: d["trials"][0]["candidate"].update(total_tokens=1)),
            ("missing outcome", lambda d: d["trials"][0]["candidate"].pop("outcome")),
            ("duplicate", lambda d: d["trials"].append(copy.deepcopy(d["trials"][0]))),
            ("prompt mismatch", lambda d: d["trials"][0]["candidate"].update(prompt="f" * 64)),
            ("model mismatch", lambda d: d["trials"][0]["candidate"].update(model="other")),
            (
                "source fingerprint",
                lambda d: d["sources"]["candidate"]["files"].update({"scripts/x.py": "f" * 64}),
            ),
            ("payload missing", lambda d: d["payloads"].pop()),
            ("no tokenizer", lambda d: d["tokenizer"].pop("version")),
            ("synthetic payload", lambda d: d["payloads"][0].update(provenance="synthetic")),
            (
                "authorization",
                lambda d: d["conditions"].append(
                    {"kind": "missing_authorization", "reason": "not approved"}
                ),
            ),
            (
                "dependency",
                lambda d: d["conditions"].append(
                    {"kind": "missing_dependency", "reason": "install tokenizer"}
                ),
            ),
        ]
        for name, mutate in changes:
            with self.subTest(name=name):
                data = copy.deepcopy(fixture)
                mutate(data)
                # Ignore caller assertions and derive all decisions again.
                data["promotion_eligible"] = True
                report = tool.build_report(data)
                self.assertFalse(report["promotion_eligible"])
                self.assertTrue(any(not c["passed"] for c in report["checks"].values()))
        self.assertEqual(
            tool.build_report(fixture), tool.build_report(json.loads(json.dumps(fixture)))
        )

    def test_token_tie_and_increase_fail_savings_even_with_valid_arithmetic(self):
        # Changing strict less-than to less-than-or-equal admits the tie.
        tool = self.load_tool()
        for extra in (0, 1):
            data = tool.synthetic_results()
            data["trials"][0]["candidate"].update(
                input_tokens=920 + extra, total_tokens=1000 + extra
            )
            self.assertFalse(tool.build_report(data)["checks"]["savings"]["passed"])

    def test_complete_payloads_are_encoded_before_token_adapter_counts(self):
        # Reducing answers or skipping a family loses complete serialization evidence.
        tool = self.load_tool()
        corpus = tool.payload_corpus()
        self.assertEqual(set(corpus), {"schema", "examples", "validation", "inspection", "answers"})
        self.assertIn("fixture answer 30", json.dumps(corpus["answers"]))
        seen = []

        def tokenizer(text):
            seen.append(text)
            return [7, 8, 9]

        result = tool.measure(corpus, tokenizer, {"name": "test", "version": "1", "model": "test"})
        self.assertEqual(len(seen), 10)
        self.assertTrue(all(p["yaml_tokens"] == p["toon_tokens"] == 3 for p in result["payloads"]))
        self.assertEqual(result["conditions"], [])
        unavailable = tool.measure(corpus, None, {"name": "missing"})
        self.assertEqual(unavailable["payloads"], [])
        self.assertEqual(unavailable["conditions"][0]["kind"], "missing_dependency")

    def test_plan_isolates_every_arm_and_records_identical_inputs(self):
        # Sharing any mutable workspace contaminates paired trials.
        tool = self.load_tool()
        with tempfile.TemporaryDirectory() as directory:
            plan = tool.make_plan(Path(directory), 3)
            self.assertEqual(len(plan["runs"]), 42)
            for key in ("workspace", "output_root", "session_dir", "registry"):
                self.assertEqual(len({r[key] for r in plan["runs"]}), 42)
            for baseline, candidate in zip(plan["runs"][::2], plan["runs"][1::2], strict=True):
                for key in ("prompt", "fixture", "permissions", "repetition"):
                    self.assertEqual(baseline[key], candidate[key])
                self.assertEqual(candidate["operational_selector"], ["--format", "toon"])
            with self.assertRaises(ValueError):
                tool.make_plan(Path(directory), 2)

    def test_candidate_snapshot_rejects_symlinks_before_reading_bytes(self):
        for kind in ("external_parent", "internal_parent", "file", "dangling_parent"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                tool = self.load_tool()
                repo = Path(directory)
                skill = repo / "skill"
                skill.mkdir()
                actual = repo / "external" if kind != "internal_parent" else skill / "actual"
                actual.mkdir()
                (actual / "fixture.py").write_bytes(b"external fixture bytes")
                scripts = skill / "scripts"
                if kind == "file":
                    scripts.mkdir()
                    (scripts / "fixture.py").symlink_to(actual / "fixture.py")
                else:
                    scripts.symlink_to(
                        repo / "missing" if kind == "dangling_parent" else actual,
                        target_is_directory=True,
                    )
                destination = repo / "snapshot"
                with (
                    mock.patch.object(tool, "SKILL", skill),
                    mock.patch.object(tool, "REPO", repo),
                    mock.patch.object(
                        tool, "git_paths", side_effect=lambda _: ["skill/scripts/fixture.py"]
                    ),
                    mock.patch("subprocess.check_output", return_value="revision"),
                    mock.patch.object(
                        Path, "read_bytes", side_effect=AssertionError("read source")
                    ),
                    self.assertRaisesRegex(ValueError, "source symlink forbidden"),
                ):
                    tool.snapshot(destination, "candidate")
                self.assertFalse((destination / "scripts/fixture.py").exists())

    def test_snapshots_hash_exact_files_without_changing_the_worktree(self):
        # A mutable source or missing manifest permits source drift.
        tool = self.load_tool()
        with tempfile.TemporaryDirectory() as directory:
            snapshot = tool.snapshot(Path(directory) / "candidate", "candidate")
            self.assertEqual(snapshot["fingerprint"], tool.digest(snapshot["files"]))
            self.assertIn("scripts/toon.py", snapshot["files"])
            self.assertIn("tests/test_prd_bundle_cli.py", snapshot["files"])
            source = Path(directory) / "candidate" / "scripts/toon.py"
            self.assertEqual(source.stat().st_mode & 0o222, 0)
            self.assertEqual(source.parent.stat().st_mode & 0o222, 0)

    def test_candidate_snapshot_includes_staged_additions_and_rename_destinations(self):
        # HEAD and untracked paths alone omit staged additions and rename destinations.
        tool = self.load_tool()
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            skill = repo / "skill"
            working = {
                "scripts/existing.py": b"modified existing working bytes\n",
                "scripts/staged.py": b"working edits after staging\n",
                "scripts/renamed.py": b"working rename destination\n",
                "scripts/untracked.py": b"untracked working bytes\n",
            }
            for name, content in working.items():
                path = skill / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)

            def git_read(command, **kwargs):
                if command[1] == "rev-parse":
                    return "a" * 40 + "\n"
                if command[1] == "ls-tree":
                    paths = ["skill/scripts/existing.py", "skill/scripts/old-name.py"]
                elif command[1:3] == ["ls-files", "--others"]:
                    paths = ["skill/scripts/untracked.py"]
                elif command[1:3] == ["ls-files", "--cached"]:
                    paths = [
                        "skill/scripts/existing.py",
                        "skill/scripts/staged.py",
                        "skill/scripts/renamed.py",
                    ]
                else:
                    self.fail(f"unexpected Git operation: {command}")
                separator = "\0" if "-z" in command else "\n"
                output = separator.join(paths) + separator
                return output if kwargs.get("text") else output.encode("utf-8")

            destination = repo / "snapshot"
            with (
                mock.patch.object(tool, "SKILL", skill),
                mock.patch.object(tool, "REPO", repo),
                mock.patch("subprocess.check_output", side_effect=git_read),
            ):
                manifest = tool.snapshot(destination, "candidate")
            self.assertEqual(
                manifest["files"],
                {name: hashlib.sha256(content).hexdigest() for name, content in working.items()},
            )
            for name, content in working.items():
                self.assertEqual((destination / name).read_bytes(), content)
            self.assertFalse((destination / "scripts/old-name.py").exists())

    def test_snapshot_captures_unicode_and_quoted_paths_from_all_git_lists(self):
        # Git C quoting must not silently remove files from an otherwise valid manifest.
        tool = self.load_tool()
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            skill = repo / "skill"
            working = {
                "scripts/plain.py": b"plain source\n",
                "scripts/tête.py": b"HEAD source\n",
                "scripts/café.py": b"staged working source\n",
                'scripts/quoted"name.py': b"untracked source\n",
            }
            for name, content in working.items():
                path = skill / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            quoted = {
                "scripts/tête.py": r'"skill/scripts/t\303\252te.py"',
                "scripts/café.py": r'"skill/scripts/caf\303\251.py"',
                'scripts/quoted"name.py': r'"skill/scripts/quoted\"name.py"',
            }

            def git_read(command, **kwargs):
                if command[1] == "rev-parse":
                    return "a" * 40 + "\n"
                if command[1] == "ls-tree":
                    names = ["scripts/plain.py", "scripts/tête.py"]
                elif command[1:3] == ["ls-files", "--cached"]:
                    names = ["scripts/plain.py", "scripts/café.py"]
                elif command[1:3] == ["ls-files", "--others"]:
                    names = ['scripts/quoted"name.py']
                else:
                    self.fail(f"unexpected Git operation: {command}")
                if "-z" in command:
                    output = "\0".join("skill/" + name for name in names) + "\0"
                else:
                    output = "\n".join(quoted.get(name, "skill/" + name) for name in names) + "\n"
                return output if kwargs.get("text") else output.encode("utf-8")

            destination = repo / "snapshot"
            with (
                mock.patch.object(tool, "SKILL", skill),
                mock.patch.object(tool, "REPO", repo),
                mock.patch("subprocess.check_output", side_effect=git_read),
            ):
                manifest = tool.snapshot(destination, "candidate")
            self.assertEqual(
                manifest["files"],
                {name: hashlib.sha256(content).hexdigest() for name, content in working.items()},
            )
            for name, content in working.items():
                self.assertEqual((destination / name).read_bytes(), content)

    def test_cli_writes_reproducible_reports_and_missing_tokenizer_evidence(self):
        # Omitting evidence files or accepting malformed input hides partial results.
        tool = self.load_tool()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(tool.main(["synthetic", "--output", str(root / "synthetic")]), 0)
            first = (root / "synthetic/report.json").read_bytes()
            self.assertTrue((root / "synthetic/report.md").exists())
            tool.main(
                [
                    "report",
                    "--input",
                    str(root / "synthetic/results.json"),
                    "--output",
                    str(root / "replay"),
                ]
            )
            self.assertEqual(first, (root / "replay/report.json").read_bytes())
            tool.main(
                ["measure", "--output", str(root / "measurement"), "--model", "unavailable-model"]
            )
            measurement = json.loads((root / "measurement/measurements.json").read_text())
            self.assertEqual(measurement["conditions"][0]["kind"], "missing_dependency")
            bad = root / "bad.json"
            bad.write_text('{"schema_version": 1, "trials": [null]}')
            tool.main(["report", "--input", str(bad), "--output", str(root / "bad")])
            report = json.loads((root / "bad/report.json").read_text())
            self.assertFalse(report["promotion_eligible"])
            self.assertEqual(report["completeness"], "incomplete")

    def test_conditions_check_includes_generated_missing_evidence_in_both_reports(self):
        # Checking conditions before missing evidence is generated contradicts the report.
        tool = self.load_tool()
        for missing in ("contract_tests", "sources", "payloads", "trials", "schema_version"):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                data = tool.synthetic_results()
                data["provenance"] = "observed"
                del data[missing]
                tool.write_json(root / "results.json", data)
                tool.main(["report", "--input", str(root / "results.json"), "--output", directory])
                report = json.loads((root / "report.json").read_text())
                self.assertIn("missing_evidence", [item["kind"] for item in report["conditions"]])
                self.assertFalse(report["checks"]["conditions"]["passed"])
                self.assertEqual(report["completeness"], "incomplete")
                self.assertFalse(report["promotion_eligible"])
                self.assertIn("- conditions: FAIL", (root / "report.md").read_text())
        complete = tool.synthetic_results()
        complete["provenance"] = "observed"
        report = tool.build_report(complete)
        self.assertEqual(report["conditions"], [])
        self.assertTrue(report["checks"]["conditions"]["passed"])

    def test_interview_fixtures_validate_and_replay_all_answers_without_a_server(self):
        # An invalid round or submit makes the controlled interview impossible to replay.
        tool = self.load_tool()
        corpus = tool.workflow_corpus()
        from scripts.interview.answers import validate_submit
        from scripts.interview.rounds import validate_round

        round_ = validate_round(json.loads(corpus["fixtures"]["round.json"]))
        answers = validate_submit(round_, json.loads(corpus["fixtures"]["answers.json"]))
        self.assertEqual(len(answers["answers"]), 30)
        self.assertEqual(answers["answers"][-1]["written"], "fixture answer 30")

    def test_transport_selects_candidate_toon_and_keeps_templates_yaml(self):
        # A prompt selector breaks comparability; unconditional selection breaks templates.
        tool = self.load_tool()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            transport = tool.write_transport(root, ROOT, "candidate")
            result = subprocess.run(
                [sys.executable, str(transport), "examples", "--full"],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("examples[", result.stdout)
            template = subprocess.run(
                [sys.executable, str(transport), "template", "--blocks", "requirements"],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(template.returncode, 0, template.stderr)
            self.assertIn("schema_version:", template.stdout)
            self.assertIn("blocks:", template.stdout)

    def test_transport_preserves_example_name_after_argument_terminator(self):
        # A selector appended after -- becomes a positional argument and changes outcomes.
        tool = self.load_tool()
        with tempfile.TemporaryDirectory() as directory:
            for arm in ("baseline", "candidate"):
                root = Path(directory) / arm
                root.mkdir()
                transport = tool.write_transport(root, ROOT, arm)
                result = subprocess.run(
                    [sys.executable, str(transport), "examples", "--", "minimal-prd"],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                with self.subTest(arm=arm):
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("minimal-prd", result.stdout)

    def test_script_entrypoint_creates_selected_evidence_directory(self):
        # Removing the entrypoint silently discards the documented commands.
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, SPEC.origin, "synthetic", "--output", directory],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((Path(directory) / "report.json").exists())

    def test_completed_baseline_failure_retains_outcome_without_hiding_completeness(self):
        # A recorded task failure differs from a runner that failed to collect evidence.
        tool = self.load_tool()
        data = tool.synthetic_results()
        data["provenance"] = "observed"
        data["trials"][0]["baseline"]["outcome"] = "failure"
        report = tool.build_report(data)
        self.assertEqual(report["completeness"], "complete")
        self.assertTrue(report["promotion_eligible"])

    def test_repetitions_cannot_change_prompts_or_permissions_together(self):
        # Pair equality alone misses changes to both arms between repetitions.
        tool = self.load_tool()
        for key in ("prompt", "fixture", "permissions"):
            data = tool.synthetic_results()
            data["provenance"] = "observed"
            for arm in ("baseline", "candidate"):
                data["trials"][1][arm][key] = "f" * 64
            self.assertFalse(tool.build_report(data)["checks"]["paired_trials"]["passed"])

    def test_interview_cleanup_stops_server_after_incomplete_answers_and_failed_wait(self):
        # Missing fixture answers must not leave the server alive after a failed replay.
        tool = self.load_tool()
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        run = next(r for r in tool.make_plan(root, 3)["runs"] if r["case"] == "interview")
        tool.seed_interview(run, ROOT)
        answers = Path(run["session_dir"]) / "interview/answers/ROUND-01.json"
        answers.rename(answers.with_name("ROUND-99.json"))
        with (
            self.assertRaisesRegex(AssertionError, "still waiting"),
            interview_commands(self, run) as commands,
        ):
            pending = commands.start_ask(Path(run["workspace"]) / "round.json")
            pending.wait_started()
            pid = commands.server_pid()
            pending.finish(timeout=0)
        self.assertTrue(wait_for_exit(pid), "failed interview left its server alive")

    def test_seeded_interview_replays_without_requesting_user_decisions(self):
        # Missing stored answers would start a server and wait for a real user.
        tool = self.load_tool()
        with tempfile.TemporaryDirectory() as directory:
            plan = tool.make_plan(Path(directory), 3)
            run = next(r for r in plan["runs"] if r["case"] == "interview")
            tool.seed_interview(run, ROOT)
            self.assertTrue((Path(run["session_dir"]) / "interview/answers/ROUND-01.json").exists())
            with interview_commands(self, run) as commands:
                result = commands.ask(Path(run["workspace"]) / "round.json")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("fixture answer 30", result.stdout)
                self.assertFalse(Path(run["registry"]).exists())
                ended = commands.end()
                self.assertEqual(ended.returncode, 0, ended.stderr)

    def test_tokenizer_cache_matches_library_precedence_and_disabled_cache(self):
        # Checking a different cache than tiktoken can permit a network download.
        tool = self.load_tool()
        cases = [
            ({}, Path("/fixture-temp/data-gym-cache")),
            ({"DATA_GYM_CACHE_DIR": "/alternate"}, Path("/alternate")),
            ({"TIKTOKEN_CACHE_DIR": "/primary"}, Path("/primary")),
            (
                {"TIKTOKEN_CACHE_DIR": "/primary", "DATA_GYM_CACHE_DIR": "/alternate"},
                Path("/primary"),
            ),
            ({"TIKTOKEN_CACHE_DIR": "", "DATA_GYM_CACHE_DIR": "/alternate"}, None),
            ({"DATA_GYM_CACHE_DIR": ""}, None),
        ]
        with mock.patch("tempfile.gettempdir", return_value="/fixture-temp"):
            for environment, expected in cases:
                with self.subTest(environment=environment):
                    self.assertEqual(tool.tokenizer_cache_directory(environment), expected)

    def test_corrupt_tokenizer_cache_never_attempts_network_repair(self):
        # tiktoken would redownload a vocabulary after detecting corrupt cached bytes.
        tool = self.load_tool()
        fake = SimpleNamespace(
            encoding_for_model=lambda model: SimpleNamespace(encode=lambda text, **kw: [1])
        )
        with tempfile.TemporaryDirectory() as directory:
            url = "https://openaipublic.blob.core.windows.net/encodings/o200k_base.tiktoken"
            (Path(directory) / hashlib.sha1(url.encode()).hexdigest()).write_bytes(b"corrupt")
            with (
                mock.patch.dict(sys.modules, {"tiktoken": fake}),
                mock.patch("importlib.metadata.version", return_value="0.12.0"),
                mock.patch.dict("os.environ", {"TIKTOKEN_CACHE_DIR": directory}),
            ):
                tokenizer, identity = tool.local_tokenizer("gpt-4o-2024-08-06")
            self.assertIsNone(tokenizer)
            self.assertEqual(identity["version"], "0.12.0")

    def test_real_tokenizer_rejects_empty_alternate_cache_despite_verified_default(self):
        # Verifying the default while tiktoken reads the alternate cache can trigger a download.
        try:
            import tiktoken.load
        except ImportError:
            self.skipTest("optional tokenizer dependencies are not installed")
        cache_dir = os.environ.get("TIKTOKEN_CACHE_DIR")
        if not cache_dir:
            self.skipTest(
                "set TIKTOKEN_CACHE_DIR to a prefetched vocabulary for this integration test"
            )
        url = "https://openaipublic.blob.core.windows.net/encodings/o200k_base.tiktoken"
        key = hashlib.sha1(url.encode()).hexdigest()
        vocabulary = Path(cache_dir) / key
        if not vocabulary.is_file():
            self.skipTest("prefetched tokenizer vocabulary is unavailable")
        expected = "446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d"
        self.assertEqual(hashlib.sha256(vocabulary.read_bytes()).hexdigest(), expected)
        tool = self.load_tool()
        with tempfile.TemporaryDirectory() as directory:
            default = Path(directory) / "data-gym-cache"
            default.mkdir()
            (default / key).write_bytes(vocabulary.read_bytes())
            alternate = Path(directory) / "alternate"
            alternate.mkdir()
            environment = {
                k: v
                for k, v in os.environ.items()
                if k not in ("TIKTOKEN_CACHE_DIR", "DATA_GYM_CACHE_DIR")
            }
            environment["DATA_GYM_CACHE_DIR"] = str(alternate)
            with (
                mock.patch.dict(os.environ, environment, clear=True),
                mock.patch("tempfile.gettempdir", return_value=directory),
                mock.patch.object(
                    tiktoken.load,
                    "read_file",
                    side_effect=AssertionError("offline tokenizer attempted network access"),
                ),
            ):
                tokenizer, identity = tool.local_tokenizer("gpt-4o-2024-08-06")
            self.assertIsNone(tokenizer)
            result = tool.measure({}, tokenizer, identity)
            self.assertEqual(result["conditions"][0]["kind"], "missing_dependency")

    def test_schema_version_rejects_boolean_and_repetitions_start_at_one(self):
        # Python's bool/int equality must not validate a boolean schema version.
        tool = self.load_tool()
        data = tool.synthetic_results()
        data["schema_version"] = True
        self.assertFalse(tool.build_report(data)["checks"]["schema"]["passed"])
        data = tool.synthetic_results()
        for pair in data["trials"]:
            pair["repetition"] += 1
        self.assertFalse(tool.build_report(data)["checks"]["paired_trials"]["passed"])

    def test_payload_fixture_identity_ignores_invoking_script_and_temporary_paths(self):
        # Machine-specific command paths would change the supposedly fixed payload corpus.
        tool = self.load_tool()
        with mock.patch.object(sys, "argv", ["first.py"]):
            first = tool.payload_corpus()
        with mock.patch.object(sys, "argv", ["another-script.py"]):
            second = tool.payload_corpus()
        self.assertEqual(first, second)

    def test_payload_corpus_and_measurements_survive_relocated_source_copies(self):
        # Source locations and shell quoting must not change equivalent payloads or token counts.
        tool = self.load_tool()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reference = root / "reference"
            tool.snapshot(reference, "candidate")
            execution = tool.prepare_execution_source(
                reference, root / "long source's execution copy"
            )
            corpora = []
            measurements = []
            cases = [
                (cwd, source)
                for cwd in (tool.REPO, ROOT)
                for source in (ROOT, reference, execution)
            ]
            for index, (cwd, source) in enumerate(cases):
                output = root / f"measurement-{index}"
                result = subprocess.run(
                    [
                        sys.executable,
                        str(source / "evals/toon-cli/evaluate.py"),
                        "measure",
                        "--output",
                        str(output),
                    ],
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                corpora.append(json.loads((output / "payloads.json").read_text()))
                measurements.append(json.loads((output / "measurements.json").read_text()))
            for corpus, measurement in zip(corpora[1:], measurements[1:], strict=True):
                self.assertEqual(corpus, corpora[0])
                self.assertEqual(measurement, measurements[0])
            self.assertEqual(
                corpora[0]["examples"]["examples"][0]["path"], "SOURCE/examples/minimal-prd.yaml"
            )

    def test_missing_or_invalid_provenance_is_incomplete_and_preserves_evidence(self):
        # A failed promotion check alone must not label unknown provenance complete.
        tool = self.load_tool()
        for value in (None, "", "reported", [], {}, True, 1):
            with self.subTest(provenance=value):
                data = tool.synthetic_results()
                data["provenance"] = value
                report = tool.build_report(data)
                self.assertEqual(report["completeness"], "incomplete")
                self.assertIsNone(report["provenance"])
                self.assertEqual(report["evidence"], data)
                self.assertIn("malformed_evidence", [item["kind"] for item in report["conditions"]])
                self.assertFalse(report["promotion_eligible"])
        data = tool.synthetic_results()
        del data["provenance"]
        report = tool.build_report(data)
        self.assertEqual(report["completeness"], "incomplete")
        self.assertIsNone(report["provenance"])
        self.assertIn("missing_evidence", [item["kind"] for item in report["conditions"]])
        for value in ("synthetic", "observed"):
            data["provenance"] = value
            report = tool.build_report(data)
            self.assertEqual(report["provenance"], value)
            self.assertEqual(report["completeness"], "complete")
            self.assertEqual(report["conditions"], [])

    def test_malformed_conditions_and_unknown_schema_remain_incomplete(self):
        # Malformed condition objects must not crash Markdown report construction.
        tool = self.load_tool()
        for condition in (None, {}, {"kind": "missing_evidence"}):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                data = tool.synthetic_results()
                data["conditions"] = [condition]
                tool.write_json(root / "results.json", data)
                tool.main(["report", "--input", str(root / "results.json"), "--output", directory])
                report = json.loads((root / "report.json").read_text())
                self.assertEqual(report["completeness"], "incomplete")
                self.assertFalse(report["promotion_eligible"])
        data = tool.synthetic_results()
        data["schema_version"] = 2
        self.assertEqual(tool.build_report(data)["completeness"], "incomplete")

    def test_execution_copy_restores_writable_asset_modes_without_changing_source_bytes(self):
        # Copying read-only snapshot modes into generated bundles prevents replacement and cleanup.
        tool = self.load_tool()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "snapshot"
            source.mkdir()
            asset = source / "asset.txt"
            asset.write_bytes(b"fixture asset")
            asset.chmod(0o444)
            source.chmod(0o555)
            runtime = tool.prepare_execution_source(source, root / "runtime")
            self.assertNotEqual(runtime, source)
            self.assertEqual((runtime / "asset.txt").read_bytes(), b"fixture asset")
            self.assertTrue(runtime.stat().st_mode & 0o200)
            self.assertEqual(source.stat().st_mode & 0o222, 0)

    def test_gate_derives_savings_but_synthetic_cannot_promote(self):
        # Removing provenance enforcement would promote a fabricated experiment.
        self.assertTrue(SPEC.origin and Path(SPEC.origin).exists(), "evaluation tooling is missing")
        module = self.load_tool()
        report = module.build_report(module.synthetic_results())
        self.assertEqual(report["totals"], {"baseline": 4200, "candidate": 3360})
        self.assertTrue(report["checks"]["savings"]["passed"])
        self.assertFalse(report["checks"]["observed"]["passed"])
        self.assertFalse(report["promotion_eligible"])


if __name__ == "__main__":
    unittest.main()
