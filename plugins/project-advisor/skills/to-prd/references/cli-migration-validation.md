# Migration validation record

Task: `action-items/agent-tasks/02-unify-cli-responses.md`.
Starting HEAD: `35616d4abe8e79f05c348cf0fe2c9878ec0bc51a`.
The encoder prerequisite is marked done.
The baseline commit `236cd788400d3e8d63bb850b6aca6cf0f482cb2b` remains accessible through Git.

## Starting working tree

There were no tracked modifications.
All pre-existing changes were these untracked files:

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

## Decision ledger

| Executor choice | Decision and rationale |
| --- | --- |
| Common response abstractions | `cli/response.py` owns response emission, the argument parser, and usage failures; interview handlers return payloads to the common dispatcher |
| Parser organization | Extract exact format selectors before parsing and execution; inspect every selector, disable option abbreviation, and honor the positional `--` separator |
| Test decoder placement | `tests/response_support.py` decodes responses by explicit format through the independent TOON oracle or the existing YAML reader; document parsing keeps `load_yaml` |
| Stable failure codes | Retain existing category codes; use `usage_error` for selectors and parser failures, existing unreadable codes for UTF-8 faults, and `io_error` for an unusable output root; keep `schema_authoring_with_blocks` at exit 2 |

Successful templates remain YAML even when a TOON selector selects their failure encoding, as required by the complete YAML authoring boundary.
Unknown blocks and examples are operation failures with their existing codes.
Existing documented defaults remain YAML for non-interview responses and TOON for interview responses.
The asset export test used an implicit argparse abbreviation, `--output`; it now uses the documented `--output-root` after strict flag rejection exposed it.
No task behavior is excluded by a blocker.

## Coverage map

The response module is `tests/test_prd_bundle_response_contract.py`.
The interview response module is `tests/test_prd_bundle_interview_responses.py`.

| Task item | Implementation | Observed evidence |
| --- | --- | --- |
| Required behavior 1: migration requirements, retry, publication, portability, consumers | Shared dispatcher, parser, failure constructors, migration reference, skill and README | New response module and interview response module; focused lifecycle and security suites |
| Required behavior 2: RISK-01 and RISK-07 | Migration notice documents text removal, temporary YAML, promotion gate, and exits | Help subprocess checks; operation failure matrix; manual documentation checks recorded below |
| Required behavior 3: every operational command | Common response dispatch and interview payload handlers | Both new modules run every command in real subprocesses |
| Required behavior 4: selectors | Full selector scan with exact flag matching and conflicts | Usage matrix, selector placement and repeated equality, FIFO side effect checks |
| Required behavior 5: defaults | Dispatcher selects command default | Default response checks and existing CLI/interview suites |
| Required behavior 6: streams | One complete encoded payload after execution; existing stderr progress | Subprocess command matrices, interview ask stderr assertions |
| Required behavior 7: migration instructions | `cli-migration.md`, README, skill, help | Help matrix and manual migration examples |
| Required behavior 8: consumers and documents | Explicit response decoder and preserved document loader | Redirected templates; schema versions and YAML/JSON input matrix; accepted published source |
| Required behavior 9: Python and standard library | Runtime imports remain standard library only | Python 3.14 isolated tests and subprocesses with `-S` |
| TEST-01 | Operational format dispatch | Operational and interview subprocess matrices; default checks |
| TEST-02 and TEST-04 | Pre-dispatch usage rejection | Usage matrix; FIFO source proves no source reads; isolated empty registry, browser log, session, output root |
| TEST-03 | YAML template and input preservation | Redirected templates; YAML/JSON versions 1 and 2 generate and inspect; YAML/JSON interview rounds; accepted source checks |
| TEST-05 | Exit 1, stable failure categories, repair guidance | Missing files, directory reads, invalid UTF-8, malformed YAML, manifest and bundle faults, output root file, injected generator faults, target refusal |
| TEST-11 | Existing interview identity, state, storage, delivery, locks | Subprocess replay, byte-stable answers, duplicate submission rejection, changed and competing rounds, disconnection/recovery, repeated end; existing delivery/reopen/submit/security suites |
| TEST-12 | Existing publication transaction | Injected staging write and replacement rename failures compare all prior bundle bytes, inspect restoration, check cleanup, refuse target and replace with force; existing backup and symlink cases |
| TEST-14 and migration TEST-15 | Portable runtime and migration guidance | `-S` subprocesses; help matrix; isolated Python suite; migration examples and consumer audit |

