from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from support import (
    BUNDLE,
    REVIEW_BLOCKS,
    base_manifest,
    example_without_open_questions,
    generate_bundle_dir,
    generate_example,
    load_yaml,
    rendered_sections,
    sample_block,
)

from scripts.render.blocks import BLOCK_RENDERERS
from scripts.spec import REVIEW_PAGE_BLOCKS


class SpecBundleRenderingTests(unittest.TestCase):
    def test_omitted_open_questions_leave_no_section_or_navigation(self) -> None:
        document = generate_example(example_without_open_questions())

        self.assertNotIn('id="open_questions"', document)
        self.assertNotIn('href="#open_questions"', document)
        self.assertIn('data-block="testing_strategy"', document)

    def test_every_review_page_block_has_a_renderer(self) -> None:
        self.assertEqual(set(BLOCK_RENDERERS), REVIEW_PAGE_BLOCKS)
        self.assertEqual(set(REVIEW_BLOCKS), REVIEW_PAGE_BLOCKS)

    def test_representative_initiatives_show_only_their_selected_review_blocks(self) -> None:
        fixtures = {
            "workflow-heavy": (
                ["document", "workflow"],
                [
                    "problem",
                    "personas",
                    "journeys",
                    "state_transition_matrix",
                    "failure_paths",
                ],
            ),
            "api-heavy": (
                ["document", "api"],
                ["problem", "requirements", "api_contract", "dependencies", "testing_strategy"],
            ),
            "data-heavy": (
                ["document", "data"],
                ["problem", "requirements", "data_model", "security_privacy"],
            ),
            "architecture-heavy": (
                ["document", "architecture"],
                ["problem", "decisions", "risks"],
            ),
            "mixed": (
                ["document", "api", "data"],
                [
                    "problem",
                    "user_stories",
                    "requirements",
                    "api_contract",
                    "data_model",
                    "rollout",
                ],
            ),
            "small-feature": (
                ["document"],
                ["problem", "goals", "requirements", "scope", "testing_strategy"],
            ),
        }
        # The page shows the review blocks of each selection, in catalog order.
        shown_blocks = {
            "workflow-heavy": ["problem"],
            "api-heavy": ["problem", "requirements", "testing_strategy"],
            "data-heavy": ["problem", "requirements"],
            "architecture-heavy": ["problem", "risks"],
            "mixed": ["problem", "requirements", "rollout"],
            "small-feature": ["problem", "goals", "requirements", "scope", "testing_strategy"],
        }
        for initiative_type, (surfaces, selected) in fixtures.items():
            shown = shown_blocks[initiative_type]
            with self.subTest(initiative_type=initiative_type):
                manifest = base_manifest(initiative_type, surfaces)
                manifest["blocks"] |= {name: sample_block(name) for name in reversed(selected)}
                document = generate_example(manifest)
                self.assertEqual(rendered_sections(document), shown)
                for name in set(BUNDLE.BLOCK_SPECS) - set(shown):
                    self.assertNotIn(f'href="#{name}"', document)

    def test_full_catalog_shows_review_blocks_as_stable_semantic_sections(self) -> None:
        manifest = base_manifest("mixed", sorted(BUNDLE.REVIEW_SURFACES))
        manifest["blocks"] |= {name: sample_block(name) for name in BUNDLE.BLOCK_SPECS}
        normalized = BUNDLE.validate_manifest(manifest)
        document = BUNDLE.render_document(normalized)

        for name in REVIEW_BLOCKS:
            self.assertIn(
                f'<section id="{name}" class="section" data-block="{name}"',
                document,
            )
            self.assertIn(f'aria-labelledby="{name}-heading"', document)
            self.assertIn(f'<a href="#{name}">{BUNDLE.BLOCK_SPECS[name].title}</a>', document)
        self.assertIn('id="req-01"', document)
        self.assertIn('id="risk-01"', document)
        self.assertIn('id="question-01"', document)
        self.assertIn('id="test-01"', document)
        self.assertIn("<th>Test</th><th>What it checks</th>", document)
        test_row = re.search(r'<tr id="test-01">(.*?)</tr>', document)
        assert test_row is not None, "the page has no TEST-01 row"
        self.assertEqual(
            re.findall(r'<td data-label="([^"]+)">', test_row.group(1)),
            ["Test", "What it checks", "Expected outcome", "Proves"],
        )

    def test_optional_blocks_do_not_renumber_stable_entities(self) -> None:
        manifest = base_manifest()
        stable_blocks = ["requirements", "decisions", "risks", "testing_strategy", "open_questions"]
        manifest["blocks"] |= {name: sample_block(name) for name in stable_blocks}
        before = BUNDLE.render_document(BUNDLE.validate_manifest(manifest))

        manifest["blocks"]["personas"] = sample_block("personas")
        manifest["blocks"]["dependencies"] = sample_block("dependencies")
        after = BUNDLE.render_document(BUNDLE.validate_manifest(manifest))

        for identity in ("req-01", "risk-01", "question-01", "test-01"):
            self.assertEqual(before.count(f'id="{identity}"'), 1)
            self.assertEqual(after.count(f'id="{identity}"'), 1)

    def test_design_tree_survives_generation_and_bundle_revalidation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest = base_manifest()
            manifest["slug"] = "tree-round-trip"
            manifest["blocks"] = {"design_tree": sample_block("design_tree")}

            bundle = generate_bundle_dir(manifest, root)
            preserved = load_yaml((bundle / "spec.yaml").read_text(encoding="utf-8"))

            root_node = preserved["blocks"]["design_tree"][0]
            self.assertEqual("node-01", root_node["id"])
            self.assertEqual("Output surface", root_node["label"])
            self.assertEqual("node-02", root_node["children"][0]["id"])
            self.assertEqual(
                "Styling is an implementation choice.",
                root_node["children"][0]["reason"],
            )
            BUNDLE.validate_generated_bundle(bundle)
