# Spec manifest contract

`spec.yaml` is the authoring source, and generated `index.html` is the review surface.
The CLI `schema` command is authoritative for field shapes, supported blocks, and review-surface constraints.
This document holds the rules it does not print.

## Manifest version

`schema_version` must be `3`, the only accepted version.

- Version 3 requires the `design_tree` block.
- `template` emits version 3, and `validate`, `generate`, and `inspect` report it as `manifest_version`.

## Fields

- `slug`: lowercase kebab-case, published as `action-items/SPEC-<slug>/`.
- `metadata`: string labels, excluding the reserved `Initiative`, `Review surfaces`, and `Output` labels.
  The review page shows these labels under the title.

## Status lifecycle

`status` is free-form prose and the durable record of the review gate.
Downstream skills read it to decide whether a spec may be split into issues or agent tasks.

- Use a draft value such as `Draft for review` before review, and again whenever a revision or withdrawal reopens the decision.
- Use exactly `Accepted` once the user accepts.

Any other wording reads as unaccepted.

## Blocks

Select only decision-relevant blocks.
The generator keeps them in canonical order.

- Document: problem, goals, scope, requirements, decisions, risks, testing, and open questions.
- Workflow: journeys, transition matrix, business rules, and failure paths.
- API: contract, dependencies, security and privacy, failure paths, and observable testing outcomes.
- Data: model, privacy, migration, and validation.
- Architecture: decisions, dependencies, risks, and repository grounding.

## Identity and traceability

ID prefixes are `REQ-*`, `DEC-*`, `RISK-*`, `QUESTION-*`, `TEST-*`, and `NODE-*`.
Keep an ID while its entity's meaning stays stable, and connect entities through `relates_to`, `validation`, and `validates`.

## Design tree

The `design_tree` block records the interview as an ordered list of root nodes with optional `children`.
It stays in `spec.yaml`, and the review page does not show it.

- Write every node id explicitly, because a revision that inserts a branch must not renumber nodes an earlier review already read.
- A `settled` node carries `superseded_answer` when a revision replaced its answer.
- `source` is `user` for an interview answer and `research` for an agent finding.
- `source` is `request` for a decision that the original request states.
- A `request` node has no interview question, so its `question` phrases the decision as a question.
  Its `evidence` quotes the request word for word.
- Each `evidence` entry of a `research` node names a URL or a repository path, with an optional line or symbol.
  `validate` and `inspect` warn when an entry names no path or URL.
  They also warn when the path does not exist under the working directory.
- Tree nodes are never coverage gaps, because they record how the spec was reasoned out rather than a claim that needs validation.

## API contract details

An `api_contract` card can carry optional detail fields beside `contract` and `behavior`:

- `request`: the fields the consumer sends.
- `checks`: the checks in the order they run.
- `response`: the fields the consumer receives.
- `errors`: the error results.
- `idempotency`: what a repeated request does.
- `concurrency`: what parallel requests do.

Record a detail when a wrong value changes acceptance, and leave it out otherwise.

## Prose warnings

`validate` and `inspect` warn on each sentence over twenty words.
The check skips identifiers, references, evidence, and code.
It does not check other ASD-STE100 rules.

## Review page

`index.html` is a sign-off summary for a product reader.
It shows these blocks when the manifest selects them: problem, goals, non-goals, requirements, scope, risks, rollout, testing strategy, and open questions.
Every other block stays in `spec.yaml` for downstream skills.
A card links only to entities that the page shows.
`inspect` reports coverage gaps under `traceability.held`, because the page does not show them.

## Publication

The generator validates the manifest, renders canonical HTML, preserves normalized YAML as `spec.yaml`, copies versioned assets, validates the staged output, and publishes atomically.
It alone writes generated HTML from the working manifest.

The manifest is complete when it satisfies every rule above that its initiative type and selected blocks make applicable.