## Red and green observations

| Check | Red evidence | Green evidence |
| --- | --- | --- |
| Operational formats | Six TOON command cases exited 2 under the earlier parser | Both formats pass for six commands |
| Usage encoding and selectors | Earlier contract hid repeated conflicts, accepted abbreviations, or emitted empty stdout/plain usage | All selector and usage cases pass |
| Operation failures | Earlier failures exited 2; invalid UTF-8 produced tracebacks; repair fields were missing | Both formats pass the failure matrix with exit 1 and guidance |
| Template document boundary | TOON selection initially encoded a successful template as TOON | All redirected templates validate as YAML |
| Help | Thirteen help surfaces omitted format or exit guidance | All help surfaces pass |
| Schema authoring conflict | Initially exited 1 without next commands | Retains its code, exits 2, and supplies repair commands |
| Positional separator | Appending the extracted selector after `--` produced usage failure | The literal filename reaches manifest loading and reports file_not_found |

Checks that initially passed exercise preserved behavior and are subject to mutation probes recorded below.
No test discovery or fixture failure is counted as red behavior evidence.

## Validation boundaries

All task validation commands target the local checkout and disposable filesystem roots.
The Python harness uses isolated registries and browser logs and starts only loopback interview servers.
The fast suite, focused suite, Ruff check, and Ruff format check make no shared or remote state changes.
`uv` and `uvx` may fetch development tooling and Python through their normal caches.
Manual migration commands use temporary output roots and session directories.
Authentication tokens and browser links are excluded from saved reports.
Independent verifiers may read files and run these safe commands, with no edits, commits, deployments, uploads, or shared state mutations.

## Validation results

Regression coverage: the focused task command plus the two new response modules passed 137 tests in verifier pass 1.
Regression coverage: `pnpm test:py:fast` passed 343 tests after updating the asset export consumer to its documented flag.
Manual verification: verifier pass 1 ran `pnpm lint:py` successfully, including Ruff check and format check.
Final regression coverage: the exact task-focused command passed 124 tests.
Final regression coverage: `pnpm test:py:fast` passed 344 tests, including all 14 tests in the new response modules.
New-behavior coverage: both response modules pass, with original-contract failures and mutation evidence recorded above.
Manual verification: final `pnpm lint:py` passed all Ruff checks and formatting checks for 83 Python files.
Manual verification: `git diff --check` passed.

### Manual verification

Every shell example in `cli-migration.md` ran successfully under Python 3.14 with `bash -e` and temporary roots.
The help, selected schema, examples, redirected template, validation, generation, inspection, and interview status commands all exited 0.
The empty session reported `no_session` without browser or server creation.
The published accepted source checks exercise the document intake contract for downstream skills.
Those skills are agent instructions with no executable intake harness; the manual consumer audit confirms that they read `prd.yaml`, and no downstream agent workflow was launched.

A disposable Chrome context, driven by Playwright through temporary development tooling, exercised the explicit interview browser action.
A written answer and note survived reload, page disconnection, a successful `browser_disconnected` result, and `interview open` recovery.
Submission after recovery returned `answered` and retained both strings in exactly one JSON answer file.
The browser, server, session files, registry, and browser log were cleaned up.
No authentication values were saved in this record.

### Mutation evidence

Fourteen mutations ran in a temporary copy of the skill, preserving the checkout.
Each mutation caused the named test to fail, and the restored implementation passed its checks.
These supply red evidence for preserved behavior that initially passed and confirm the new assertions detect realistic breaks.

