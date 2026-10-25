# CLI response migration

Operational responses accept `--format toon` and `--format yaml` during migration.
This applies to `status`, `schema`, `examples`, `validate`, `generate`, `inspect`, and `interview ask|open|status|end`.
Interview responses default to TOON.
Other responses default to YAML.
Selectors can precede or follow the command, use `--format=value`, and repeat with the same value.
Conflicting selectors fail even when later selectors agree.

## Update consumers

Text responses are removed in this migration.
Replace `--format text` with `--format toon` or temporary `--format yaml` before upgrading a consumer.
JSON response selection is unsupported.
YAML compatibility remains available until promotion.
TOON becomes the operational default and sole response format only after passing contract tests, lower aggregate token counts, and controlled agent trials with no observed task regression against the YAML baseline.
Measurements must compare equivalent complete payloads before output reduction.
Trials must identify the agent, model, prompts, fixtures, permissions, repetitions, tokenizer, outcomes, tool calls, and retries.
At least one model must complete the trials.
Missing or failing evidence blocks promotion.
Maintainers must authorize trials that use configured credentials or incur external cost.
The immutable YAML baseline is `236cd788400d3e8d63bb850b6aca6cf0f482cb2b`.
This migration does not authorize promotion.

Decode each operational stdout as one response in the selected format.
Progress and diagnostics go to stderr.
Do not combine the streams before decoding.
No command asks for terminal answers.
Explicit `--help` prints reference text and exits with `0`.

Update exit handling:

- `0`: success, including interview disconnection and ended sessions.
- `1`: expected operation failure, including invalid input files, invalid documents, generation faults, and existing targets.
- `2`: usage failure, including unknown commands or flags, missing arguments, and malformed, unsupported, or conflicting selectors.

Non-interview operation failures previously used `2`, and generator runtime failures used `3`.
Consumers must now handle those failures as `1`.
A valid selector also encodes usage errors.
Without a selector, errors use the addressed command's default.
An unusable or conflicting selector produces TOON.
Failures contain `status: error`, a stable `code`, `errors` with `path`, `message`, and `fix`, and `next` commands.
Existing failure codes retain their meanings.
`usage_error` covers parser and selector rejection.
`manifest_unreadable` and `bundle_unreadable` also cover invalid UTF-8.
`session_io_error` covers interview filesystem failures during execution, including storage creation and lock access.
It identifies the session, includes repair guidance, and supplies a command to retry after correcting storage access.
`schema_authoring_with_blocks` remains a usage failure with its existing code.
An output root that is a file is `io_error`; `bundle_exists` identifies a bundle target conflict.

## Keep document parsing separate

Successful `template --blocks ...` always prints a complete YAML manifest without an operational envelope.
The existing `--format yaml` continues to select that document representation.
A TOON selector selects template failure encoding; successful template output remains YAML.
Template failures default to YAML during migration.
Published `prd.yaml`, YAML or JSON manifest inputs, YAML or JSON round inputs, private JSON session files, and HTTP JSON messages keep their document contracts.

Known consumers are the `to-prd` skill, its README, help, and Python tests.
Response tests use `tests/response_support.py` and the independent TOON decoder.
Document tests keep `load_yaml` for authored and published documents.
`to-agent-tasks` reads the accepted published `prd.yaml` as its source of truth.
`to-issues` also accepts PRD source documents.
Neither downstream skill decodes operational stdout, so their intake remains document based.

## Try the migration

Run these commands from the repository root with Python 3.14 or newer.
All writes target a disposable directory.
The interview example reads an empty scratch session and opens no browser.

```sh
CLI=plugins/project-advisor/skills/to-prd/scripts/__main__.py
scratch="$(mktemp -d)"
export TO_PRD_INTERVIEW_REGISTRY="$scratch/registry.json"
export TO_PRD_INTERVIEW_BROWSER_LOG="$scratch/browser.log"
mkdir "$scratch/session"
python3 "$CLI" --help
python3 "$CLI" schema requirements --format=toon
python3 "$CLI" --format yaml examples minimal-prd
python3 "$CLI" template --blocks requirements testing_strategy --format yaml > "$scratch/prd.yaml"
python3 "$CLI" validate "$scratch/prd.yaml" --format toon
python3 "$CLI" generate "$scratch/prd.yaml" --output-root "$scratch/bundles" --format toon
python3 "$CLI" inspect "$scratch/bundles/PRD-draft-prd" --format yaml
python3 "$CLI" --format=yaml interview status "$scratch/session"
```

Generation requires explicit `--force` to replace an existing target.
Inspect a refused target before authorizing replacement.
Failed staging or replacement preserves the previous valid bundle through the existing rollback boundary.
Concurrent bundle publishers have no additional guarantee.
Repeating reads creates no bundle or answer records.
An interview replay uses the session directory, round ID, and unchanged content, and returns stored answers.
Changed or competing rounds remain conflicts.
Repeated `interview end` succeeds after the server stops.
Session summaries remain `no_session`, `round_open`, `round_answered`, and `ended`.
Result statuses remain `answered`, `opened`, `browser_failed`, `browser_disconnected`, and `ended`.
