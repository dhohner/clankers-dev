"""Schema and rendering specifications for spec manifests."""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import cast

from .manifest_types import DesignTreeBlock, DesignTreeNode, NormalizedBlocks, TraceableEntity

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
TEMPLATE_MARKER_PATTERN = re.compile(r"\{\{[A-Z0-9_]+\}\}")
INITIATIVE_TYPES = {
    "workflow-heavy",
    "api-heavy",
    "data-heavy",
    "architecture-heavy",
    "mixed",
    "small-feature",
}
REVIEW_SURFACES = {
    "document",
    "workflow",
    "api",
    "data",
    "architecture",
}
REQUIRED_SURFACES_BY_INITIATIVE = {
    "small-feature": {"document"},
    "workflow-heavy": {"document", "workflow"},
    "api-heavy": {"document", "api"},
    "data-heavy": {"document", "data"},
    "architecture-heavy": {"document", "architecture"},
    "mixed": {"document"},
}
CURRENT_SCHEMA_VERSION = 3
SCHEMA_VERSIONS = (CURRENT_SCHEMA_VERSION,)
MANIFEST_FIELDS = {
    "schema_version",
    "slug",
    "title",
    "summary",
    "status",
    "initiative_type",
    "review_surfaces",
    "metadata",
    "blocks",
}
GENERATED_METADATA_LABELS = {"initiative", "review surfaces", "output"}


DESIGN_TREE_STATUSES = ("settled", "pruned", "deferred")
# `request` marks a decision the original request already states, so no interview question
# was asked and the evidence quotes the request instead.
DESIGN_TREE_SOURCES = ("user", "request", "research")
DESIGN_TREE_NODE_FIELDS = ("id", "label", "question", "status")
DESIGN_TREE_NODE_OPTIONAL_FIELDS = ("children", "relates_to", "evidence")
# Each status owns the fields that record why the branch ended the way it did,
# so a field that belongs to one status is an error on the others.
DESIGN_TREE_REQUIRED_FIELDS_BY_STATUS = {
    "settled": ("answer", "source", "rationale"),
    "pruned": ("reason",),
    "deferred": (),
}
DESIGN_TREE_EXTRA_FIELDS_BY_STATUS = {
    "settled": ("superseded_answer",),
    "pruned": (),
    "deferred": (),
}
DESIGN_TREE_STATUS_FIELDS = {
    field
    for status in DESIGN_TREE_STATUSES
    for field in DESIGN_TREE_REQUIRED_FIELDS_BY_STATUS[status]
    + DESIGN_TREE_EXTRA_FIELDS_BY_STATUS[status]
}


@dataclass(frozen=True)
class BlockSpec:
    title: str
    description: str
    category: str
    review_area: str
    kind: str
    fields: tuple[str, ...] = ()
    id_prefix: str | None = None
    label_prefix: str | None = None


