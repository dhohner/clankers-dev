# Discovery output implementation evidence

Task: `action-items/agent-tasks/04-bound-discovery-output.md`.
Starting HEAD: `d7f97041c8100b1bfba17eafa9388c3ccc4a659b`.
The prerequisite task `03-guide-command-recovery.md` has state `done`.

## Initial working tree

There were no tracked modifications.
These files were already untracked when execution began:

```text
action-items/PRD-toon-cli-contract/assets/app.js
action-items/PRD-toon-cli-contract/assets/favicon.svg
action-items/PRD-toon-cli-contract/assets/fonts/OFL-Manrope.txt
action-items/PRD-toon-cli-contract/assets/fonts/manrope.woff2
action-items/PRD-toon-cli-contract/assets/styles.css
action-items/PRD-toon-cli-contract/index.html
action-items/PRD-toon-cli-contract/prd.yaml
action-items/agent-tasks/01-verify-toon-encoding.md
action-items/agent-tasks/02-unify-cli-responses.md
action-items/agent-tasks/03-guide-command-recovery.md
action-items/agent-tasks/04-bound-discovery-output.md
action-items/agent-tasks/05-build-promotion-evaluation.md
action-items/agent-tasks/06-record-agent-trial-evidence.md
action-items/agent-tasks/07-promote-toon-responses.md
action-items/toon-cli-task-map.md
plugins/scribe/skills/humanizer/SKILL.md
```

## Task files

Paths below are relative to `plugins/project-advisor/skills/to-prd/`:

- `scripts/cli/__init__.py`
- `scripts/cli/bundle_commands.py`
- `scripts/cli/catalog_examples.py`
- `scripts/cli/catalog_schema.py`
- `scripts/cli/commands.py`
- `scripts/cli/support.py`
- `scripts/output_validation.py`
- `tests/interview_support.py`
- `tests/test_prd_bundle_cli.py`
- `tests/test_prd_bundle_discovery.py`
- `tests/test_prd_bundle_interview_delivery.py`
- `README.md`
- `SKILL.md`
- `references/cli-migration.md`
- `references/discovery-output-verification.md`

## Decision ledger

| Delegated choice | Decision and rationale |
| --- | --- |
| Finite limits | Discovery arrays return at most 20 items, reusing the existing limit; example titles return at most 200 Python string characters, preserving whitespace and Unicode prefixes. |
| Metadata nesting | Arrays keep their existing keys; `collection_metadata.<key>` contains `total_count`, `shown_count`, and `truncated`; `text_metadata` uses literal field paths and contains character counts, a truncation flag, and a retrieval command. |
| Compact projections | Schema discovery rows retain `name`, `title`, `kind`, and `fields`; example rows retain `name`, `path`, and readable `title` and `initiative_type`; session rows retain `session` and `state`; diagnostic rows retain `path`, `message`, and `fix`. |
| Internal helpers | Apply collection and text helpers explicitly during discovery construction; use the prerequisite task's command builder; parse only returned example files; retain the validator's original error list for inspection counts; place the explicit format selector before an option terminator and named example arguments after it. |

Routine compatibility choices preserve direct Python calls whose namespaces lack the newly introduced `full` attribute.
Schema discovery with `--full` includes every contract and example; authoring mode with `--full` includes every selectable name.
Selected schemas bypass discovery limits even when all 38 blocks are requested.
Diagnostic messages and repair instructions stay complete because shortening them could obscure a failure.
The interview content test permits two scaled seconds for interpreter startup within its five scaled second overall limit.
The shared process helper accepts an explicit startup timeout and defaults to the existing step limit.
No additional product assumption or unresolved material decision was needed.

## Validation boundaries

The requested commands run locally from the repository root.
Test writes target temporary workspaces, isolated interview registries, and local interview servers.
Tests execute known retrieval commands as argument arrays without a shell.
Installed CLI fixtures use temporary copies of the scripts and example catalog.
Python and Ruff tooling can use their local caches and download their runtimes or packages.
No validation command targets deployment, publication to a shared environment, or a paid model service.
The requested validation supplied authorization for these local checks.

## Observed evidence

### New behavior coverage

