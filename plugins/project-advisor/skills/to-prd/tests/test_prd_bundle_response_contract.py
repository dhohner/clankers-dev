from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from support import (
    EXAMPLE,
    NO_BROWSER_ENV,
    SKILL_DIR,
    dump_yaml,
    load_example_manifest,
    load_yaml,
    run_cli,
    run_cli_process,
)

from response_support import decode_response
from toon_oracle import decode


class ResponseContractTests(unittest.TestCase):
    # Removing TOON dispatch breaks independent decoding across operational commands.
    def test_operational_commands_emit_selected_format_in_subprocesses(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for output_format in ("toon", "yaml"):
                output = root / output_format
                commands = [
                    ("status", "--output-root", str(output)),
                    ("schema",),
                    ("examples",),
                    ("validate", str(EXAMPLE)),
                    ("generate", str(EXAMPLE), "--output-root", str(output)),
                    ("inspect", str(output / "PRD-example-review-bundle")),
                ]
                for args in commands:
                    with self.subTest(format=output_format, command=args[0]):
                        result = run_cli_process(*args, "--format", output_format)
                        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                        payload = decode_response(result.stdout, output_format)
                        self.assertEqual(payload["status"], "ok")
                        self.assertEqual(result.stderr, "")

    # Conflicts must remain visible even when followed by equal selectors.
    def test_usage_errors_follow_selector_precedence(self) -> None:
        cases = [
            (("status", "--format"), "toon"),
            (("status", "--format="), "toon"),
            (("status", "--format", "text"), "toon"),
            (("status", "--format=json"), "toon"),
            (("--format", "yaml", "status", "--format", "toon", "--format", "toon"), "toon"),
            (("--format", "toon", "status", "--format", "yaml", "--format", "yaml"), "toon"),
            (("--format", "json", "status", "--format", "yaml"), "toon"),
            (("--format", "yaml", "status", "--format"), "toon"),
            (("--format", "yaml", "bogus"), "yaml"),
            (("bogus", "--format=toon"), "toon"),
            (("validate", "--format=yaml"), "yaml"),
            (("generate", "--format=toon"), "toon"),
            (("status", "--bogus", "--format=yaml"), "yaml"),
            (("status", "--form=yaml"), "yaml"),
            (("interview", "ask", "--format=yaml"), "yaml"),
            (("interview", "bogus"), "toon"),
            (("status", "--bogus"), "yaml"),
        ]
        for args, output_format in cases:
            with self.subTest(args=args):
                result = run_cli_process(*args)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                payload = decode_response(result.stdout, output_format)
                self.assertEqual(payload["status"], "error")
                self.assertEqual(payload["code"], "usage_error")
                self.assertTrue(payload["next"])
                for error in payload["errors"]:
                    self.assertTrue(error["path"] and error["message"] and error["fix"])
                self.assertEqual(result.stderr, "")

    # Returning usage exits or omitting repair guidance hides operation failures.
    def test_operation_failures_have_exit_one_and_repair_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            encoding = root / "encoding.yaml"
            encoding.write_bytes(b"\xff")
            malformed = root / "malformed.yaml"
            malformed.write_text("id: [\n", encoding="utf-8")
            invalid = root / "invalid.yaml"
            invalid.write_text("schema_version: 7\n", encoding="utf-8")
            duplicate = root / "duplicate.yaml"
            manifest = load_example_manifest()
            manifest["blocks"]["requirements"][1]["id"] = "REQ-01"
            duplicate.write_text(dump_yaml(manifest), encoding="utf-8")
            bundle = root / "PRD-invalid"
            bundle.mkdir()
            unreadable_bundle = root / "PRD-encoding"
            unreadable_bundle.mkdir()
            (unreadable_bundle / "prd.yaml").write_bytes(b"\xff")
            target_file = root / "output-file"
            target_file.touch()
            cases = [
                (("validate", str(root / "missing.yaml")), "file_not_found"),
                (("validate", str(root)), "manifest_unreadable"),
                (("validate", str(encoding)), "manifest_unreadable"),
                (("validate", str(malformed)), "yaml_invalid"),
                (("validate", str(invalid)), "manifest_invalid"),
                (("validate", str(duplicate)), "manifest_invalid"),
                (("inspect", str(root / "missing")), "bundle_missing"),
                (("inspect", str(bundle)), "bundle_invalid"),
                (("inspect", str(unreadable_bundle)), "bundle_unreadable"),
                (("generate", str(EXAMPLE), "--output-root", str(target_file)), "io_error"),
                (("schema", "bogus"), "block_unknown"),
                (("examples", "bogus"), "example_unknown"),
                (("template", "--blocks", "bogus"), "block_unknown"),
            ]
            for output_format in ("toon", "yaml"):
                for args, code in cases:
                    with self.subTest(format=output_format, args=args):
                        result = run_cli_process(*args, "--format", output_format)
                        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                        payload = decode_response(result.stdout, output_format)
                        self.assertEqual(payload["status"], "error")
                        self.assertEqual(payload["code"], code)
                        self.assertTrue(payload["next"])
                        for error in payload["errors"]:
                            self.assertTrue(error["path"] and error["message"] and error["fix"])
                        self.assertEqual(result.stderr, "")

    # Encoding a successful template as a response would corrupt redirected authoring input.
    def test_redirected_template_remains_a_yaml_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest = Path(temporary) / "prd.yaml"
            for selector in ((), ("--format", "yaml"), ("--format=toon",)):
                with self.subTest(selector=selector):
                    result = run_cli_process(
                        "template", "--blocks", "requirements", "testing_strategy", *selector
                    )
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    document = load_yaml(result.stdout)
                    self.assertEqual(document["schema_version"], 2)
                    self.assertEqual(
                        document["blocks"]["requirements"][0]["validation"], ["TEST-01"]
                    )
                    manifest.write_text(result.stdout, encoding="utf-8")
                    validation = run_cli_process("validate", str(manifest), "--format=toon")
                    self.assertEqual(
                        validation.returncode, 0, validation.stdout + validation.stderr
                    )
                    self.assertEqual(decode(validation.stdout)["status"], "ok")

    # Omitting migration options in help leaves consumers on the removed text contract.
    def test_help_explains_formats_defaults_and_failure_exits(self) -> None:
        commands = [
            (),
            *(
                (command,)
                for command in (
                    "status",
                    "schema",
                    "examples",
                    "validate",
                    "generate",
                    "inspect",
                    "template",
                )
            ),
            ("interview",),
            *(("interview", command) for command in ("ask", "open", "status", "end")),
        ]
        for command in commands:
            with self.subTest(command=command):
                result = run_cli_process(*command, "--help")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, "")
                text = " ".join(result.stdout.split())
                for phrase in (
                    "--format",
                    "toon",
                    "yaml",
                    "0 success",
                    "1 operation failure",
                    "2 usage error",
                ):
                    self.assertIn(phrase, text)
                self.assertIn("default", text)

    # An incompatible schema invocation is usage and must carry recovery commands.
    def test_authoring_schema_rejects_block_arguments_as_usage(self) -> None:
        result = run_cli_process("schema", "--authoring", "goals", "--format=toon")
        self.assertEqual(result.returncode, 2, result.stdout)
        payload = decode(result.stdout)
        self.assertEqual(payload["code"], "schema_authoring_with_blocks")
        self.assertTrue(payload["errors"][0]["fix"])
        self.assertTrue(payload["next"])

    # Selector extraction must support placement, equals syntax, and equal repeats.
    def test_valid_selectors_and_yaml_defaults(self) -> None:
        commands = [(), ("status",), ("schema",), ("examples",), ("validate", str(EXAMPLE))]
        for args in commands:
            result = run_cli_process(*args)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(load_yaml(result.stdout)["status"], "ok")
        for output_format in ("toon", "yaml"):
            selectors = [
                ("--format", output_format, "schema", "requirements"),
                ("schema", "--format=" + output_format, "requirements"),
                ("--format=" + output_format, "schema", "requirements", "--format", output_format),
            ]
            for args in selectors:
                with self.subTest(args=args):
                    result = run_cli_process(*args)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    payload = decode_response(result.stdout, output_format)
                    self.assertEqual(payload["block"], "requirements")
                    self.assertEqual(payload["example"]["requirements"][0]["id"], "REQ-01")

    # Dispatch before parsing would block on the FIFO or create interview/publication state.
    def test_invalid_usage_has_no_source_browser_server_or_publication_effects(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.yaml"
            os.mkfifo(source)
            session = root / "session"
            session.mkdir()
            output = root / "output"
            log = root / "browser.log"
            registry = root / "registry.json"
            env = {
                **NO_BROWSER_ENV,
                "TO_PRD_INTERVIEW_BROWSER_LOG": str(log),
                "TO_PRD_INTERVIEW_REGISTRY": str(registry),
            }
            commands = [
                ("validate", str(source), "--bogus"),
                ("generate", str(source), "--output-root", str(output), "--format=json"),
                ("interview", "ask", str(session), str(source), "--bogus"),
                ("interview", "open", str(session), "--bogus"),
                (
                    "--format=yaml",
                    "interview",
                    "ask",
                    str(session),
                    str(source),
                    "--format=toon",
                    "--format=toon",
                ),
            ]
            for args in commands:
                with self.subTest(args=args):
                    result = subprocess.run(
                        [sys.executable, "-S", "-m", "scripts", *args],
                        cwd=SKILL_DIR,
                        check=False,
                        env=env,
                        stdin=subprocess.PIPE,
                        capture_output=True,
                        text=True,
                        timeout=2,
                    )
                    self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                    self.assertFalse(output.exists())
                    self.assertFalse(log.exists())
                    self.assertFalse(registry.exists())
                    self.assertEqual(list(session.iterdir()), [])

    # A failed staging write or publication rename must retain the previous valid bundle.
    def test_generation_failures_restore_previous_bundle_and_exit_one(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            generated = run_cli("generate", str(EXAMPLE), "--output-root", str(root))
            self.assertEqual(generated.returncode, 0, generated.stderr)
            bundle = root / "PRD-example-review-bundle"
            before = {
                str(path.relative_to(bundle)): path.read_bytes()
                for path in bundle.rglob("*")
                if path.is_file()
            }
            original_write = Path.write_text
            original_rename = Path.rename

            def fail_staging(path, *args, **kwargs):
                if path.name == "index.html":
                    raise OSError("injected staging write failure")
                return original_write(path, *args, **kwargs)

            def fail_replacement(path, target):
                if path.name.startswith(".PRD-") and Path(target) == bundle.resolve():
                    raise RuntimeError("injected replacement failure")
                return original_rename(path, target)

            for boundary, failure, code in (
                ("write_text", fail_staging, "io_error"),
                ("rename", fail_replacement, "generator_failed"),
            ):
                with self.subTest(boundary=boundary), mock.patch.object(Path, boundary, failure):
                    result = run_cli(
                        "generate",
                        str(EXAMPLE),
                        "--output-root",
                        str(root),
                        "--force",
                        "--format=toon",
                    )
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    payload = decode(result.stdout)
                    self.assertEqual(payload["code"], code)
                    self.assertTrue(payload["errors"][0]["fix"])
                    self.assertEqual(
                        {
                            str(path.relative_to(bundle)): path.read_bytes()
                            for path in bundle.rglob("*")
                            if path.is_file()
                        },
                        before,
                    )
                    self.assertEqual(list(root.iterdir()), [bundle])
                    inspected = run_cli("inspect", str(bundle), "--format=toon")
                    self.assertEqual(inspected.returncode, 0, inspected.stdout + inspected.stderr)
            refused = run_cli_process(
                "generate", str(EXAMPLE), "--output-root", str(root), "--format=toon"
            )
            self.assertEqual(refused.returncode, 1, refused.stdout)
            payload = decode(refused.stdout)
            self.assertEqual(payload["code"], "bundle_exists")
            self.assertIn("inspect", payload["next"][0])
            replaced = run_cli_process(
                "generate", str(EXAMPLE), "--output-root", str(root), "--force", "--format=toon"
            )
            self.assertEqual(replaced.returncode, 0, replaced.stdout + replaced.stderr)

    # Response encoding must never change accepted YAML documents or supported JSON inputs.
    def test_versions_and_input_documents_remain_portable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for version in (1, 2):
                manifest = load_example_manifest()
                manifest["schema_version"] = version
                manifest["status"] = "Accepted"
                if version == 1:
                    del manifest["blocks"]["design_tree"]
                for extension, content in (
                    ("yaml", dump_yaml(manifest)),
                    ("json", json.dumps(manifest)),
                ):
                    source = root / f"v{version}.{extension}"
                    source.write_text(content, encoding="utf-8")
                    output = root / f"v{version}-{extension}"
                    bundle = output / "PRD-example-review-bundle"
                    for args in (
                        ("validate", str(source)),
                        ("generate", str(source), "--output-root", str(output)),
                        ("inspect", str(bundle), "--full"),
                    ):
                        result = subprocess.run(
                            [sys.executable, "-S", "-m", "scripts", *args, "--format=toon"],
                            cwd=SKILL_DIR,
                            check=False,
                            env=NO_BROWSER_ENV,
                            capture_output=True,
                            text=True,
                            timeout=2,
                        )
                        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                        self.assertEqual(decode(result.stdout)["manifest_version"], version)
                        self.assertEqual(result.stderr, "")
                    published = load_yaml((bundle / "prd.yaml").read_text(encoding="utf-8"))
                    self.assertEqual(published["status"], "Accepted")
                    self.assertEqual(published["schema_version"], version)
                    self.assertEqual(
                        published["blocks"]["requirements"][0]["title"],
                        "Portable multi-file bundle",
                    )
                    self.assertEqual(published["blocks"]["requirements"][0]["id"], "req-01")
                    self.assertFalse((bundle / "interview").exists())

    # Moving a selector behind -- would turn it into unwanted positional arguments.
    def test_selector_keeps_positional_separator_intact(self) -> None:
        result = run_cli_process("--format=toon", "validate", "--", "--missing.yaml")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(decode(result.stdout)["code"], "file_not_found")


if __name__ == "__main__":
    unittest.main()
