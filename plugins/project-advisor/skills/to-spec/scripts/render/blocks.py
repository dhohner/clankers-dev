"""Block-specific rendering for the review page of a spec."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .helpers import (
    escape_html,
    render_evidence,
    render_list,
    render_ref,
    render_refs,
    render_related,
)


def _row(label: str, body: str, anchor: str = "") -> str:
    identity = f' id="{escape_html(anchor)}"' if anchor else ""
    return (
        f'<li class="row"{identity}><div class="row-label">{label}</div>'
        f'<div class="row-body">{body}</div></li>'
    )


def render_problem(value: dict[str, Any]) -> str:
    return (
        f'<p class="statement">{escape_html(value["statement"])}</p>'
        '<h3 class="subhead">What shows the problem</h3>'
        f"{render_list(value['evidence'])}"
    )


def render_goals(items: list[dict[str, Any]]) -> str:
    rows = "".join(
        _row(
            escape_html(item["goal"]),
            '<p class="muted small">Success looks like</p>'
            f"<p>{escape_html(item['success_signal'])}</p>",
        )
        for item in items
    )
    return f'<ul class="rows">{rows}</ul>'


def _done_when(item: dict[str, Any], tests: dict[str, dict[str, Any]]) -> str:
    """Show what proves a requirement, so a reader needs no jump to the test table."""
    checks = [
        f"<li>{render_ref(test_id)} "
        f'<span class="done-target">{escape_html(tests[test_id]["target"])}.</span> '
        f"{escape_html(tests[test_id]['expected_outcome'])}</li>"
        for test_id in item.get("validation", [])
    ]
    if checks:
        return (
            f'<div class="done"><p class="done-label">Done when</p><ul>{"".join(checks)}</ul></div>'
        )
    reason = f"<p>{escape_html(item['exception'])}</p>" if item.get("exception") else ""
    return (
        '<div class="done done--gap"><p class="done-label">'
        f'<span class="lamp" aria-hidden="true"></span>No test yet</p>{reason}</div>'
    )


def render_requirements(
    items: list[dict[str, Any]], shown: frozenset[str], tests: dict[str, dict[str, Any]]
) -> str:
    entries = "".join(
        f'<li><article id="{escape_html(item["id"])}" class="req">'
        f'<div class="req-head">{render_ref(item["id"])}<h3>{escape_html(item["title"])}</h3></div>'
        '<div class="req-body">'
        f"<p>{escape_html(item['description'])}</p>"
        f"{_done_when(item, tests)}"
        f"{render_related('Related', item.get('relates_to', []), shown)}"
        f"{render_evidence(item.get('evidence', []))}"
        "</div></article></li>"
        for item in items
    )
    return f'<ol class="ledger">{entries}</ol>'


def render_scope(value: dict[str, Any]) -> str:
    return (
        '<div class="split">'
        f'<div><h3 class="subhead">In scope</h3>{render_list(value["in"])}</div>'
        f'<div><h3 class="subhead">Out of scope</h3>{render_list(value["out"])}</div>'
        "</div>"
    )


def render_risks(items: list[dict[str, Any]], shown: frozenset[str]) -> str:
    rows = "".join(
        _row(
            f"{render_ref(item['id'])}<span>{escape_html(item['risk'])}</span>",
            '<p class="muted small">Mitigation</p>'
            f"<p>{escape_html(item['mitigation'])}</p>"
            f"{render_related('Affects', item.get('relates_to', []), shown)}"
            f"{render_evidence(item.get('evidence', []))}",
            anchor=item["id"],
        )
        for item in items
    )
    return f'<ul class="rows">{rows}</ul>'


def render_rollout(items: list[dict[str, Any]]) -> str:
    steps = "".join(
        f'<li><span class="step-num" aria-hidden="true">{index}</span>'
        f"<div><h3>{escape_html(item['phase'])}</h3><p>{escape_html(item['outcome'])}</p></div></li>"
        for index, item in enumerate(items, start=1)
    )
    return f'<ol class="steps">{steps}</ol>'


TEST_COLUMNS = ("Test", "What it checks", "Expected outcome", "Proves")


def render_tests(items: list[dict[str, Any]], shown: frozenset[str]) -> str:
    def row(item: dict[str, Any]) -> str:
        cells = (
            render_ref(item["id"]),
            escape_html(item["target"]),
            escape_html(item["expected_outcome"]),
            render_refs(item.get("validates", []), shown) or "None",
        )
        # Narrow screens drop the header row, so every cell carries its own label.
        return (
            f'<tr id="{escape_html(item["id"])}">'
            + "".join(
                f'<td data-label="{heading}">{cell}</td>'
                for heading, cell in zip(TEST_COLUMNS, cells, strict=True)
            )
            + "</tr>"
        )

    headings = "".join(f"<th>{heading}</th>" for heading in TEST_COLUMNS)
    return (
        '<div class="table-wrap"><table class="ref-table"><thead><tr>'
        f"{headings}</tr></thead><tbody>{''.join(row(item) for item in items)}</tbody>"
        "</table></div>"
    )


def render_questions(items: list[dict[str, Any]], shown: frozenset[str]) -> str:
    entries = "".join(
        f'<li id="{escape_html(item["id"])}">'
        f'<p class="question">{render_ref(item["id"])} {escape_html(item["question"])}</p>'
        f"{render_related('Affects', item.get('relates_to', []), shown)}</li>"
        for item in items
    )
    return f'<ul class="questions">{entries}</ul>'


# Each renderer takes the block value, the entity IDs shown on the page, and the tests by ID.
# The keys must match `REVIEW_PAGE_BLOCKS`; a test enforces it.
BLOCK_RENDERERS: dict[str, Callable[[Any, frozenset[str], dict[str, dict[str, Any]]], str]] = {
    "problem": lambda value, shown, tests: render_problem(value),
    "goals": lambda value, shown, tests: render_goals(value),
    "non_goals": lambda value, shown, tests: render_list(value),
    "requirements": render_requirements,
    "scope": lambda value, shown, tests: render_scope(value),
    "risks": lambda value, shown, tests: render_risks(value, shown),
    "rollout": lambda value, shown, tests: render_rollout(value),
    "testing_strategy": lambda value, shown, tests: render_tests(value, shown),
    "open_questions": lambda value, shown, tests: render_questions(value, shown),
}


__all__ = ["BLOCK_RENDERERS"]
