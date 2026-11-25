"""Shared HTML rendering helpers for spec bundle output."""

from __future__ import annotations

import html

from ..spec import entity_label


def escape_html(value: str) -> str:
    return html.escape(value, quote=True)


def render_list(items: list[str]) -> str:
    return (
        '<ul class="list">' + "".join(f"<li>{escape_html(item)}</li>" for item in items) + "</ul>"
    )


def render_ref(entity_id: str) -> str:
    label = escape_html(entity_label(entity_id))
    return f'<a class="ref" href="#{escape_html(entity_id)}">{label}</a>'


def render_refs(references: list[str], shown: frozenset[str]) -> str:
    # A reference to an entity the page leaves out would be a dead link, so it is dropped.
    return ", ".join(render_ref(reference) for reference in references if reference in shown)


def _related_line(label: str, body_html: str) -> str:
    if not body_html:
        return ""
    return f'<p class="related"><span class="muted">{escape_html(label)}</span> {body_html}</p>'


def render_related(label: str, references: list[str], shown: frozenset[str]) -> str:
    return _related_line(label, render_refs(references, shown))


def render_evidence(references: list[str]) -> str:
    if not references:
        return ""
    evidence = "; ".join(escape_html(reference) for reference in references)
    return _related_line("Evidence", f'<span class="evidence">{evidence}</span>')


__all__ = [
    "escape_html",
    "render_evidence",
    "render_list",
    "render_ref",
    "render_refs",
    "render_related",
]