BLOCK_SPECS: dict[str, BlockSpec] = {
    "executive_summary": BlockSpec(
        "Executive summary", "The proposed product change at a glance.", "framing", "all", "summary"
    ),
    "problem": BlockSpec(
        "Problem and evidence", "Why this outcome matters now.", "framing", "all", "problem"
    ),
    "goals": BlockSpec(
        "Goals and success measures",
        "Observable outcomes for the initiative.",
        "framing",
        "validation",
        "cards",
        ("goal", "success_signal"),
    ),
    "non_goals": BlockSpec(
        "Non-goals",
        "Outcomes this initiative intentionally does not pursue.",
        "framing",
        "decisions",
        "list",
    ),
    "personas": BlockSpec(
        "Personas and actors",
        "Who participates and what changes for them.",
        "people-workflow",
        "all",
        "cards",
        ("actor", "need", "outcome"),
    ),
    "user_stories": BlockSpec(
        "User stories",
        "User-centered behavior the product must enable.",
        "people-workflow",
        "validation",
        "cards",
        ("story", "acceptance"),
    ),
    "journeys": BlockSpec(
        "Current and future journey",
        "How the experience changes from today to the target state.",
        "people-workflow",
        "all",
        "cards",
        ("current", "future"),
    ),
    "state_transition_matrix": BlockSpec(
        "State-transition matrix",
        "Allowed states, triggers, and resulting behavior.",
        "people-workflow",
        "validation",
        "table",
    ),
    "failure_paths": BlockSpec(
        "Failure and fallback paths",
        "Expected behavior when the happy path cannot complete.",
        "people-workflow",
        "validation",
        "cards",
        ("scenario", "fallback"),
    ),
    "requirements": BlockSpec(
        "Requirements",
        "Behavior the delivered product must support.",
        "product-definition",
        "validation decisions",
        "cards",
        ("title", "description"),
        "req",
        "REQ",
    ),
    "capability_map": BlockSpec(
        "Capability map",
        "Product capabilities and the outcomes they enable.",
        "product-definition",
        "all",
        "cards",
        ("capability", "outcome"),
    ),
    "scope": BlockSpec(
        "Scope boundaries",
        "Explicit limits for implementation planning.",
        "product-definition",
        "decisions",
        "scope",
    ),
    "business_rules": BlockSpec(
        "Business rules",
        "Durable rules that constrain product behavior.",
        "product-definition",
        "validation decisions",
        "cards",
        ("rule", "rationale"),
    ),
    "decisions": BlockSpec(
        "Decision log",
        "Settled choices that shape delivery.",
        "product-definition",
        "decisions",
        "cards",
        ("decision", "rationale"),
        "dec",
        "DEC",
    ),
    "design_tree": BlockSpec(
        "Design tree",
        "The interview branches behind the settled decisions.",
        "product-definition",
        "decisions",
        "tree",
        id_prefix="node",
        label_prefix="NODE",
    ),
    "alternatives": BlockSpec(
        "Alternatives and tradeoffs",
        "Options considered and why they were not selected.",
        "product-definition",
        "decisions",
        "cards",
        ("option", "tradeoff"),
    ),
    "api_contract": BlockSpec(
        "API contract",
        "Interfaces and observable behavior consumers depend on.",
        "technical-contracts",
        "validation decisions",
        "cards",
        ("contract", "behavior"),
    ),
    "data_model": BlockSpec(
        "Data model",
        "Entities and relationships introduced or changed.",
        "technical-contracts",
        "validation decisions",
        "cards",
        ("entity", "definition"),
    ),
    "file_symbol_map": BlockSpec(
        "File and symbol map",
        "Repository locations expected to participate in delivery.",
        "technical-contracts",
        "all",
        "cards",
        ("reference", "role"),
    ),
    "annotated_code": BlockSpec(
        "Annotated code or diff",
        "Code evidence that clarifies a contract or constraint.",
        "technical-contracts",
        "all",
        "code",
    ),
    "dependencies": BlockSpec(
        "Dependencies",
        "External work or capabilities required for delivery.",
        "delivery-assurance",
        "decisions",
        "cards",
        ("dependency", "impact"),
    ),
    "risks": BlockSpec(
        "Risks and mitigations",
        "Known failure modes and responses.",
        "delivery-assurance",
        "decisions validation",
        "cards",
        ("risk", "mitigation"),
        "risk",
        "RISK",
    ),
    "security_privacy": BlockSpec(
        "Security and privacy",
        "Sensitive data, access, and abuse considerations.",
        "delivery-assurance",
        "validation decisions",
        "cards",
        ("concern", "response"),
    ),
    "rollout": BlockSpec(
        "Rollout and migration",
        "How the outcome reaches users safely.",
        "delivery-assurance",
        "validation",
        "cards",
        ("phase", "outcome"),
    ),
    "testing_strategy": BlockSpec(
        "Testing strategy",
        "Observable proof that the requirements work.",
        "delivery-assurance",
        "validation",
        "cards",
        ("target", "expected_outcome"),
        "test",
        "TEST",
    ),
    "traceability_matrix": BlockSpec(
        "Traceability matrix",
        "Relationships between product intent and verification.",
        "delivery-assurance",
        "validation decisions",
        "table",
    ),
    "open_questions": BlockSpec(
        "Open questions",
        "Decisions that still need explicit confirmation.",
        "delivery-assurance",
        "decisions",
        "questions",
        id_prefix="question",
        label_prefix="QUESTION",
    ),
    "repository_grounding": BlockSpec(
        "Repository grounding",
        "Evidence that informed the product shape.",
        "delivery-assurance",
        "all",
        "cards",
        ("reference", "observation", "implication"),
    ),
}

ENTITY_OPTIONAL_FIELDS_BY_BLOCK = {
    "requirements": {"id", "relates_to", "validation", "evidence", "exception"},
    "decisions": {"id", "relates_to", "evidence"},
    "risks": {"id", "relates_to", "evidence"},
    "testing_strategy": {"id", "relates_to", "validates", "evidence"},
}

