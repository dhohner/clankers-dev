"""Typed manifest models shared across generator modules.

These types describe the normalized manifest contract returned by validation and
consumed by rendering and bundle publication. They give future schema versions a
stable place to evolve without forcing every module boundary back to
``dict[str, Any]``.
"""

from __future__ import annotations

from typing import Required, TypedDict


class MetricItem(TypedDict):
    label: str
    value: str
    description: str


class SummaryBlock(TypedDict):
    metrics: list[MetricItem]
    recommendation: str


class ProblemBlock(TypedDict):
    statement: str
    evidence: list[str]


ScopeBlock = TypedDict("ScopeBlock", {"in": list[str], "out": list[str]})


class TableBlock(TypedDict):
    columns: list[str]
    rows: list[list[str]]


class CodeSample(TypedDict):
    reference: str
    language: str
    code: str
    annotation: str


class TraceableEntity(TypedDict, total=False):
    """An item that validation assigns a stable id, label, and reference lists."""

    id: Required[str]
    label: Required[str]
    relates_to: Required[list[str]]
    evidence: Required[list[str]]


class RequirementItem(TraceableEntity, total=False):
    title: str
    description: str
    validation: Required[list[str]]
    exception: str


class DecisionItem(TraceableEntity, total=False):
    decision: str
    rationale: str


class RiskItem(TraceableEntity, total=False):
    risk: str
    mitigation: str


class TestingStrategyItem(TraceableEntity, total=False):
    target: str
    expected_outcome: str
    validates: list[str]


class OpenQuestionItem(TraceableEntity, total=False):
    question: str


class DesignTreeNode(TypedDict, total=False):
    """One interview question and the branches below it.

    ``status`` selects the fields that must accompany it: ``settled`` carries
    ``answer``, ``source``, and ``rationale``; ``pruned`` carries ``reason``;
    ``deferred`` names an open question through ``relates_to``.
    """

    id: Required[str]
    label: Required[str]
    question: Required[str]
    status: Required[str]
    answer: str
    source: str
    rationale: str
    superseded_answer: str
    reason: str
    relates_to: list[str]
    evidence: list[str]
    children: list[DesignTreeNode]


# Card fields are strings, except the list-shaped detail fields of CARD_DETAIL_FIELDS_BY_BLOCK.
type CardItem = dict[str, str | list[str]]
type CardBlock = list[CardItem]
type StringBlock = list[str]
type RequirementsBlock = list[RequirementItem]
type DecisionsBlock = list[DecisionItem]
type RisksBlock = list[RiskItem]
type TestingStrategyBlock = list[TestingStrategyItem]
type OpenQuestionsBlock = list[OpenQuestionItem]
type DesignTreeBlock = list[DesignTreeNode]
type AnnotatedCodeBlock = list[CodeSample]

type NormalizedBlock = (
    SummaryBlock
    | ProblemBlock
    | ScopeBlock
    | TableBlock
    | CardBlock
    | StringBlock
    | RequirementsBlock
    | DecisionsBlock
    | RisksBlock
    | TestingStrategyBlock
    | OpenQuestionsBlock
    | AnnotatedCodeBlock
    | DesignTreeBlock
)


class NormalizedBlocks(TypedDict, total=False):
    executive_summary: SummaryBlock
    problem: ProblemBlock
    goals: CardBlock
    non_goals: StringBlock
    personas: CardBlock
    user_stories: CardBlock
    journeys: CardBlock
    state_transition_matrix: TableBlock
    failure_paths: CardBlock
    requirements: RequirementsBlock
    capability_map: CardBlock
    scope: ScopeBlock
    business_rules: CardBlock
    decisions: DecisionsBlock
    design_tree: DesignTreeBlock
    alternatives: CardBlock
    api_contract: CardBlock
    data_model: CardBlock
    file_symbol_map: CardBlock
    annotated_code: AnnotatedCodeBlock
    dependencies: CardBlock
    risks: RisksBlock
    security_privacy: CardBlock
    rollout: CardBlock
    testing_strategy: TestingStrategyBlock
    traceability_matrix: TableBlock
    open_questions: OpenQuestionsBlock
    repository_grounding: CardBlock


class NormalizedManifest(TypedDict):
    schema_version: int
    slug: str
    title: str
    summary: str
    status: str
    initiative_type: str
    review_surfaces: list[str]
    metadata: dict[str, str]
    blocks: NormalizedBlocks


__all__ = [
    "AnnotatedCodeBlock",
    "CardBlock",
    "CardItem",
    "CodeSample",
    "DecisionItem",
    "DecisionsBlock",
    "DesignTreeBlock",
    "DesignTreeNode",
    "MetricItem",
    "NormalizedBlock",
    "NormalizedBlocks",
    "NormalizedManifest",
    "OpenQuestionItem",
    "OpenQuestionsBlock",
    "ProblemBlock",
    "RequirementItem",
    "RequirementsBlock",
    "RiskItem",
    "RisksBlock",
    "ScopeBlock",
    "StringBlock",
    "SummaryBlock",
    "TableBlock",
    "TestingStrategyBlock",
    "TestingStrategyItem",
    "TraceableEntity",
]
