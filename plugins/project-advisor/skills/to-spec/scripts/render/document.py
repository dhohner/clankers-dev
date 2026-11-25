"""HTML document assembly for normalized spec manifests."""

from __future__ import annotations

import hashlib
from typing import Any

from ..manifest_types import NormalizedManifest
from ..paths import ASSET_DIR, TEMPLATE_PATH
from ..spec import (
    BLOCK_SPECS,
    REVIEW_PAGE_BLOCKS,
    TEMPLATE_MARKER_PATTERN,
    review_page_entity_ids,
)
from .blocks import BLOCK_RENDERERS
from .helpers import escape_html


def asset_version() -> str:
    digest = hashlib.sha256()
    for asset_path in sorted(ASSET_DIR.rglob("*")):
        if not asset_path.is_file():
            continue
        digest.update(asset_path.relative_to(ASSET_DIR).as_posix().encode("utf-8"))
        digest.update(asset_path.read_bytes())
    return digest.hexdigest()[:12]


def is_accepted(status: str) -> bool:
    # Downstream skills accept only the exact word, so "Not accepted" must not read as accepted.
    return status.strip() == "Accepted"


def status_lamp(status: str) -> str:
    if is_accepted(status):
        return "go"
    normalized = status.strip().lower()
    if "reject" in normalized or "block" in normalized:
        return "gap"
    return "wait"


def render_navigation(entries: list[tuple[str, str]]) -> str:
    links = [("summary", "Summary"), *entries]
    return "".join(
        f'<li><a href="#{anchor}">{escape_html(title)}</a></li>' for anchor, title in links
    )


def render_metadata(metadata: dict[str, str]) -> str:
    if not metadata:
        return ""
    rows = "".join(
        f"<div><dt>{escape_html(label)}</dt><dd>{escape_html(value)}</dd></div>"
        for label, value in metadata.items()
    )
    return f'<dl class="hero-meta">{rows}</dl>'


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}{'' if count == 1 else 's'}"


def _standing_row(topic: str, lamp: str, call_html: str, why: str) -> str:
    return (
        '<li class="standing-row">'
        f'<span class="standing-topic">{escape_html(topic)}</span>'
        '<div class="standing-body">'
        f'<p class="standing-call"><span class="lamp lamp--{lamp}" aria-hidden="true"></span>'
        f"{call_html}</p>"
        f'<p class="standing-why">{escape_html(why)}</p></div></li>'
    )


def render_standing(manifest: NormalizedManifest) -> str:
    """Say where the spec stands: the decision, the proof behind it, and what waits."""
    blocks: dict[str, Any] = manifest["blocks"]
    status = manifest["status"]
    questions = blocks.get("open_questions", [])
    if is_accepted(status):
        why = "The work can now be split into tickets and coding tasks."
    else:
        to_read = "the requirements and the open questions" if questions else "the requirements"
        why = f"Read {to_read}, then accept the spec or ask for changes."
    rows = [_standing_row("Decision", status_lamp(status), escape_html(status), why)]
    requirements = blocks.get("requirements", [])
    if requirements:
        tested = sum(bool(item.get("validation")) for item in requirements)
        untested = len(requirements) - tested
        call_html = f'<a href="#requirements">{_plural(len(requirements), "requirement")}</a>'
        if untested:
            verb = "has" if untested == 1 else "have"
            lamp, why = "gap", f"{untested} of them {verb} no test yet."
        else:
            lamp, why = "go", "Each one has a test that shows when it is done."
        rows.append(_standing_row("Requirements", lamp, call_html, why))
    if questions:
        call_html = f'<a href="#open_questions">{_plural(len(questions), "open question")}</a>'
        rows.append(
            _standing_row(
                "Open questions", "gap", call_html, "Answer them before you accept the spec."
            )
        )
    else:
        rows.append(_standing_row("Open questions", "go", "None", "No decision is waiting."))
    risks = blocks.get("risks", [])
    if risks:
        call_html = f'<a href="#risks">{_plural(len(risks), "risk")}</a>'
        rows.append(_standing_row("Risks", "go", call_html, "Each one names a mitigation."))
    return (
        '<section class="standing" aria-labelledby="standing-title">'
        '<h2 id="standing-title" class="standing-title">Where this spec stands</h2>'
        f'<ul class="standing-rows">{"".join(rows)}</ul></section>'
    )


def render_document(manifest: NormalizedManifest) -> str:
    blocks = manifest["blocks"]
    page_blocks = [(name, value) for name, value in blocks.items() if name in REVIEW_PAGE_BLOCKS]
    shown_ids = frozenset(review_page_entity_ids(blocks))
    tests = {item["id"]: item for item in blocks.get("testing_strategy", [])}

    navigation_entries: list[tuple[str, str]] = []
    rendered_blocks: list[str] = []
    for name, value in page_blocks:
        spec = BLOCK_SPECS[name]
        heading_id = f"{name}-heading"
        content = BLOCK_RENDERERS[name](value, shown_ids, tests)
        navigation_entries.append((name, spec.title))
        rendered_blocks.append(
            f'<section id="{name}" class="section" data-block="{name}" '
            f'aria-labelledby="{heading_id}">'
            '<div class="section-head">'
            f'<h2 id="{heading_id}">{escape_html(spec.title)}</h2>'
            f"<p>{escape_html(spec.description)}</p></div>"
            f"{content}</section>"
        )

    replacements = {
        "{{TITLE}}": escape_html(manifest["title"]),
        "{{SUMMARY}}": escape_html(manifest["summary"]),
        "{{STATUS}}": escape_html(manifest["status"]),
        "{{STATUS_LAMP}}": status_lamp(manifest["status"]),
        "{{ASSET_VERSION}}": asset_version(),
        "{{METADATA}}": render_metadata(manifest["metadata"]),
        "{{STANDING}}": render_standing(manifest),
        "{{NAVIGATION}}": render_navigation(navigation_entries),
        "{{BLOCKS}}": "\n".join(rendered_blocks),
    }
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    template_markers = set(TEMPLATE_MARKER_PATTERN.findall(template))
    unknown_markers = sorted(template_markers - replacements.keys())
    if unknown_markers:
        raise RuntimeError(f"template contains unresolved markers: {', '.join(unknown_markers)}")
    missing_markers = sorted(replacements.keys() - template_markers)
    if missing_markers:
        raise RuntimeError(f"template is missing expected markers: {', '.join(missing_markers)}")
    return TEMPLATE_MARKER_PATTERN.sub(lambda match: replacements[match.group(0)], template)


__all__ = ["render_document"]