# The blocks `index.html` shows: a sign-off summary for a product reader. Every block stays
# in `spec.yaml` for downstream skills, and the page leaves out the rest.
REVIEW_PAGE_BLOCKS = frozenset(
    {
        "problem",
        "goals",
        "non_goals",
        "requirements",
        "scope",
        "risks",
        "rollout",
        "testing_strategy",
        "open_questions",
    }
)

# Optional detail fields of a card block that carries no ids, mapped to their shape: `text`
# for one string, `list` for strings in any order, and `steps` for strings in a fixed order.
CARD_DETAIL_FIELDS_BY_BLOCK: dict[str, dict[str, str]] = {
    "api_contract": {
        "request": "text",
        "checks": "steps",
        "response": "text",
        "errors": "list",
        "idempotency": "text",
        "concurrency": "text",
    },
}

ENTITY_ID_PATTERN = re.compile(r"^(req|dec|risk|question|test|node)-[a-z0-9][a-z0-9-]*$")


def normalize_entity_id(value: str) -> str:
    return value.strip().lower()


def entity_label(entity_id: str) -> str:
    prefix, _, suffix = entity_id.partition("-")
    return f"{prefix.upper()}-{suffix.upper()}"


def entity_blocks(
    blocks: NormalizedBlocks,
) -> Iterator[tuple[str, BlockSpec, list[TraceableEntity]]]:
    """Yield each selected block whose items are traceable entities, in catalog order.

    Design tree nodes carry ids too, but they come from ``tree_blocks`` because
    they record interview history rather than tracked claims.
    """
    for name, items in blocks.items():
        spec = BLOCK_SPECS[name]
        if spec.id_prefix and spec.kind != "tree":
            # Every item type of an id-prefixed block extends TraceableEntity.
            yield name, spec, cast("list[TraceableEntity]", items)


def review_page_entity_ids(blocks: NormalizedBlocks) -> list[str]:
    """Return the ids of the entities the review page shows, in catalog order."""
    return [
        item["id"]
        for name, _, items in entity_blocks(blocks)
        if name in REVIEW_PAGE_BLOCKS
        for item in items
    ]


def tree_blocks(blocks: NormalizedBlocks) -> Iterator[tuple[str, BlockSpec, DesignTreeBlock]]:
    """Yield each selected design tree block."""
    for name, items in blocks.items():
        spec = BLOCK_SPECS[name]
        if spec.kind == "tree":
            yield name, spec, cast("DesignTreeBlock", items)


def iter_tree_nodes(nodes: Sequence[DesignTreeNode]) -> Iterator[DesignTreeNode]:
    """Yield every design tree node in document order, parents before children.

    The walk is iterative because tree depth comes from author input, and a
    recursive walk would raise RecursionError instead of a manifest error.
    """
    stack = list(reversed(nodes))
    while stack:
        node = stack.pop()
        yield node
        stack.extend(reversed(node.get("children", [])))


__all__ = [
    "BLOCK_SPECS",
    "CARD_DETAIL_FIELDS_BY_BLOCK",
    "CURRENT_SCHEMA_VERSION",
    "DESIGN_TREE_EXTRA_FIELDS_BY_STATUS",
    "DESIGN_TREE_NODE_FIELDS",
    "DESIGN_TREE_NODE_OPTIONAL_FIELDS",
    "DESIGN_TREE_REQUIRED_FIELDS_BY_STATUS",
    "DESIGN_TREE_SOURCES",
    "DESIGN_TREE_STATUSES",
    "DESIGN_TREE_STATUS_FIELDS",
    "ENTITY_ID_PATTERN",
    "ENTITY_OPTIONAL_FIELDS_BY_BLOCK",
    "GENERATED_METADATA_LABELS",
    "INITIATIVE_TYPES",
    "MANIFEST_FIELDS",
    "REQUIRED_SURFACES_BY_INITIATIVE",
    "REVIEW_PAGE_BLOCKS",
    "REVIEW_SURFACES",
    "SCHEMA_VERSIONS",
    "SLUG_PATTERN",
    "TEMPLATE_MARKER_PATTERN",
    "BlockSpec",
    "entity_blocks",
    "entity_label",
    "iter_tree_nodes",
    "normalize_entity_id",
    "review_page_entity_ids",
    "tree_blocks",
]