| Mutation | Failing test |
| --- | --- |
| Remove selector conflict validation | `test_usage_errors_follow_selector_precedence` |
| Remove equals selector extraction | `test_valid_selectors_and_yaml_defaults` |
| Change the non-interview default to TOON | `test_valid_selectors_and_yaml_defaults` |
| Suppress parser usage rejection | `test_invalid_usage_has_no_source_browser_server_or_publication_effects` |
| Restore operation failure exit 2 | `test_operation_failures_have_exit_one_and_repair_guidance` |
| Emit an empty response | `test_operational_commands_emit_selected_format_in_subprocesses` |
| Encode successful templates as responses | `test_redirected_template_remains_a_yaml_manifest` |
| Restore generator runtime failure exit 3 | `test_generation_failures_restore_previous_bundle_and_exit_one` |
| Remove rollback restoration | `test_generation_failures_restore_previous_bundle_and_exit_one` |
| Reject JSON manifest inputs | `test_versions_and_input_documents_remain_portable` |
| Ignore interview YAML selection | `test_every_interview_command_uses_both_formats_and_preserves_replay` |
| Route disconnected results to ended | `test_disconnected_round_recovers_in_both_formats` |
| Stop catching invalid round encoding | `test_unreadable_rounds_emit_repair_guidance_in_both_formats` |
| Remove fallback repair guidance | `test_operation_failures_have_exit_one_and_repair_guidance` |

### Independent verification

Pass 1 used a fresh verifier with the canonical prompt and read/bash tools.
It found no implementation gaps and classified every Required behavior and Acceptance item as covered.
It observed 137 focused tests, 343 fast tests, and successful Ruff validation.
It requested completion of the then-pending manual and mutation evidence and correction of the focused test count.
Those evidence entries are now recorded above.
No gaps were rejected.
No behavior is blocked.
Pass 2 used another fresh verifier with the canonical prompt, completed evidence, and the same validation boundaries.
It classified every Required behavior and Acceptance item as covered and reported no gaps or blockers.
It observed 124 tests from the exact task command, 138 with both response modules, 344 from the fast suite, and successful Ruff checks for 83 files.
It assessed the recorded manual browser, migration example, mutation, and downstream intake evidence.
All probed states had recorded methods and results.
There are no unresolved gaps, rejected gaps, blocked task items, or untested task items.
The task qualifies for `state: done`.

## Review follow-up: interview filesystem failures

The review identified a session permission failure that the first two verification passes missed.
A valid `interview ask` reached `session_lock()` and raised `PermissionError` while creating the interview directory.
Both formats exited 1 with empty stdout and a traceback before the fix.
The same failure occurred when an existing session lock denied access for ask, open, status, and end.

Decision: catch execution-time `OSError` in `cli/interview.py::run`, after argument parsing, and raise `InterviewFailure` from the original error.
Use the new stable code `session_io_error` because the existing `session_unreadable` code describes path resolution failures.
The response identifies the command and session, gives storage repair guidance, and includes a retry command with the known session and round paths.
The common dispatcher emits the failure in the selected response format with exit 1.
This closes the reported gap in REQ-03 and TEST-05.

New-behavior coverage: `test_session_permission_failures_preserve_data_and_emit_both_formats` reproduced ten empty-stdout failures before the fix and passes afterward.
Its twelve subprocess cases cover denied directory creation, a conflicting storage file, and denied lock access for all four interview commands in TOON and YAML.
They verify all failure fields, empty stderr, unchanged existing manifest/round/answer/state bytes, and no browser log, server files, or registry creation.
The real permission checks ran as user 501; the test explicitly skips root because root bypasses the permissions under test.
Mutation coverage: narrowing the handler to `PermissionError` caused both conflicting-directory cases to fail with empty stdout; restoring `OSError` passed.
Regression coverage: the focused task suites plus interview responses passed 128 tests.
Regression coverage: `pnpm test:py:fast` passed 345 tests.
Manual verification: `pnpm lint:py` passed Ruff checks and formatting checks for 83 Python files.
Manual verification: `git diff --check` passed.
Independent follow-up verification found no gaps or blockers and classified every Required behavior and Acceptance item as covered.
It reran all twelve subprocess cases without skips, the exact task command with 124 tests, the focused set with 128 tests, the fast suite with 345 tests, Ruff checks, and `git diff --check`.
It confirmed that lock unwinding precedes error conversion and that parsing and existing specific failure categories retain their behavior.
