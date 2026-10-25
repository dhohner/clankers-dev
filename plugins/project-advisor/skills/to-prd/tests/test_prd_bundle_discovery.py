"""Counts and complete retrieval through the operational CLI."""

from __future__ import annotations

import argparse
import contextlib
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from support import (
    BUNDLE,
    EXAMPLE,
    NO_BROWSER_ENV,
    SKILL_DIR,
    dump_yaml,
    load_example_manifest,
    load_yaml,
    run_cli,
)

from interview_support import ServerFixture
from response_support import decode_response
from scripts.cli.bundle_commands import command_status
from scripts.cli.catalog_examples import command_examples
from scripts.cli.catalog_schema import command_schema
from scripts.interview.registry import register
from scripts.spec import ENTITY_OPTIONAL_FIELDS_BY_BLOCK
from test_prd_bundle_interview_delivery import ROUND_ONE


class DiscoveryTests(unittest.TestCase):
    def assert_collection(self, payload: dict[str, Any], name: str, total: int, shown: int) -> None:
        self.assertEqual(len(payload[name]), shown)
        metadata = payload["collection_metadata"][name]
        self.assertEqual(int(metadata["total_count"]), total)
        self.assertEqual(int(metadata["shown_count"]), shown)
        self.assertEqual(str(metadata["truncated"]).lower(), str(shown < total).lower())

    def follow(self, command: str, output_format: str, cwd: Path = SKILL_DIR) -> dict[str, Any]:
        tokens = shlex.split(command)
        self.assertIn("--full", tokens)
        self.assertNotIn("--force", tokens)
        options = tokens[: tokens.index("--")] if "--" in tokens else tokens
        self.assertEqual(options[-2:], ["--format", output_format])
        result = subprocess.run(
            tokens, cwd=cwd, env=NO_BROWSER_ENV, capture_output=True, text=True, check=False
        )
        self.assertIn(result.returncode, (0, 1), result.stdout + result.stderr)
        return decode_response(result.stdout, output_format)

    def installation(self, root: Path) -> Path:
        installed = root / "installation ' $;"
        shutil.copytree(
            SKILL_DIR / "scripts",
            installed / "scripts",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        (installed / "examples").mkdir()
        return installed

    def installed_response(
        self, installed: Path, *args: str, encoding: str | None = "toon"
    ) -> dict[str, Any]:
        result = subprocess.run(
            [
                sys.executable,
                str(installed / "scripts" / "__main__.py"),
                *(["--format", encoding] if encoding else []),
                *args,
            ],
            cwd=installed,
            env=NO_BROWSER_ENV,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return decode_response(result.stdout, encoding or "yaml")

    # Losing counts or the installed catalog target makes omitted examples inaccessible.
    def test_examples_counts_empty_catalog_and_complete_retrieval(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            installed = self.installation(Path(temporary))
            for count in (0, 19, 20, 21):
                for index in range(len(list((installed / "examples").iterdir())), count):
                    (installed / "examples" / f"sample-{index:02}.yaml").write_text(
                        dump_yaml({"title": f"Example {index}", "initiative_type": "api-heavy"}),
                        encoding="utf-8",
                    )
                for encoding in ("yaml", "toon"):
                    with self.subTest(count=count, encoding=encoding):
                        payload = self.installed_response(installed, "examples", encoding=encoding)
                        self.assert_collection(payload, "examples", count, min(count, 20))
                        self.assertTrue(payload["next"])
                        self.assertTrue(all(len(row) <= 4 for row in payload["examples"]))
                        full = (
                            self.follow(payload["next"][0], encoding, installed)
                            if count > 20
                            else self.installed_response(
                                installed, "examples", "--full", encoding=encoding
                            )
                        )
                        self.assert_collection(full, "examples", count, count)
                        self.assertEqual(
                            {row["name"] for row in full["examples"]},
                            {f"sample-{index:02}" for index in range(count)},
                        )

    # Byte counts, strip(), or slicing arguments corrupt Unicode detail and retrieval targets.
    def test_example_text_boundaries_preserve_characters_and_named_retrieval(self) -> None:
        name = "named ' $;" + "n" * 201
        with tempfile.TemporaryDirectory() as temporary:
            installed = self.installation(Path(temporary))
            for size in (0, 199, 200, 201):
                for seed in ("x", "é🙂漢", '\n,|:"\\'):
                    text = (seed * 201)[:size]
                    (installed / "examples" / f"{name}.yaml").write_text(
                        dump_yaml({"title": text, "initiative_type": "api-heavy"}), encoding="utf-8"
                    )
                    for encoding in ("yaml", "toon"):
                        with self.subTest(size=size, seed=seed, encoding=encoding):
                            payload = self.installed_response(
                                installed, "examples", name, encoding=encoding
                            )
                            self.assertEqual(payload["examples"][0]["title"], text[:200])
                            metadata = payload["text_metadata"]["examples[0].title"]
                            self.assertEqual(int(metadata["total_characters"]), size)
                            self.assertEqual(int(metadata["shown_characters"]), min(size, 200))
                            self.assertEqual(
                                str(metadata["truncated"]).lower(), str(size > 200).lower()
                            )
                            full = self.follow(metadata["command"], encoding, installed)
                            self.assertEqual(full["examples"][0]["title"], text)
                            self.assertEqual(shlex.split(metadata["command"])[-2:], ["--", name])
                            self.assertEqual(payload["examples"][0]["name"], name)
                            self.assertEqual(
                                payload["examples"][0]["path"], f"examples/{name}.yaml"
                            )
                            self.assert_collection(full, "examples", 1, 1)
                            full_text = full["text_metadata"]["examples[0].title"]
                            self.assertEqual(int(full_text["shown_characters"]), size)
                            self.assertEqual(str(full_text["truncated"]).lower(), "false")

    # Without an option terminator, valid names become flags or select the whole catalog.
    def test_full_retrieval_preserves_example_names_that_begin_with_dash(self) -> None:
        names = ("-custom", "--full", "--format=bad", "--", "-custom ' $; &")
        title = "Complete 🙂漢,|:\ntext. " * 20
        with tempfile.TemporaryDirectory() as temporary:
            installed = self.installation(Path(temporary))
            for name in names:
                (installed / "examples" / f"{name}.yaml").write_text(
                    dump_yaml({"title": title}), encoding="utf-8"
                )
            for encoding in (None, "yaml", "toon"):
                for name in names:
                    with self.subTest(encoding=encoding, name=name):
                        payload = self.installed_response(
                            installed, "examples", "--", name, encoding=encoding
                        )
                        self.assertEqual(payload["examples"][0]["name"], name)
                        metadata = payload["text_metadata"]["examples[0].title"]
                        self.assertEqual(payload["next"][0], metadata["command"])
                        tokens = shlex.split(metadata["command"])
                        result = subprocess.run(
                            tokens,
                            cwd=installed,
                            env=NO_BROWSER_ENV,
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                        full = decode_response(result.stdout, encoding or "yaml")
                        self.assertEqual(
                            full["examples"],
                            [
                                {
                                    "name": name,
                                    "path": f"examples/{name}.yaml",
                                    "title": title,
                                }
                            ],
                        )
                        self.assert_collection(full, "examples", 1, 1)
                        self.assertEqual(
                            tokens[2:],
                            [
                                "examples",
                                "--full",
                                *(["--format", encoding] if encoding else []),
                                "--",
                                name,
                            ],
                        )

    # Projected fields and omitted catalog entries must be recoverable in both schema modes.
    def test_schema_discovery_projects_four_fields_and_restores_catalog(self) -> None:
        names = list(BUNDLE.BLOCK_SPECS)
        for encoding in ("yaml", "toon"):
            for options in ((), ("--authoring",)):
                with self.subTest(encoding=encoding, options=options):
                    payload = decode_response(
                        run_cli("schema", *options, "--format", encoding).stdout, encoding
                    )
                    self.assert_collection(payload, "blocks", len(names), 20)
                    if not options:
                        self.assertTrue(all(len(row) <= 4 for row in payload["blocks"]))
                    full = self.follow(payload["next"][0], encoding)
                    self.assert_collection(full, "blocks", len(names), len(names))
                    if options:
                        self.assertEqual(full["blocks"], sorted(names))
                    else:
                        self.assertEqual([row["name"] for row in full["blocks"]], names)
                        for row in full["blocks"]:
                            spec = BUNDLE.BLOCK_SPECS[row["name"]]
                            self.assertEqual(row["fields"], list(spec.fields))
                            self.assertEqual(row["description"], spec.description)

    # Error totals and aggregates must come from source records, including full retries.
    def test_validation_counts_source_errors_before_slicing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source ' $;.yaml"
            for count in (0, 19, 20, 21):
                manifest = load_example_manifest()
                manifest["blocks"]["requirements"][0]["validation"].extend(
                    f"TEST-missing-{index}" for index in range(count)
                )
                source.write_text(dump_yaml(manifest), encoding="utf-8")
                for encoding in ("yaml", "toon"):
                    with self.subTest(count=count, encoding=encoding):
                        result = run_cli("validate", str(source), "--format", encoding)
                        payload = decode_response(result.stdout, encoding)
                        if not count:
                            self.assertEqual(result.returncode, 0, result.stdout)
                            self.assert_collection(payload, "warnings", 0, 0)
                            self.assert_collection(
                                payload,
                                "selected_blocks",
                                len(manifest["blocks"]),
                                len(manifest["blocks"]),
                            )
                            for block, field in (
                                ("requirements", "requirements"),
                                ("testing_strategy", "tests"),
                                ("design_tree", "blocks"),
                            ):
                                expected = (
                                    len(manifest["blocks"])
                                    if field == "blocks"
                                    else len(manifest["blocks"][block])
                                )
                                self.assertEqual(int(payload["summary"][field]), expected)
                            continue
                        self.assertEqual(result.returncode, 1)
                        self.assertEqual(payload["code"], "manifest_invalid")
                        self.assertEqual(int(payload["total_errors"]), count)
                        self.assert_collection(payload, "errors", count, min(count, 20))
                        full = (
                            self.follow(payload["next"][0], encoding)
                            if count > 20
                            else decode_response(
                                run_cli(
                                    "validate", str(source), "--full", "--format", encoding
                                ).stdout,
                                encoding,
                            )
                        )
                        self.assert_collection(full, "errors", count, count)
                        for index, error in enumerate(full["errors"]):
                            self.assertIn(f"TEST-missing-{index}", error["message"])

    # A full inspection must restore IDs, assets, and the complete normalized source.
    def test_inspect_counts_ids_and_assets_and_full_returns_normalized_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for count in (0, 19, 20, 21):
                manifest = load_example_manifest()
                manifest["schema_version"] = 1
                manifest["blocks"] = {"non_goals": ["No omitted content."]}
                if count:
                    manifest["blocks"]["decisions"] = [
                        {
                            "id": f"DEC-{index:02}",
                            "label": f"DEC-{index:02}",
                            "decision": f"Decision {index}: " + "Complete 🙂漢,|:\ntext. " * 30,
                            "rationale": "A measurable outcome.",
                        }
                        for index in range(count)
                    ]
                source = root / f"source-{count}.yaml"
                source.write_text(dump_yaml(manifest), encoding="utf-8")
                output = root / f"output-{count} ' $;"
                generated = run_cli("generate", str(source), "--output-root", str(output))
                self.assertEqual(generated.returncode, 0, generated.stdout)
                bundle = output / "PRD-example-review-bundle"
                asset_count = sum(path.is_file() for path in (bundle / "assets").rglob("*"))
                for index in range(max(0, count - asset_count)):
                    (bundle / "assets" / f"extra-{index}.txt").touch()
                assets = sorted(
                    str(path.relative_to(bundle))
                    for path in (bundle / "assets").rglob("*")
                    if path.is_file()
                )
                for encoding in ("yaml", "toon"):
                    with self.subTest(count=count, encoding=encoding):
                        result = run_cli("inspect", str(bundle), "--format", encoding)
                        self.assertEqual(result.returncode, 0, result.stdout)
                        payload = decode_response(result.stdout, encoding)
                        self.assert_collection(payload, "ids", count, min(count, 20))
                        self.assert_collection(payload, "assets", len(assets), min(len(assets), 20))
                        self.assert_collection(
                            payload, "sections", len(manifest["blocks"]), len(manifest["blocks"])
                        )
                        full = self.follow(payload["next"][0], encoding)
                        self.assert_collection(full, "ids", count, count)
                        self.assert_collection(full, "assets", len(assets), len(assets))
                        self.assertEqual(full["assets"], assets)
                        self.assertEqual(full["ids"], [f"dec-{index:02}" for index in range(count)])
                        normalized = full["normalized_manifest"]
                        self.assertEqual(normalized["blocks"]["non_goals"], ["No omitted content."])
                        self.assertEqual(len(normalized["blocks"].get("decisions", [])), count)
                        for item, original in zip(
                            normalized["blocks"].get("decisions", []),
                            manifest["blocks"].get("decisions", []),
                            strict=True,
                        ):
                            self.assertEqual(item["decision"], original["decision"].strip())
                            self.assertEqual(item["rationale"], "A measurable outcome.")
                            self.assertEqual(item["label"], original["label"])
                        self.assertEqual(len(full["html_ids"]), int(full["anchors"]["count"]))
                        self.assertTrue(full["fragment_links"])

    # Inspection must retain its failure state while disclosing every omitted diagnostic.
    def test_invalid_inspection_counts_and_retrieves_all_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "output ' $;"
            generated = run_cli("generate", str(EXAMPLE), "--output-root", str(output))
            self.assertEqual(generated.returncode, 0, generated.stdout)
            bundle = output / "PRD-example-review-bundle"
            index = bundle / "index.html"
            original = index.read_text(encoding="utf-8")
            for count in (19, 20, 21):
                index.write_text(
                    original
                    + "".join(f'<img src="./missing-{number};🙂|.png">' for number in range(count)),
                    encoding="utf-8",
                )
                for encoding in ("yaml", "toon"):
                    with self.subTest(count=count, encoding=encoding):
                        result = run_cli("inspect", str(bundle), "--format", encoding)
                        self.assertEqual(result.returncode, 1)
                        payload = decode_response(result.stdout, encoding)
                        self.assertEqual(payload["code"], "bundle_invalid")
                        self.assertEqual(int(payload["total_errors"]), count)
                        self.assert_collection(payload, "errors", count, min(count, 20))
                        full = (
                            self.follow(payload["next"][0], encoding)
                            if count > 20
                            else decode_response(
                                run_cli(
                                    "inspect", str(bundle), "--full", "--format", encoding
                                ).stdout,
                                encoding,
                            )
                        )
                        self.assert_collection(full, "errors", count, count)
                        self.assertEqual(full["status"], "error")
                        for number in range(count):
                            self.assertTrue(
                                any(
                                    f"missing-{number};🙂|.png" in item["message"]
                                    for item in full["errors"]
                                )
                            )

    # Applying the discovery cap to explicit selections would remove authoring contracts.
    def test_every_selected_schema_retains_fields_shapes_prefixes_and_examples(self) -> None:
        names = list(BUNDLE.BLOCK_SPECS)
        for encoding in ("yaml", "toon"):
            result = run_cli("schema", *names, "--format", encoding)
            self.assertEqual(result.returncode, 0, result.stdout)
            schemas = decode_response(result.stdout, encoding)["schemas"]
            self.assertEqual([item["block"] for item in schemas], names)
            for item in schemas:
                name = item["block"]
                spec = BUNDLE.BLOCK_SPECS[name]
                single = decode_response(
                    run_cli("schema", name, "--format", encoding).stdout, encoding
                )
                self.assertEqual(
                    item,
                    {
                        key: value
                        for key, value in single.items()
                        if key not in {"status", "schema_version", "next"}
                    },
                )
                self.assertEqual(item["fields"], list(spec.fields))
                self.assertEqual(
                    item["optional_fields"],
                    sorted(ENTITY_OPTIONAL_FIELDS_BY_BLOCK.get(name, set())),
                )
                self.assertTrue(set(spec.fields).issubset(item["field_shapes"]))
                self.assertTrue(item["example"][name])
                self.assertEqual(item["id_prefix"], spec.id_prefix)
                self.assertEqual(item["label_prefix"], spec.label_prefix)
                if name == "design_tree":
                    self.assertIn("settled", item["field_shapes"]["answer"])
                    self.assertIn("research", item["field_shapes"]["evidence"])
                if name == "requirements":
                    self.assertIn("validation", item["optional_fields"])
                    self.assertEqual(
                        item["field_shapes"]["validation"], "array of non-empty strings"
                    )

    # A serializer or collection cap on successful templates would destroy selected blocks.
    def test_template_keeps_all_selected_blocks_and_validates_with_full_summary(self) -> None:
        names = list(BUNDLE.BLOCK_SPECS)
        result = run_cli("template", "--blocks", *names, "--format", "toon")
        self.assertEqual(result.returncode, 0, result.stdout)
        document = load_yaml(result.stdout)
        self.assertEqual(list(document["blocks"]), names)
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "template ' $;.yaml"
            source.write_text(result.stdout, encoding="utf-8")
            for encoding in ("yaml", "toon"):
                summary = run_cli("validate", str(source), "--format", encoding)
                self.assertEqual(summary.returncode, 0, summary.stdout)
                payload = decode_response(summary.stdout, encoding)
                self.assert_collection(payload, "selected_blocks", len(names), 20)
                full = self.follow(payload["next"][0], encoding)
                self.assertEqual(full["selected_blocks"], names)
                self.assert_collection(full, "selected_blocks", len(names), len(names))
                self.assertEqual(int(full["summary"]["blocks"]), len(names))

    # An unreadable example must remain discoverable with its identifier and path.
    def test_unreadable_examples_keep_counts_paths_and_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            installed = self.installation(Path(temporary))
            (installed / "examples" / "encoding.yaml").write_bytes(b"\xff")
            (installed / "examples" / "syntax.yaml").write_text("title: [broken", encoding="utf-8")
            for encoding in ("yaml", "toon"):
                payload = self.installed_response(installed, "examples", encoding=encoding)
                self.assert_collection(payload, "examples", 2, 2)
                self.assertEqual(
                    payload["examples"],
                    [
                        {"name": "encoding", "path": "examples/encoding.yaml"},
                        {"name": "syntax", "path": "examples/syntax.yaml"},
                    ],
                )
                self.assertTrue(payload["next"])

    # Existing Python callers may construct namespaces without the new --full option.
    def test_command_namespaces_without_full_keep_default_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            for command, args, collection in (
                (
                    command_status,
                    argparse.Namespace(output_root=Path(temporary)),
                    "existing_drafts",
                ),
                (command_schema, argparse.Namespace(blocks=[]), "blocks"),
                (command_examples, argparse.Namespace(name=None), "examples"),
            ):
                with self.subTest(command=command.__name__):
                    payload = command(args)
                    self.assertLessEqual(len(payload[collection]), 20)
                    self.assertEqual(
                        payload["collection_metadata"][collection]["shown_count"],
                        len(payload[collection]),
                    )

    # Session counts are independent of draft counts, and omitted sessions keep next commands.
    def test_status_bounds_live_sessions_without_slicing_session_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, contextlib.ExitStack() as servers:
            root = Path(temporary).resolve()
            sessions = []
            for count in (0, 19, 20, 21):
                for index in range(len(sessions), count):
                    session = root / f"session-{index} ' $;"
                    server = ServerFixture(self, session, ROUND_ONE)
                    servers.callback(server.stop)
                    register(session, SKILL_DIR, server.port)
                    sessions.append(session)
                for encoding in ("yaml", "toon"):
                    with self.subTest(count=count, encoding=encoding):
                        payload = decode_response(
                            run_cli(
                                "status",
                                "--output-root",
                                str(root / "output"),
                                "--format",
                                encoding,
                            ).stdout,
                            encoding,
                        )
                        self.assert_collection(payload, "existing_drafts", 0, 0)
                        self.assert_collection(payload, "interview_sessions", count, min(count, 20))
                        commands = [shlex.split(step)[2:] for step in payload["next"]]
                        for session in sessions:
                            self.assertIn(
                                ["interview", "status", str(session), "--format", encoding],
                                commands,
                            )
                        full = (
                            self.follow(payload["next"][0], encoding)
                            if count > 20
                            else decode_response(
                                run_cli(
                                    "status",
                                    "--output-root",
                                    str(root / "output"),
                                    "--full",
                                    "--format",
                                    encoding,
                                ).stdout,
                                encoding,
                            )
                        )
                        self.assert_collection(full, "interview_sessions", count, count)
                        self.assertEqual(
                            full["interview_sessions"],
                            [
                                {"session": str(session), "state": "round_open"}
                                for session in sessions
                            ],
                        )

    # Slicing before counting or dropping --output-root loses drafts on retrieval.
    def test_status_counts_drafts_before_slicing_and_retrieves_same_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "output ' $; &"
            output.mkdir()
            for count in (0, 19, 20, 21):
                for index in range(len(list(output.iterdir())), count):
                    bundle = output / f"PRD-{index:02}"
                    bundle.mkdir()
                    (bundle / "prd.yaml").touch()
                expected = {str(path / "prd.yaml") for path in output.iterdir()}
                for encoding in ("yaml", "toon"):
                    with self.subTest(count=count, encoding=encoding):
                        result = run_cli(
                            "status", "--output-root", str(output), "--format", encoding
                        )
                        self.assertEqual(result.returncode, 0, result.stdout)
                        payload = decode_response(result.stdout, encoding)
                        self.assert_collection(payload, "existing_drafts", count, min(count, 20))
                        self.assert_collection(payload, "interview_sessions", 0, 0)
                        self.assertEqual(int(payload["bundle_count"]), count)
                        self.assertTrue(payload["next"])
                        full = (
                            self.follow(payload["next"][0], encoding)
                            if count > 20
                            else decode_response(
                                run_cli(
                                    "status",
                                    "--output-root",
                                    str(output),
                                    "--full",
                                    "--format",
                                    encoding,
                                ).stdout,
                                encoding,
                            )
                        )
                        self.assert_collection(full, "existing_drafts", count, count)
                        self.assertEqual(set(full["existing_drafts"]), expected)
