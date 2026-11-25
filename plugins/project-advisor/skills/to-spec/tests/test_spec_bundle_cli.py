from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from support import (
    EXAMPLE,
    SKILL_DIR,
    SOURCE_ASSETS,
    AnchorParser,
    dump_yaml,
    generate_example,
    load_example_manifest,
    load_yaml,
    run_cli,
    run_cli_process,
    run_generator,
)

from scripts.cli import support as cli_support


class SpecBundleCliTests(unittest.TestCase):
    def test_valid_manifest_generates_complete_bundle_with_copied_assets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            result = run_generator(EXAMPLE, root / "action-items")

            self.assertEqual(result.returncode, 0, result.stderr)
            bundle = root / "action-items" / "SPEC-example-review-bundle"
            document = (bundle / "index.html").read_text(encoding="utf-8")
            preserved_manifest = load_yaml((bundle / "spec.yaml").read_text(encoding="utf-8"))

            self.assertIn(
                '<h1 id="document-title">Rich Interactive HTML Output for to-spec</h1>',
                document,
            )
            self.assertNotIn("{{", document)
            self.assertIn("default-src 'none'", document)
            self.assertIn("script-src 'self';", document)
            self.assertIn("style-src 'self';", document)
            self.assertNotIn("'unsafe-inline'", document)
            self.assertIn('name="referrer" content="no-referrer"', document)
            self.assertIn('href="./assets/favicon.svg" type="image/svg+xml"', document)
            self.assertIn('href="./assets/styles.css?v=', document)
            self.assertIn('src="./assets/app.js?v=', document)
            self.assertNotIn("<svg", document)
            self.assertIn('<a class="bar-title" href="#summary">Project Advisor spec</a>', document)
            self.assertIn('aria-label="Contents"', document)
            self.assertIn('id="nav-toggle"', document)
            self.assertIn('class="footer"', document)
            self.assertIn('id="req-01"', document)
            self.assertIn('href="#req-01"', document)
            self.assertIn('id="risk-01"', document)
            self.assertIn('id="question-01"', document)
            self.assertIn('id="test-01"', document)
            self.assertIn('<ol class="ledger">', document)
            self.assertIn('<ol class="steps">', document)
            self.assertIn('<span class="step-num" aria-hidden="true">1</span>', document)
            self.assertIn('<section class="standing"', document)
            self.assertEqual(preserved_manifest["slug"], "example-review-bundle")
            self.assertEqual(preserved_manifest["schema_version"], 3)

            source_assets = sorted(
                path.relative_to(SOURCE_ASSETS)
                for path in SOURCE_ASSETS.rglob("*")
                if path.is_file()
                and not {"interview", "shared"}.intersection(path.relative_to(SOURCE_ASSETS).parts)
            )
            generated_assets = sorted(
                path.relative_to(bundle / "assets")
                for path in (bundle / "assets").rglob("*")
                if path.is_file()
            )
            self.assertEqual(generated_assets, source_assets)
            for asset in source_assets:
                if asset == Path("styles.css"):
                    continue
                self.assertEqual(
                    (bundle / "assets" / asset).read_bytes(),
                    (SOURCE_ASSETS / asset).read_bytes(),
                )

            anchors = AnchorParser()
            anchors.feed(document)
            self.assertEqual(len(anchors.ids), len(set(anchors.ids)))
            self.assertEqual(
                set(anchors.fragment_links) - set(anchors.ids),
                set(),
                "every generated fragment link should resolve to a unique target",
            )

    def test_generate_emits_structured_success_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)

            result = run_cli(
                "generate",
                str(EXAMPLE),
                "--output-root",
                str(root / "action-items"),
            )
            payload = load_yaml(result.stdout)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["validation"], {"manifest": "ok", "bundle": "ok"})
            self.assertTrue(Path(payload["files"]["index"]).exists())
            self.assertIn(" inspect", payload["next"][1])

    def test_validate_emits_aggregates_without_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)

            result = run_cli("validate", str(EXAMPLE))
            payload = load_yaml(result.stdout)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["normalized_slug"], "example-review-bundle")
            self.assertEqual(payload["summary"]["requirements"], "4")
            self.assertIn("workflow", payload["review_surfaces"])
            self.assertFalse((root / "action-items").exists())

    def test_no_arg_dashboard_is_content_first(self) -> None:
        result = run_cli()
        payload = load_yaml(result.stdout)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["status"], "ok")
        self.assertIn("generator", payload)
        self.assertIn("bundle_count", payload)
        self.assertIn("next", payload)

    def test_status_ignores_broken_bundle_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_root = root / "action-items"
            output_root.mkdir()
            (output_root / "SPEC-broken").symlink_to(root / "missing")

            result = run_cli("status", "--output-root", str(output_root))
            payload = load_yaml(result.stdout)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["bundle_count"], "0")

    def test_inspect_emits_bundle_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_root = root / "action-items"
            generated = run_generator(EXAMPLE, output_root)
            self.assertEqual(generated.returncode, 0, generated.stderr)

            bundle = output_root / "SPEC-example-review-bundle"
            result = run_cli("inspect", str(bundle))
            payload = load_yaml(result.stdout)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(payload["status"], "ok")
            self.assertIn("requirements", payload["sections"])
            self.assertIn("req-01", payload["ids"])
            self.assertEqual(payload["anchors"]["broken"], [])
            self.assertEqual(payload["traceability"]["requirements"], "4")

    def test_inspect_lists_the_entries_still_held_by_a_coverage_gap(self) -> None:
        # REQ-01 names no decision or risk, and QUESTION-01 names no requirement.
        source = SKILL_DIR / "evals" / "inputs" / "spec-bundle-review-notes.yaml"
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_root = Path(temporary_directory) / "action-items"
            generated = run_generator(source, output_root)
            self.assertEqual(generated.returncode, 0, generated.stderr)

            result = run_cli("inspect", str(output_root / "SPEC-bundle-review-notes"))
            payload = load_yaml(result.stdout)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                payload["traceability"]["held"],
                [
                    {"id": "REQ-01", "gap": "No decision or risk context"},
                    {"id": "QUESTION-01", "gap": "Not connected to a requirement"},
                ],
            )

    def test_inspect_reports_every_nested_design_tree_node(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_root = root / "action-items"
            generated = run_generator(EXAMPLE, output_root)
            self.assertEqual(generated.returncode, 0, generated.stderr)

            bundle = output_root / "SPEC-example-review-bundle"
            result = run_cli("inspect", str(bundle))
            payload = load_yaml(result.stdout)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("design_tree", payload["sections"])
            for identity in ("node-01", "node-02", "node-03", "node-04", "node-05"):
                self.assertIn(identity, payload["ids"])
            self.assertEqual(payload["anchors"]["broken"], [])

    def test_template_emits_valid_placeholder_manifest(self) -> None:
        blocks = [
            "goals",
            "personas",
            "user_stories",
            "journeys",
            "failure_paths",
            "requirements",
            "decisions",
            "rollout",
            "testing_strategy",
            "open_questions",
            "repository_grounding",
        ]
        # Version 2 requires the design tree, so the template adds it at its
        # canonical position even when the author did not select it.
        position = blocks.index("rollout")
        expected_blocks = [*blocks[:position], "design_tree", *blocks[position:]]
        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest_path = Path(temporary_directory) / "spec.yaml"
            result = run_cli("template", "--blocks", *blocks)
            manifest_path.write_text(result.stdout, encoding="utf-8")
            validation = run_cli("validate", str(manifest_path))
            manifest = load_yaml(result.stdout)
            validation_payload = load_yaml(validation.stdout)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(manifest["slug"], "draft-spec")
            self.assertEqual(manifest["schema_version"], 3)
            self.assertEqual(list(manifest["blocks"]), expected_blocks)
            self.assertEqual(
                manifest["blocks"]["design_tree"][0]["id"],
                "NODE-01",
            )
            self.assertEqual(
                manifest["blocks"]["goals"][0]["goal"],
                "Replace with goal.",
            )
            self.assertEqual(
                manifest["blocks"]["requirements"][0]["validation"],
                ["TEST-01"],
            )
            self.assertEqual(
                manifest["blocks"]["testing_strategy"][0]["validates"],
                ["REQ-01"],
            )
            self.assertEqual(validation.returncode, 0, validation.stderr)
            self.assertEqual(validation_payload["selected_blocks"], expected_blocks)
            self.assertEqual(validation_payload["manifest_version"], "3")

    def test_schema_and_examples_are_structured(self) -> None:
        top_level_schema = run_cli("schema")
        top_level_payload = load_yaml(top_level_schema.stdout)
        authoring_schema = run_cli("schema", "--authoring")
        authoring_payload = load_yaml(authoring_schema.stdout)
        schema = run_cli("schema", "requirements")
        schema_payload = load_yaml(schema.stdout)
        multi_schema = run_cli("schema", "goals", "personas", "testing_strategy")
        multi_schema_payload = load_yaml(multi_schema.stdout)
        examples = run_cli("examples", "api-heavy")
        examples_payload = load_yaml(examples.stdout)
        all_examples = run_cli("examples")
        all_examples_payload = load_yaml(all_examples.stdout)

        self.assertEqual(top_level_schema.returncode, 0, top_level_schema.stderr)
        self.assertEqual(authoring_schema.returncode, 0, authoring_schema.stderr)
        self.assertIn("mixed", authoring_payload["initiative_types"])
        self.assertIn(
            "document",
            authoring_payload["required_review_surfaces_by_initiative"]["mixed"],
        )
        self.assertIn("requirements", authoring_payload["blocks"])
        self.assertNotIn("review_surfaces", authoring_payload)
        self.assertEqual(
            top_level_payload["required_review_surfaces_by_initiative"]["data-heavy"],
            ["document", "data"],
        )
        self.assertEqual(schema.returncode, 0, schema.stderr)
        self.assertEqual(schema_payload["block"], "requirements")
        self.assertIn("validation", schema_payload["optional_fields"])
        self.assertIn("array", schema_payload["field_shapes"]["evidence"])
        self.assertEqual(
            schema_payload["example"]["requirements"][0]["id"],
            "REQ-01",
        )
        self.assertEqual(multi_schema.returncode, 0, multi_schema.stderr)
        self.assertEqual(
            [item["block"] for item in multi_schema_payload["schemas"]],
            ["goals", "personas", "testing_strategy"],
        )
        self.assertEqual(
            multi_schema_payload["schemas"][0]["example"]["goals"][0]["goal"],
            "Example goal",
        )
        self.assertNotIn("status", multi_schema_payload["schemas"][0])
        self.assertEqual(examples.returncode, 0, examples.stderr)
        self.assertEqual(examples_payload["examples"][0]["name"], "api-heavy")
        self.assertIn(" validate", examples_payload["next"][0])
        self.assertEqual(all_examples.returncode, 0, all_examples.stderr)
        self.assertEqual(all_examples_payload["examples"][0]["name"], "minimal-spec")

    def test_manifest_content_is_html_escaped(self) -> None:
        manifest = load_example_manifest()
        manifest["title"] = '<script>alert("no")</script>'

        document = generate_example(manifest)

        self.assertNotIn("<script>alert", document)
        self.assertIn("&lt;script&gt;alert", document)

    def test_manifest_content_that_looks_like_template_syntax_is_preserved(self) -> None:
        manifest = load_example_manifest()
        manifest["title"] = "Keep {{STATUS}} literal"

        document = generate_example(manifest)

        self.assertIn(
            '<h1 id="document-title">Keep {{STATUS}} literal</h1>',
            document,
        )

    def test_preserved_manifest_keeps_quoted_metadata_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest = load_example_manifest()
            manifest["metadata"] = {"Owner: team": "A", "Release #": "1"}
            manifest_path = root / "manifest.yaml"
            manifest_path.write_text(dump_yaml(manifest), encoding="utf-8")

            result = run_generator(manifest_path, root / "action-items")
            preserved_manifest = load_yaml(
                (root / "action-items" / "SPEC-example-review-bundle" / "spec.yaml").read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(preserved_manifest["metadata"], manifest["metadata"])

    def test_duplicate_yaml_keys_are_rejected_before_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest_path = root / "duplicate.yaml"
            manifest_path.write_text(
                "schema_version: 1\nschema_version: 1\n",
                encoding="utf-8",
            )

            result = run_generator(manifest_path, root / "action-items")

            payload = load_yaml(result.stdout)

            self.assertEqual(result.returncode, 2)
            self.assertEqual(payload["code"], "yaml_invalid")
            self.assertIn(
                "YAML mapping contains duplicate key(s): schema_version",
                payload["errors"][0]["message"],
            )
            self.assertEqual(result.stderr, "")
            self.assertFalse((root / "action-items").exists())

    def test_invalid_manifest_reports_all_errors_without_creating_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest_path = root / "invalid.yaml"
            manifest_path.write_text(
                dump_yaml({"schema_version": 4, "slug": "../escape"}),
                encoding="utf-8",
            )

            result = run_generator(manifest_path, root / "action-items")

            payload = load_yaml(result.stdout)
            messages = "\n".join(error["message"] for error in payload["errors"])

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(payload["code"], "manifest_invalid")
            self.assertIn(
                "schema_version must be the number 3",
                messages,
            )
            self.assertIn("slug must contain only lowercase", messages)
            self.assertIn("initiative_type must be a non-empty string", messages)
            self.assertIn("review_surfaces must be a non-empty array", messages)
            self.assertIn("blocks must be a non-empty object", messages)
            self.assertEqual(result.stderr, "")
            self.assertFalse((root / "action-items" / "SPEC-escape").exists())
            self.assertFalse((root / "action-items").exists())

    def test_invalid_yaml_has_location_and_creates_no_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest_path = root / "invalid.yaml"
            manifest_path.write_text('{"schema_version": 1,}', encoding="utf-8")

            result = run_generator(manifest_path, root / "action-items")

            payload = load_yaml(result.stdout)

            self.assertEqual(result.returncode, 2)
            self.assertEqual(payload["code"], "yaml_invalid")
            self.assertIn("line 1, column", payload["errors"][0]["message"])
            self.assertEqual(result.stderr, "")
            self.assertFalse((root / "action-items").exists())

    def test_boolean_schema_version_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest = load_example_manifest()
            manifest["schema_version"] = True
            manifest_path = root / "manifest.yaml"
            manifest_path.write_text(dump_yaml(manifest), encoding="utf-8")

            result = run_generator(manifest_path, root / "action-items")

            payload = load_yaml(result.stdout)

            self.assertEqual(result.returncode, 2)
            self.assertEqual(payload["code"], "manifest_invalid")
            self.assertIn(
                "schema_version must be the number 3",
                payload["errors"][0]["message"],
            )
            self.assertEqual(result.stderr, "")
            self.assertFalse((root / "action-items").exists())

    def test_current_manifest_without_a_design_tree_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest = load_example_manifest()
            del manifest["blocks"]["design_tree"]
            manifest_path = root / "manifest.yaml"
            manifest_path.write_text(dump_yaml(manifest), encoding="utf-8")

            result = run_generator(manifest_path, root / "action-items")
            payload = load_yaml(result.stdout)
            messages = "\n".join(error["message"] for error in payload["errors"])

            self.assertEqual(result.returncode, 2)
            self.assertEqual(payload["code"], "manifest_invalid")
            self.assertIn(
                "blocks.design_tree is required by schema_version 3",
                messages,
            )
            self.assertEqual(payload["errors"][0]["path"], "blocks.design_tree")
            self.assertFalse((root / "action-items").exists())

    def test_unsupported_schema_versions_name_the_accepted_version(self) -> None:
        rejected = {
            "too_new": 4,
            "previous": 2,
            "zero": 0,
            "quoted": "2",
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            for name, version in rejected.items():
                with self.subTest(version=name):
                    manifest = load_example_manifest()
                    manifest["schema_version"] = version
                    manifest_path = root / f"{name}.yaml"
                    manifest_path.write_text(dump_yaml(manifest), encoding="utf-8")

                    result = run_cli("validate", str(manifest_path))
                    payload = load_yaml(result.stdout)
                    messages = "\n".join(error["message"] for error in payload["errors"])

                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(payload["code"], "manifest_invalid")
                    self.assertIn(
                        "schema_version must be the number 3",
                        messages,
                    )
                    self.assertNotIn("design_tree is required", messages)

            manifest = load_example_manifest()
            del manifest["schema_version"]
            manifest_path = root / "missing.yaml"
            manifest_path.write_text(dump_yaml(manifest), encoding="utf-8")

            result = run_cli("validate", str(manifest_path))
            payload = load_yaml(result.stdout)

            self.assertEqual(result.returncode, 2)
            self.assertIn(
                "schema_version must be the number 3",
                payload["errors"][0]["message"],
            )

    def test_reports_name_the_applied_manifest_version(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_root = root / "action-items"

            validation = run_cli("validate", str(EXAMPLE))
            generation = run_generator(EXAMPLE, output_root)
            inspection = run_cli(
                "inspect",
                str(output_root / "SPEC-example-review-bundle"),
            )

            self.assertEqual(validation.returncode, 0, validation.stderr)
            self.assertEqual(generation.returncode, 0, generation.stderr)
            self.assertEqual(inspection.returncode, 0, inspection.stderr)
            for result in (validation, generation, inspection):
                self.assertEqual(load_yaml(result.stdout)["manifest_version"], "3")

    def test_existing_bundle_requires_force_and_force_replaces_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_root = root / "action-items"
            first = run_generator(EXAMPLE, output_root)
            self.assertEqual(first.returncode, 0, first.stderr)
            sentinel = output_root / "SPEC-example-review-bundle" / "old.txt"
            sentinel.write_text("old", encoding="utf-8")

            refused = run_generator(EXAMPLE, output_root)
            payload = load_yaml(refused.stdout)
            self.assertEqual(refused.returncode, 2)
            self.assertEqual(payload["code"], "bundle_exists")
            self.assertIn(" inspect", payload["next"][0])
            self.assertTrue(sentinel.exists())

            replaced = run_generator(EXAMPLE, output_root, "--force")
            self.assertEqual(replaced.returncode, 0, replaced.stderr)
            self.assertFalse(sentinel.exists())
            self.assertTrue((output_root / "SPEC-example-review-bundle" / "index.html").exists())

    def test_force_does_not_delete_a_preexisting_backup_named_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_root = root / "action-items"
            first = run_generator(EXAMPLE, output_root)
            self.assertEqual(first.returncode, 0, first.stderr)
            unrelated_backup = output_root / ".SPEC-example-review-bundle.backup"
            unrelated_backup.mkdir()
            sentinel = unrelated_backup / "unrelated.txt"
            sentinel.write_text("keep", encoding="utf-8")

            replaced = run_generator(EXAMPLE, output_root, "--force")

            self.assertEqual(replaced.returncode, 0, replaced.stderr)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

    def test_force_safely_replaces_a_symlink_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_root = root / "action-items"
            output_root.mkdir()
            external_directory = root / "external"
            external_directory.mkdir()
            sentinel = external_directory / "sentinel.txt"
            sentinel.write_text("keep", encoding="utf-8")
            target = output_root / "SPEC-example-review-bundle"
            target.symlink_to(external_directory, target_is_directory=True)

            replaced = run_generator(EXAMPLE, output_root, "--force")

            self.assertEqual(replaced.returncode, 0, replaced.stderr)
            self.assertFalse(target.is_symlink())
            self.assertTrue((target / "index.html").exists())
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")


class SpecBundleEntrypointTests(unittest.TestCase):
    """Checks of `python -m scripts`, which the other tests replace with in-process calls."""

    def test_entry_point_validates_generates_and_inspects_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_root = Path(temporary_directory) / "action-items"
            bundle = output_root / "SPEC-example-review-bundle"
            commands = {
                "validate": ("validate", str(EXAMPLE)),
                "generate": ("generate", str(EXAMPLE), "--output-root", str(output_root)),
                "inspect": ("inspect", str(bundle)),
            }
            for name, args in commands.items():
                with self.subTest(name):
                    result = run_cli_process(*args)

                    self.assertEqual(result.returncode, 0, result.stderr)
                    # A RuntimeWarning about `scripts.__main__` would show up here.
                    self.assertEqual(result.stderr, "")
                    self.assertEqual(load_yaml(result.stdout)["manifest_version"], "3")
            self.assertTrue((bundle / "index.html").exists())

    def test_in_process_run_matches_entry_point_run(self) -> None:
        cases = {
            "success with next commands": ("validate", str(EXAMPLE)),
            "usage error": ("generate",),
            "help": ("generate", "--help"),
            "interview usage error": ("interview", "status"),
        }
        for name, args in cases.items():
            with self.subTest(name):
                process = run_cli_process(*args)

                result = run_cli(*args)

                self.assertEqual(
                    (result.returncode, result.stdout, result.stderr),
                    (process.returncode, process.stdout, process.stderr),
                )


class InterpreterTests(unittest.TestCase):
    def test_too_old_interpreter_exits_with_a_message_instead_of_a_syntax_error(self) -> None:
        entrypoint = str(SKILL_DIR / "scripts" / "__main__.py")
        runs = {
            "python -m scripts": "runpy.run_module('scripts', run_name='__main__')",
            "python scripts/__main__.py": f"runpy.run_path({entrypoint!r}, run_name='__main__')",
        }
        for name, run in runs.items():
            with self.subTest(name):
                # The guard reads sys.version_info, so a lowered value stands in for Python 3.9.
                code = f"import runpy, sys; sys.version_info = (3, 9, 6); {run}"
                result = subprocess.run(
                    [sys.executable, "-c", code],
                    check=False,
                    capture_output=True,
                    text=True,
                    cwd=SKILL_DIR,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                )

                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertIn("to-spec needs Python 3.14 or newer", result.stderr)
                self.assertIn("is Python 3.9.6", result.stderr)
                self.assertIn("uv run --no-project --python 3.14 python ", result.stderr)
                self.assertNotIn("SyntaxError", result.stderr)

    def test_next_commands_name_the_running_interpreter_unless_python3_is_it(self) -> None:
        executable = Path(sys.executable).resolve()
        cases = {
            "python3 on PATH is the running interpreter": (str(executable), "python3 "),
            "python3 on PATH is another interpreter": ("/usr/bin/false", f"{sys.executable} "),
            "no python3 on PATH": (None, f"{sys.executable} "),
        }
        for name, (on_path, prefix) in cases.items():
            with (
                self.subTest(name),
                mock.patch.object(cli_support.shutil, "which", return_value=on_path),
            ):
                result = run_cli("examples")

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f'  - "{prefix}scripts/__main__.py', result.stdout)
