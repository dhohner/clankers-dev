"""Shared schema example and manifest template block payloads."""

from __future__ import annotations

from typing import Any

from ..spec import BLOCK_SPECS


def example_block(block: str) -> Any:
    return _catalog_block(block, template=False)


def template_block(block: str) -> Any:
    return _catalog_block(block, template=True)


def _field_text(field: str, template: bool) -> str:
    label = field.replace("_", " ")
    return f"Replace with {label}." if template else f"Example {label}"


def _catalog_block(block: str, template: bool) -> Any:
    def text(example: str, placeholder: str) -> str:
        return placeholder if template else example

    spec = BLOCK_SPECS[block]
    if spec.kind == "summary":
        return {
            "metrics": [
                {
                    "label": text("Current", "Replace with metric label"),
                    "value": text("Manual review", "Replace with metric value"),
                    "description": text(
                        "Reviewers need a compact signal.",
                        "Replace with why this metric matters.",
                    ),
                }
            ],
            "recommendation": text(
                "Generate a validated spec bundle for review.",
                "Replace with recommended product direction.",
            ),
        }
    if spec.kind == "problem":
        return {
            "statement": text(
                "Reviewers need a clear statement of the problem.",
                "Replace with the problem statement.",
            ),
            "evidence": [
                text(
                    "Repository or user evidence that supports the problem.",
                    "Replace with user, business, or repository evidence.",
                )
            ],
        }
    if spec.kind == "scope":
        return {
            "in": [text("Behavior included in this spec.", "Replace with included scope.")],
            "out": [
                text(
                    "Adjacent behavior intentionally excluded.",
                    "Replace with excluded scope.",
                )
            ],
        }
    if spec.kind == "table":
        if template:
            return {
                "columns": ["Replace with first column", "Replace with second column"],
                "rows": [["Replace with first value", "Replace with second value"]],
            }
        return {"columns": ["From", "To"], "rows": [["Current", "Target"]]}
    if spec.kind == "questions":
        return [
            {
                "id": f"{spec.label_prefix or 'QUESTION'}-01",
                "question": text(
                    "Which decision still needs confirmation?",
                    "Replace with open question.",
                ),
            }
        ]
    if spec.kind == "tree":
        return [
            {
                "id": f"{spec.label_prefix or 'NODE'}-01",
                "label": text("Output surface", "Replace with short decision name"),
                "question": text(
                    "Where is the design tree stored?",
                    "Replace with the verbatim interview question.",
                ),
                "status": "settled",
                "answer": text(
                    "In spec.yaml beside the decisions.",
                    "Replace with the answer.",
                ),
                "source": "user",
                "rationale": text(
                    "Downstream skills read the tree from spec.yaml.",
                    "Replace with why this answer was chosen.",
                ),
                "children": [
                    {
                        "id": f"{spec.label_prefix or 'NODE'}-02",
                        "label": text("Node styling", "Replace with short decision name"),
                        "question": text(
                            "Which colours mark a pruned branch?",
                            "Replace with the verbatim interview question.",
                        ),
                        "status": "pruned",
                        "reason": text(
                            "Styling is an implementation choice, not a product decision.",
                            "Replace with why this branch left spec scope.",
                        ),
                    }
                ],
            }
        ]
    if spec.kind == "list":
        return [text("Outcome intentionally excluded from this spec.", "Replace with item.")]
    if spec.kind == "code":
        return [
            {
                "reference": text("src/example.py", "Replace with repository path"),
                "language": text("python", "text"),
                "code": text("result = build()", "Replace with code excerpt."),
                "annotation": text(
                    "Repository evidence that informs the spec.",
                    "Replace with why this code matters.",
                ),
            }
        ]

    item = {field: _field_text(field, template) for field in spec.fields}
    if spec.label_prefix:
        item["id"] = f"{spec.label_prefix}-01"
    if block == "requirements":
        item["exception"] = text(
            "Validation target is selected when testing scope is known.",
            "Replace with validation exception or link this requirement to a TEST ID.",
        )
    return [item]


__all__ = ["example_block", "template_block"]