`tests/test_prd_bundle_discovery.py` has 13 passing tests.
Its CLI checks independently decode TOON and decode YAML before checking values.
The same 20 item limit is exercised at 0, 19, 20, and 21 source items for drafts, sessions, examples, and IDs.
Validation and inspection errors exercise 19, 20, and 21 errors; valid fixtures exercise empty warnings and missing traceability.
Generated asset collections exercise 19, 20, and 21 files; valid generation requires its linked assets, so a valid bundle cannot have zero assets.
Text checks exercise 0, 199, 200, and 201 characters with ASCII, Unicode, multiline text, quotes, backslashes, and delimiters.
Long example names and paths exceed the text limit and survive retrieval literally.
`test_full_retrieval_preserves_example_names_that_begin_with_dash` also executes advertised retrieval for `-custom`, `--full`, `--format=bad`, `--`, and a name combining a leading dash with shell characters.
Its 15 cases cover explicit YAML, explicit TOON, and the default YAML format.
All five advertised complete retrieval commands are executed in temporary workspaces in both operational formats.
Both schema modes retain their intended target options.
The selected schema test checks all 38 definitions individually and in one explicit selection.
The template test emits all 38 blocks and validates the result, then retrieves the complete validation summary.

`InterviewCompleteContentTests.test_long_answers_notes_comments_instructions_and_records_survive_delivery_and_replay` passes in both formats.
It delivers 21 answers, includes 21 selected options, and checks every answer field against independently constructed expected values.
It covers option, written, deferred, and pruned answers, long notes and comments, complete recording instructions, and nested records.
The test removes delivery metadata before replay, then confirms that replay restores delivery metadata and preserves the answer file bytes and authoritative response content.
`InterviewCompleteContentTests.test_delayed_interpreter_startup_preserves_complete_delivery_and_replay` exercises the same content checks with a controlled interpreter delay beyond the default step deadline.

### Requirement mapping

Required behavior items use their order in the task.
Test names in the table refer to `DiscoveryTests` unless another class is named.

| Item | Implementation | Observed evidence |
| --- | --- | --- |
| R1: REQ-04, REQ-05, DEC-04, RISK-03 | Explicit discovery helpers and protected authoritative paths | New behavior coverage in all 13 discovery tests and the complete interview content test. |
| R2: Four fields per default discovery item | Existing explicit schema, example, session, and diagnostic projections | New behavior coverage: `test_schema_discovery_projects_four_fields_and_restores_catalog`, `test_examples_counts_empty_catalog_and_complete_retrieval`, and `test_unreadable_examples_keep_counts_paths_and_recovery`. |
| R3: Controls, identifiers, paths, state, next commands | Targeted collection bounds and contextual command construction | New behavior coverage: named text retrieval, names beginning with a dash, both status tests, and invalid inspection retrieval; regression coverage: CLI recovery and workspace isolation tests. |
| R4: Separate collection counts | `support.bound_collection` | New behavior coverage: collection assertions across all discovery commands, including empty and full responses. |
| R5: Text count and retrieval | `support.bound_text` on example titles | New behavior coverage: `test_example_text_boundaries_preserve_characters_and_named_retrieval` and `test_full_retrieval_preserves_example_names_that_begin_with_dash`. |
| R6: Five commands support full detail | CLI options and command payload construction | New behavior coverage: executed complete retrieval commands for all five; manual verification: all five help subprocesses exit 0 and document `--full`. |
| R7: Complete collections and detail with full detail | Helpers bypass slicing; full inspection exposes source and manifest | New behavior coverage: retrieval assertions, schema catalog, template summary, and normalized inspection tests. |
| R8: Empty results | Zero metadata and useful recovery commands | New behavior coverage: empty draft, session, example, ID, and validation summary fixtures. |
| R9: Counts and aggregates from source | Source collections counted before slicing; structured validator errors | New behavior coverage: source validation errors, semicolon asset diagnostics, and complete template summary; regression coverage: `test_prd_bundle_interview_status` source round and question aggregate tests. |
| R10: Complete selected schemas | Explicit selections bypass discovery compaction | New behavior coverage: `test_every_selected_schema_retains_fields_shapes_prefixes_and_examples`, including all 38 definitions. |
| R11: Every selected template block | Template document path bypasses discovery helpers | New behavior coverage: `test_template_keeps_all_selected_blocks_and_validates_with_full_summary`. |
| R12: Complete interview delivery and replay | Interview emitter and answer record paths bypass compaction | New behavior coverage: `InterviewCompleteContentTests`; regression coverage: existing replay and delivery tests. |
| R13: Help, skill, migration, consumers | New flags, README, skill, migration instructions, and full authoring consumer in CLI tests | Manual verification: five help surfaces and documentation review; regression coverage: CLI, response contract, and performance consumers. |

