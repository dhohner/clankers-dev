from __future__ import annotations

import copy
import json
import os
import shlex
import unittest
from unittest import mock

from support import NO_BROWSER_ENV, dump_yaml, run_cli_process

from interview_support import InterviewHarness, InterviewTestCase
from response_support import decode_response
from test_prd_bundle_interview_delivery import ROUND_ONE, ROUND_ONE_SUBMIT


class InterviewResponseTests(InterviewTestCase):
    time_limit_seconds = 5.0

    # Disconnection is a successful result and cannot discard the open round.
    def test_disconnected_round_recovers_in_both_formats(self) -> None:
        environment = mock.patch.dict(os.environ, {"TO_PRD_INTERVIEW_GRACE_SECONDS": "0.05"})
        environment.start()
        self.addCleanup(environment.stop)
        for output_format in ("toon", "yaml"):
            with self.subTest(format=output_format):
                session = self.root / output_format
                session.mkdir()
                harness = InterviewHarness(self, self.root, session)
                source = self.write_round(ROUND_ONE, f"{output_format}.json")
                ask = harness.start_ask_process(source, "--format=" + output_format)
                ask.wait_started()
                disconnected = ask.finish()
                self.assertEqual(disconnected.returncode, 0, disconnected.stderr)
                self.assertEqual(
                    decode_response(disconnected.stdout, output_format)["status"],
                    "browser_disconnected",
                )
                stored = harness.rounds_dir / "ROUND-01.json"
                before = stored.read_bytes()
                competing = copy.deepcopy(ROUND_ONE)
                competing["id"] = "ROUND-02"
                competing_source = self.write_round(competing, f"competing-{output_format}.json")
                rejected = run_cli_process(
                    "interview",
                    "ask",
                    str(session),
                    str(competing_source),
                    "--format=" + output_format,
                )
                self.assertEqual(rejected.returncode, 1, rejected.stderr)
                self.assertEqual(
                    decode_response(rejected.stdout, output_format)["code"], "round_open"
                )
                self.assertEqual(stored.read_bytes(), before)
                self.assertEqual(harness.state()["state"], "active")
                self.assertFalse((session / "interview" / "answers" / "ROUND-01.json").exists())
                opened = run_cli_process(
                    "interview", "open", str(session), "--format=" + output_format
                )
                self.assertEqual(opened.returncode, 0, opened.stderr)
                self.assertEqual(harness.submit(ROUND_ONE_SUBMIT)[0], 200)
                recovered = run_cli_process(
                    "interview", "ask", str(session), str(source), "--format=" + output_format
                )
                self.assertEqual(recovered.returncode, 0, recovered.stderr)
                self.assertEqual(
                    decode_response(recovered.stdout, output_format)["status"], "answered"
                )
                self.assertEqual(stored.read_bytes(), before)
                harness.end()

    # Round read failures must use the requested encoding and never start a session.
    def test_unreadable_rounds_emit_repair_guidance_in_both_formats(self) -> None:
        source = self.root / "invalid-encoding.yaml"
        source.write_bytes(b"\xff")
        for output_format in ("toon", "yaml"):
            for path, code in (
                (source, "round_unreadable"),
                (self.root, "round_unreadable"),
                (self.root / "missing.yaml", "round_not_found"),
            ):
                with self.subTest(format=output_format, path=path):
                    result = run_cli_process(
                        "interview",
                        "ask",
                        str(self.session),
                        str(path),
                        "--format=" + output_format,
                    )
                    self.assertEqual(result.returncode, 1, result.stderr)
                    payload = decode_response(result.stdout, output_format)
                    self.assertEqual(payload["code"], code)
                    self.assertTrue(payload["errors"][0]["fix"])
                    self.assertEqual(list(self.session.iterdir()), [])
                    self.assertEqual(result.stderr, "")

    # Unhandled session I/O would replace the selected response with a traceback.
    @unittest.skipIf(os.geteuid() == 0, "root bypasses directory and file permission checks")
    def test_session_permission_failures_preserve_data_and_emit_both_formats(self) -> None:
        source = self.write_round(ROUND_ONE, "round with spaces.json")
        browser_log = self.root / "browser.log"
        registry = self.root / "registry.json"
        environment = {
            "TO_PRD_INTERVIEW_BROWSER_LOG": str(browser_log),
            "TO_PRD_INTERVIEW_REGISTRY": str(registry),
        }
        for stage in ("directory_creation", "directory_conflict", "lock_access"):
            session = self.root / f"{stage} session"
            session.mkdir()
            (session / "prd.yaml").write_text("status: Draft\n", encoding="utf-8")
            protected = session
            denied_mode = 0o500
            commands = ("ask",)
            if stage == "directory_conflict":
                (session / "interview").write_text("Keep this file.\n", encoding="utf-8")
                denied_mode = 0o700
            if stage == "lock_access":
                storage = session / "interview"
                storage.mkdir()
                (storage / "state.json").write_text('{"state": "ended"}\n', encoding="utf-8")
                (storage / "rounds").mkdir()
                (storage / "rounds" / "ROUND-01.json").write_text(
                    json.dumps(ROUND_ONE), encoding="utf-8"
                )
                (storage / "answers").mkdir()
                (storage / "answers" / "ROUND-01.json").write_text(
                    json.dumps(ROUND_ONE_SUBMIT), encoding="utf-8"
                )
                protected = storage / "lock"
                protected.touch(mode=0o600)
                denied_mode = 0o400
                commands = ("ask", "open", "status", "end")
            original_mode = protected.stat().st_mode & 0o777
            before = {
                path.relative_to(session): path.read_bytes()
                for path in session.rglob("*")
                if path.is_file()
            }
            for output_format in ("toon", "yaml"):
                for command in commands:
                    with self.subTest(stage=stage, format=output_format, command=command):
                        protected.chmod(denied_mode)
                        try:
                            with mock.patch.dict(NO_BROWSER_ENV, environment):
                                result = run_cli_process(
                                    "interview",
                                    command,
                                    str(session),
                                    *((str(source),) if command == "ask" else ()),
                                    "--format=" + output_format,
                                )
                        finally:
                            protected.chmod(original_mode)
                        self.assertEqual(result.returncode, 1, result.stderr)
                        self.assertTrue(result.stdout, result.stderr)
                        payload = decode_response(result.stdout, output_format)
                        self.assertEqual(payload["status"], "error")
                        self.assertEqual(payload["code"], "session_io_error")
                        self.assertEqual(payload["session"], str(session))
                        retry = ["interview", command, str(session)]
                        if command == "ask":
                            retry.append(str(source))
                        self.assertEqual(shlex.split(payload["next"][0])[-len(retry) :], retry)
                        self.assertTrue(payload["errors"])
                        for error in payload["errors"]:
                            self.assertEqual(error["path"], "session_dir")
                            self.assertTrue(error["message"] and error["fix"])
                        self.assertEqual(result.stderr, "")
                        self.assertEqual(
                            {
                                path.relative_to(session): path.read_bytes()
                                for path in session.rglob("*")
                                if path.is_file()
                            },
                            before,
                        )
                        self.assertFalse(browser_log.exists())
                        self.assertFalse(registry.exists())

    # Bypassing the common emitter loses YAML selection or puts progress on stdout.
    def test_every_interview_command_uses_both_formats_and_preserves_replay(self) -> None:
        for output_format in ("toon", "yaml"):
            with self.subTest(format=output_format):
                session = self.root / output_format
                session.mkdir()
                harness = InterviewHarness(self, self.root, session)
                round_file = self.root / f"round.{output_format}"
                round_file.write_text(
                    json.dumps(ROUND_ONE) if output_format == "toon" else dump_yaml(ROUND_ONE),
                    encoding="utf-8",
                )
                selector = ("--format", output_format)
                initial = run_cli_process(*selector, "interview", "status", str(session))
                self.assertEqual(
                    decode_response(initial.stdout, output_format)["state"], "no_session"
                )
                ask = harness.start_ask_process(round_file, *selector)
                self.assertIn("waiting for ROUND-01", ask.wait_started())
                status = run_cli_process("interview", "status", str(session), *selector)
                self.assertEqual(
                    decode_response(status.stdout, output_format)["state"], "round_open"
                )
                opened = run_cli_process("interview", "open", str(session), *selector)
                self.assertEqual(opened.returncode, 0, opened.stderr)
                self.assertEqual(decode_response(opened.stdout, output_format)["status"], "opened")
                self.assertEqual(harness.submit(ROUND_ONE_SUBMIT)[0], 200)
                result = ask.finish()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("waiting for ROUND-01", result.stderr)
                self.assertNotIn("waiting for", result.stdout)
                payload = decode_response(result.stdout, output_format)
                self.assertEqual(payload["status"], "answered")
                self.assertTrue(payload["answers"] and payload["instructions"])
                answers = session / "interview" / "answers" / "ROUND-01.json"
                before = answers.read_bytes()
                replay = run_cli_process(
                    *selector, "interview", "ask", str(session), str(round_file)
                )
                self.assertEqual(replay.returncode, 0, replay.stderr)
                self.assertEqual(decode_response(replay.stdout, output_format), payload)
                self.assertEqual(answers.read_bytes(), before)
                self.assertEqual(len(list(answers.parent.iterdir())), 1)
                self.assertTrue((session / "interview" / "delivered" / "ROUND-01.json").exists())
                self.assertEqual(harness.submit(ROUND_ONE_SUBMIT)[0], 409)
                status = run_cli_process("interview", "status", str(session), *selector)
                self.assertEqual(
                    decode_response(status.stdout, output_format)["state"], "round_answered"
                )
                changed = copy.deepcopy(ROUND_ONE)
                changed["questions"][0]["question"] = "Changed content?"
                round_file.write_text(json.dumps(changed), encoding="utf-8")
                rejected = run_cli_process(
                    "interview", "ask", str(session), str(round_file), *selector
                )
                self.assertEqual(rejected.returncode, 1, rejected.stderr)
                self.assertEqual(
                    decode_response(rejected.stdout, output_format)["code"], "round_changed"
                )
                self.assertEqual(answers.read_bytes(), before)
                for _ in range(2):
                    ended = run_cli_process("interview", "end", str(session), *selector)
                    self.assertEqual(ended.returncode, 0, ended.stderr)
                    self.assertEqual(
                        decode_response(ended.stdout, output_format)["status"], "ended"
                    )
                status = run_cli_process("interview", "status", str(session), *selector)
                payload = decode_response(status.stdout, output_format)
                self.assertEqual(payload["state"], "ended")
                self.assertFalse(payload["server_running"])
                self.assertEqual(answers.read_bytes(), before)
