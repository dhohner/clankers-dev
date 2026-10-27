# Evidence schema 1

All JSON files use UTF-8.
SHA-256 fingerprints are lowercase hexadecimal strings of length 64.
Source revisions are full Git commit identifiers of length 40.
Counts are integers greater than or equal to zero; booleans are invalid.
Unknown caller fields, including `promotion_eligible`, never override derived checks.

## Result input

`results.json` contains these fields:

| Field | Contract |
| --- | --- |
| `schema_version` | Integer `1` |
| `provenance` | `synthetic` or `observed` |
| `sources` | `baseline` and `candidate` source records |
| `contract_tests` | Candidate `source` fingerprint, exact `command`, and `outcome` (`success` or `failure`) |
| `tokenizer` | Exact `name`, package `version`, and immutable `model` version |
| `payloads` | One measurement for each of `schema`, `examples`, `validation`, `inspection`, `answers` |
| `trials` | Array of paired trial records |
| `conditions` | Array of `{kind, reason}` records; every supplied condition blocks eligibility |

A source record contains `base_revision`, `files`, and `fingerprint`.
`files` maps each relative source path to the SHA-256 of its bytes.
`fingerprint` is the SHA-256 of the UTF-8 JSON representation of `files`, with sorted keys, separators `,` and `:`, and `ensure_ascii=False`.
The baseline revision must be `236cd788400d3e8d63bb850b6aca6cf0f482cb2b`.
Candidate working files may differ from their base revision.
Keep the snapshots with the report so the manifests can be audited against bytes.

A payload measurement contains `family`, `provenance`, `complete`, `payload`, `yaml_tokens`, and `toon_tokens`.
`payload` fingerprints the canonical complete JSON value with the same canonicalization as source manifests.
Only `provenance: observed` and `complete: true` qualify.
`payloads.json` preserves the complete measured values.
Both encodings are constructed from each same complete value, without any response reduction.
Per-payload token increases are allowed.

A paired trial contains `case`, `repetition`, `baseline`, and `candidate`.
Cases are `discovery`, `authoring`, `repair`, `publication`, `inspection`, `retrieval`, and `interview`.
Repetitions start at one, are unique within each case, and have identical sets across cases, with at least three entries.
Each arm contains:

- `source`: its source fingerprint.
- `agent` and `model`: immutable version identities, identical throughout the experiment.
- `prompt`, `fixture`, and `permissions`: fingerprints, identical between arms and between repetitions of the same case.
- `outcome`: `success`, `failure`, or `timeout` for the task outcome.
- `input_tokens`, `output_tokens`, `total_tokens`, `tool_calls`, and `retries`: counts.

`total_tokens` must equal `input_tokens + output_tokens`.
Include all agent turns, tool result input, retries, and recovery in workflow totals.
Use provider usage accounting for workflow input and output tokens.
A completed attempt with a negative task outcome still has complete evidence when all measurements were collected.
An adapter failure that prevents collection is a `failed_run` condition and leaves the affected record partial.
Never invent zero measurements to fill a failed collection.

Condition kinds distinguish `missing_authorization`, `missing_dependency`, `failed_run`, `missing_evidence`, and `malformed_evidence`.
Reasons must contain only safe descriptions, without transport logs or secrets.
Missing measurements or repetitions remain absent in partial input files.
The report preserves supplied records and derives failed checks and incomplete status.

## Outputs

`report.json` contains `schema_version`, `provenance`, `completeness`, `evidence`, `conditions`, `totals`, `payload_changes`, `checks`, and `promotion_eligible`.
`provenance` and `completeness` are independent: synthetic evidence may be complete and observed evidence may be incomplete.
Missing provenance adds a `missing_evidence` condition; an invalid provenance value adds a `malformed_evidence` condition.
Both produce `completeness: incomplete` and `provenance: null` in the report, with the supplied input preserved in `evidence`.
Reports for structurally malformed input also use `provenance: null`.
`evidence` preserves input records for auditing.
Malformed input produces an incomplete report with a `malformed_evidence` condition.
`totals` sums input plus output tokens independently for both arms.
`payload_changes` records `toon_tokens - yaml_tokens` by family.
Every `checks` entry has a derived `passed` boolean and a `reason`.
The conditions check includes both supplied conditions and conditions generated during evidence validation.
Eligibility requires every check to pass: observed provenance, schema, source manifests, candidate contract tests, actual payload measurements, matched trials, retained baseline successes, strictly lower aggregate tokens, and no unresolved conditions.
A candidate failure or timeout paired with a baseline success fails the task check.
An equal or greater aggregate token total fails savings.
`report.md` presents the same decisions and totals for reading.
Report generation contains no timestamps or random identifiers, so replaying the same input reproduces the output bytes.

## Plan and measurement files

`plan.json` contains `schema_version`, source manifests, the complete `corpus`, `repetitions`, and `runs`.
Each run has its case, arm, repetition, prompt/fixture/permission fingerprints, mutable directory paths, transport path, execution source path, and operational selector.
Execution sources copy immutable snapshot bytes into separate directories with normal writable asset modes; this prevents generated bundles from inheriting read-only snapshot directory modes.
The adapter must enforce its source write restrictions and verify source bytes before and after each run.
The corpus contains the exact prompt strings, fixture content, and permission description.
The plan creates no agent or server.
`measurements.json` contains `tokenizer`, `payloads`, and `conditions`, ready to merge into a result input.