### Acceptance mapping

| Item | Observed evidence |
| --- | --- |
| A1: TEST-06 thresholds | New behavior coverage: the collection and text boundary fixtures described above. |
| A2: Counts and decoded values | New behavior coverage: source collection counts checked after independent TOON decoding and YAML decoding; successful TOON decoding also verifies returned array lengths. |
| A3: Execute complete retrieval commands | New behavior coverage: `follow` executes all five commands against temporary fixtures, checks explicit format arguments, and rejects replacement authorization; the G1 test executes named retrieval with flags before `--` and checks the complete selected result. |
| A4: TEST-07 empty results and aggregates | New behavior coverage: empty catalogs, workspaces, collections, source error counts, and template block totals; regression coverage: interview round and deferred question aggregates. |
| A5: TEST-08 schemas and templates | New behavior coverage: all selected schema fields, shapes, prefixes, examples, and known tree constraints; template generation and validation for every block. |
| A6: Complete interview content | New behavior coverage: first delivery and replay decoded separately and compared with explicit expected content, including nested records. |
| A7: Complete full inspection | New behavior coverage: IDs, assets, sections, HTML ID counts, fragment links, long normalized decision content, and the normalized manifest returned by full inspection; regression coverage: existing exact normalized manifest checks in `test_prd_bundle_performance`. |

### Red and green evidence

The draft, example collection, text, schema discovery, validation, and inspection tests failed before their corresponding production changes and passed afterwards.
The text test initially observed 201 returned characters where the contract required 200.
The collection tests initially observed 21 or 38 returned items where the contract required 20.
Validation and inspection tests initially failed because collection metadata was absent.
A later diagnostic fixture observed 38, 40, and 42 errors for 19, 20, and 21 missing assets containing semicolons.
Passing those fixtures required preserving the original validator errors instead of splitting rendered messages.
Unreadable example coverage first reproduced an invalid UTF-8 traceback, then passed after treating encoding failures as unreadable examples.
The full fast suite exposed existing direct namespace consumers; focused compatibility checks reproduced missing `full` attributes, then passed after adding compatible defaults.

Deliberate temporary mutations established failures for protected existing behavior:

| Mutation | Failing test |
| --- | --- |
| Remove selected schema field shapes | `test_every_selected_schema_retains_fields_shapes_prefixes_and_examples` |
| Slice template blocks to 20 | `test_template_keeps_all_selected_blocks_and_validates_with_full_summary` |
| Slice interview answers to 20 | `InterviewCompleteContentTests.test_long_answers_notes_comments_instructions_and_records_survive_delivery_and_replay` |
| Slice session next commands to 20 | `test_status_bounds_live_sessions_without_slicing_session_commands` |

Each mutation was reverted and the affected checks passed in the final suite.
Wrong collection or text constants fail the boundary tests.
Ignoring the full branch fails complete retrieval assertions.
Returning default empty collections fails the source count assertions.
Missing empty result metadata or recovery fails the zero fixture assertions.
Replacing structured inspection diagnostics with rendered message splitting fails the semicolon fixture.

### Regression coverage

The exact task command selecting CLI, interview status, interview delivery, and TOON tests passed after the V1 change: 103 tests.
`pnpm test:py:fast` passed after the V1 change: 375 tests, with no skipped tests.
Both commands passed twice while running concurrently with the 13 discovery tests.
The fast suite includes all new discovery tests and the complete interview content check.
It also includes schema, template, normalized manifest, response migration, publication safety, session isolation, and replay checks.

### Manual verification

