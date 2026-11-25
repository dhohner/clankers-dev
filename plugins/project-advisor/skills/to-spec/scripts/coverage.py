"""Coverage gaps: tracked entities that still miss the connection their review needs."""

from __future__ import annotations

from typing import Any

from .manifest_types import NormalizedBlocks
from .spec import entity_blocks

RELATIONSHIP_FIELDS = ("relates_to", "validation", "validates")


def _entities(blocks: NormalizedBlocks) -> list[tuple[str, dict[str, Any]]]:
    """Return every entity that carries a stable ID with its block name, in catalog order."""
    return [(block_name, item) for block_name, _, items in entity_blocks(blocks) for item in items]


def connection_index(entities: list[tuple[str, dict[str, Any]]]) -> dict[str, set[str]]:
    """Map every entity ID to the IDs it references and the IDs referencing it."""
    connections: dict[str, set[str]] = {item["id"]: set() for _, item in entities}
    for _, item in entities:
        for field in RELATIONSHIP_FIELDS:
            for reference in item.get(field, []):
                connections[item["id"]].add(reference)
                if reference in connections:
                    connections[reference].add(item["id"])
    return connections


def coverage_gap(block: str, item: dict[str, Any], linked_blocks: set[str]) -> str | None:
    """Return the gap title for an entity, or None when it is covered."""
    if block == "requirements":
        if item.get("exception"):
            return "Validation deferred"
        if not {"decisions", "risks"} & linked_blocks:
            return "No decision or risk context"
        return None
    if "requirements" in linked_blocks:
        return None
    if block == "testing_strategy":
        return "Validates no requirement"
    return "Not connected to a requirement"


def coverage_gaps(blocks: NormalizedBlocks) -> list[tuple[str, str]]:
    """Return the label and gap title of each held entity, in catalog order."""
    entities = _entities(blocks)
    connections = connection_index(entities)
    block_by_id = {item["id"]: block for block, item in entities}
    gaps: list[tuple[str, str]] = []
    for block, item in entities:
        linked_blocks = {
            block_by_id[reference]
            for reference in connections[item["id"]]
            if reference in block_by_id
        }
        gap = coverage_gap(block, item, linked_blocks)
        if gap is not None:
            gaps.append((item["label"], gap))
    return gaps


__all__ = ["coverage_gaps"]
