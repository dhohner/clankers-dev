from __future__ import annotations

import re
import unittest

from support import (
    REVIEW_BLOCKS,
    example_without_open_questions,
    generate_example,
    load_example_manifest,
    rendered_sections,
    sample_block,
)


def example_with_every_review_block() -> dict:
    manifest = load_example_manifest()
    # The example omits only non-goals among the review blocks.
    manifest["blocks"]["non_goals"] = sample_block("non_goals")
    return manifest


def example_with_an_untested_requirement() -> dict:
    """Return the example with REQ-01 deferred and no test validating it."""
    manifest = load_example_manifest()
    manifest["blocks"]["testing_strategy"][0]["validates"] = []
    manifest["blocks"]["requirements"][0]["validation"] = []
    manifest["blocks"]["requirements"][0]["exception"] = "Covered by a later release."
    return manifest


def requirement_card(document: str) -> str:
    card = re.search(r'<article id="req-01".*?</article>', document)
    assert card is not None, "the page has no REQ-01 card"
    return card.group(0)


def summary_text(document: str) -> str:
    summary = re.search(r'<section class="standing".*?</section>', document)
    assert summary is not None, "the page has no summary"
    return re.sub(r"<[^>]+>", "", summary.group(0))


class ReviewPageTests(unittest.TestCase):
    def test_page_shows_only_the_product_review_blocks_in_canonical_order(self) -> None:
        document = generate_example(example_with_every_review_block())

        self.assertEqual(rendered_sections(document), REVIEW_BLOCKS)

    def test_context_lists_only_the_metadata_the_author_wrote(self) -> None:
        document = generate_example()

        context = re.search(r'<dl class="hero-meta"[^>]*>(.*?)</dl>', document)
        assert context is not None, "the page has no document context"
        labels = re.findall(r"<dt>(.*?)</dt>", context.group(1))

        self.assertEqual(labels, ["Owner", "Primary user", "Review mode"])

    def test_card_links_only_to_entries_on_the_page(self) -> None:
        # REQ-01 relates to DEC-01, which the page leaves out, and to RISK-01, which it shows.
        card = requirement_card(generate_example())

        links = re.findall(r'<a class="ref" href="#([a-z0-9-]+)">', card)

        self.assertEqual(links, ["req-01", "test-01", "risk-01"])

    def test_requirement_shows_the_outcome_of_the_test_that_proves_it(self) -> None:
        card = requirement_card(generate_example())

        self.assertIn("Done when", card)
        self.assertIn("index.html and every referenced local asset exist and resolve.", card)

    def test_requirement_without_a_test_says_so_and_gives_the_reason(self) -> None:
        card = requirement_card(generate_example(example_with_an_untested_requirement()))

        self.assertIn("No test yet", card)
        self.assertIn("Covered by a later release.", card)
        self.assertNotIn("Done when", card)

    def test_summary_states_the_decision_the_proof_and_what_waits(self) -> None:
        text = summary_text(generate_example(example_with_an_untested_requirement()))

        self.assertIn("Draft for review", text)
        self.assertIn("Read the requirements and the open questions", text)
        self.assertIn("4 requirements", text)
        self.assertIn("1 of them has no test yet.", text)
        self.assertIn("2 open questions", text)
        self.assertIn("3 risks", text)

    def test_draft_summary_without_open_questions_asks_only_for_the_requirements(self) -> None:
        document = generate_example(example_without_open_questions())

        self.assertIn("Read the requirements, then accept the spec or ask for changes.", document)

    def test_summary_of_an_accepted_spec_with_nothing_waiting(self) -> None:
        manifest = example_without_open_questions()
        manifest["status"] = "Accepted"

        text = summary_text(generate_example(manifest))

        self.assertIn("The work can now be split into tickets and coding tasks.", text)
        self.assertIn("Each one has a test that shows when it is done.", text)
        self.assertIn("No decision is waiting.", text)

    def test_status_that_only_mentions_acceptance_reads_as_waiting(self) -> None:
        # Downstream skills hand off only on exactly `Accepted`, so the page must agree.
        for status in ("Not accepted", "Awaiting acceptance", "accepted"):
            with self.subTest(status=status):
                manifest = example_without_open_questions()
                manifest["status"] = status

                document = generate_example(manifest)

                self.assertNotIn("The work can now be split", document)
                self.assertIn("then accept the spec or ask for changes.", document)
                bar_lamp = re.search(
                    r'class="doc-status">\s*<span class="lamp lamp--(\w+)"', document
                )
                assert bar_lamp is not None, "the page has no status lamp"
                self.assertEqual(bar_lamp.group(1), "wait")


if __name__ == "__main__":
    unittest.main()