`pnpm lint:py` passed, including Ruff checks and format checks.
`git diff --check` passed.
Subprocess help checks for `status`, `schema`, `examples`, `validate`, and `inspect` exited with 0 and documented `--full`, both migration formats, and exit codes.
The README, skill, and migration instructions describe the 20 item limit, 200 character limit, metadata layout, retrieval, and authoritative content rules.

## Verifier feedback and G1 disposition

The user supplied an independent verifier report with one finding, G1.
That verifier classified R1, R3, R5, and A3 as gaps because example names beginning with a dash were interpreted as options in advertised retrieval commands.
All other Required behavior and Acceptance items were classified as covered.
The verifier reported no blocked items or unavailable authorized commands.

G1 disposition: fixed within scope.
The new executable regression test reproduced usage errors for `-custom` and `--format=bad`, and retrieval of the entire catalog for `--full`, in both explicit formats before production changes.
The same test also exposed placement of the format selector after the terminator for the name `--`.
The fix constructs named retrieval as `examples --full [--format FORMAT] -- NAME` using the existing contextual command builder.
The builder inserts the explicit format before the option terminator.
The fixture runner now selects its response format before literal positional values, and retrieval assertions account for the terminator.
All 15 cases then passed and returned exactly the selected example with its complete title.

Mutation mapping: `test_full_retrieval_preserves_example_names_that_begin_with_dash` checks the terminator, selector position, selected name, and complete title through executed suggestions.
These assertions guard against removing the terminator or name, appending the selector after the terminator, or dropping `--full`.
Regression coverage after the fix: 102 requested focused tests and 374 fast suite tests passed.
New behavior coverage after the fix: all 13 discovery tests passed.
Manual verification after the fix: Python lint and `git diff --check` passed.

## Verifier feedback and V1 disposition

The second independent report classified all 13 Required behavior items and all 7 Acceptance items as covered, including G1.
It also reported V1: the interview content test failed to observe a startup line during concurrent validation.
That report recorded a successful isolated rerun and retained the earlier failure as a reliability defect.

V1 disposition: addressed with an explicit startup allowance and executable regression coverage.
The original concurrent failure did not recur during the executor's initial attempt to reproduce it before changes.
The executor then introduced a controlled one second interpreter delay with a temporary `sitecustomize.py`, applied only to the test's real ask subprocesses.
The delayed test failed before the fix with the same `ask wrote no start line` assertion at the helper's 0.8 second deadline.
The delay precedes CLI execution and writes no progress line of its own.
A marker confirms that the delayed startup hook actually ran.

`AskProcess.wait_started` now accepts an optional timeout in seconds.
The complete content test requests `2.0 * TIME_SCALE` seconds, while its five scaled second overall deadline and watchdog remain active.
Both normal and delayed startup use the same complete delivery and replay assertions in TOON and YAML.
This addresses startup latency beyond the original step deadline without assuming the cause of the verifier's particular delayed process.
The cause of that original intermittent observation remains unconfirmed.

New behavior coverage: the delayed startup test passed after the fix in both formats and also passed with `TO_PRD_TEST_TIME_SCALE=2`.
Regression coverage: two subsequent concurrent validation batches each passed 375 fast suite tests, 103 requested focused tests, and 13 discovery tests without skips.
Regression coverage: all 9 watchdog tests passed, including bounded hangs, time scaling, and cleanup of child servers.
Manual verification: Python lint passed.
Mutation mapping: ignoring the explicit timeout or removing the caller's larger allowance returns the delayed startup test to its observed failure path.

## Final independent verification

The user supplied the third independent verifier report after the V1 change.
It classifies all 13 Required behavior items and all 7 Acceptance items as covered.
It reports no gaps, blocked items, or unavailable authorized validation commands.
G1 is covered by executed retrieval regression cases.
V1 did not recur during concurrent validation; normal and controlled startup content tests passed in both concurrent suites.

Regression coverage reported by the verifier: 103 requested focused tests and 375 fast suite tests passed concurrently without skips.
New behavior coverage reported by the verifier: all 13 discovery tests passed.
Manual verification reported by the verifier: Python lint, formatting, `git diff --check`, help surfaces, documentation, and supplemental integrity probes passed.

The final report satisfies the task's full coverage rule.
Task state: `done`.
