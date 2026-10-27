# Task 05 implementation evidence

## Task and starting state

Task: `action-items/agent-tasks/05-build-promotion-evaluation.md`.
Starting HEAD: `02ebe833b278ba5889cbc4326520887e3cc92817`.
The initial working tree had only these untracked files:

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

Task files created:

- `plugins/project-advisor/skills/to-prd/evals/toon-cli/evaluate.py`
- `plugins/project-advisor/skills/to-prd/evals/toon-cli/README.md`
- `plugins/project-advisor/skills/to-prd/evals/toon-cli/SCHEMA.md`
- `plugins/project-advisor/skills/to-prd/evals/toon-cli/requirements.txt`
- `plugins/project-advisor/skills/to-prd/evals/toon-cli/VALIDATION.md`
- `plugins/project-advisor/skills/to-prd/tests/test_prd_bundle_promotion_eval.py`

## Observed validation

### New-behavior coverage

The maintainer's final independent review reports all 28 focused tests passing in the tokenizer environment.
The ordinary environment passes 27 of these and explicitly skips the integration test because tokenizer dependencies are absent.
The tests exercise derived gates, malformed evidence, exact integer counts, source manifests, repeat comparability, corpus completeness, token adapters, isolated plans, transports, snapshot permissions, execution copies, and complete interview replay followed by cleanup.
Development proceeded through observed failures and passing reruns at these seams.
Failures included absent tooling, admitted incomplete evidence, missing corpus families, missing runs and source files, absent report files, invalid interview fixtures, incorrect transport selection, missing seeded answers/state, corrupt tokenizer cache acceptance, boolean schema acceptance, changing prompts between repetitions, malformed condition crashes, machine dependent command identities, and writable snapshot directories.
All 28 focused tests passed in the final independent review after the source isolation fix described below.

A deliberate mutation changed the aggregate savings comparison from `<` to `<=`.
`test_token_tie_and_increase_fail_savings_even_with_valid_arithmetic` failed on the tie.
The mutation was reverted, and the original 18 tests passed again.
Other mutation protections are named below:

| Mutation | Test that catches it |
| --- | --- |
| Wrong totals or an empty report | `test_gate_derives_savings_but_synthetic_cannot_promote` |
| Synthetic evidence admitted | `test_gate_derives_savings_but_synthetic_cannot_promote` |
| Lost success, timeout, malformed counts, mismatched identity, missing tests, or missing repetitions admitted | `test_gate_rejects_each_invalid_or_incomplete_evidence_state` |
| Repetition inputs change together in both arms | `test_repetitions_cannot_change_prompts_or_permissions_together` |
| Report files omitted | `test_script_entrypoint_creates_selected_evidence_directory` |
| Interview answer or active state persistence omitted | `test_seeded_interview_replays_without_requesting_user_decisions` |
| Candidate selector omitted or applied to templates | `test_transport_selects_candidate_toon_and_keeps_templates_yaml` |
| Missing tokenizer replaced with estimates | `test_complete_payloads_are_encoded_before_token_adapter_counts` |
| Corrupt cache allowed to reach tokenizer loading | `test_corrupt_tokenizer_cache_never_attempts_network_repair` |
| Snapshot protection removed | `test_snapshots_hash_exact_files_without_changing_the_worktree` |
| Snapshot modes leaked into execution copies | `test_execution_copy_restores_writable_asset_modes_without_changing_source_bytes` |

### Regression coverage

The final independent review reports `pnpm test:py:fast` ran 403 tests: 402 passed and the optional real tokenizer integration test was skipped.
That integration test passed separately in the evaluation environment, where all 28 focused tests ran without skips.
The remaining 375 tests cover existing operational behavior.
The final `pnpm lint:py` run passed checks and formatting for all 90 Python files.
The ordinary test run used its existing isolated Python environment without benchmark dependencies.

### Manual verification

Disposable evidence root:
`/var/folders/gj/r365px1x66s54wjzw6b70bgm0000gn/T/toon-evidence.uhvFPd/`.
These artifacts are local development evidence.

- Executed the README's synthetic report and replay commands; `cmp` confirmed identical report bytes.
- Executed offline measurement without tokenizer dependencies; `measurements.json` reported `missing_dependency`, installation instructions, and no fabricated counts.
- Executed plan generation with three repetitions; the plan produced 42 independent arms and immutable reference snapshots.
- Verified all 42 execution sources against every source manifest file digest.
- Replayed all six baseline/candidate interview arms, confirmed the final fixture answer, and successfully ended every session without a server or registry being created.
- Ran the candidate response contract suite against a separate execution copy: 11 tests passed.
- Ran the candidate discovery suite against that copy: 13 tests passed.
- Installed `tiktoken==0.12.0` in a disposable evaluation environment, prefetched its public vocabulary separately, and measured the frozen candidate with model identity `gpt-4o-2024-08-06`.
- Reviewed the documented external adapter command, provider authorization, budget requirements, source restrictions, evidence filtering, and server cleanup procedure without executing a configured adapter.
- Checked the process list after validation; no Python interview server remained.

The initial frozen measurement is in `verified-measured/measurements.json` under the evidence root above.
The current normalized measurement is in `/var/folders/gj/r365px1x66s54wjzw6b70bgm0000gn/T/toon-source-final.680rfL/comparison.json`.
It records tokenizer version `0.12.0` and vocabulary SHA-256 `446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d`.
Observed raw counts below match across working source, a reference snapshot, and an execution copy, from both repository and skill working directories:

| Complete payload | YAML tokens | TOON tokens |
| --- | ---: | ---: |
| Schema | 5,640 | 5,433 |
| Example list | 692 | 553 |
| Validation failure | 371 | 275 |
| Inspection | 905 | 770 |
| Interview answers | 2,262 | 2,257 |

Initial manual checks exposed two tooling defects that were reproduced and fixed before the final checks above.
Read-only snapshot directory modes propagated through bundle asset copies and broke replacement; isolated execution copies now restore writable asset modes while retaining identical file bytes.
Seeded interview answers without session state replayed but could not end; seeding now records a recoverable active state without a server or credentials.
The initial test that exposed missing answer seeding started a local server; its lock path identified the owned process, which was terminated and confirmed absent afterward.

## Required behavior mapping

The numbers follow the task's Required behavior bullet order.

| Item | Implementation | Observed evidence |
| --- | --- | --- |
| R1: REQ-12, TEST-16/17, DEC-06, RISK-04/06 tooling | `build_report`, corpus, measurements, and controlled procedure | Synthetic gate boundaries; actual tokenizer counts; reviewed authorization procedure |
| R2: documented tooling directory | README, schema, requirements, tool | Executed commands; documented source enumeration and verified path normalization |
| R3: equivalent complete payloads | `payload_corpus`, `measure` | Complete family/answer tests and actual counts for all five families |
| R4: actual tokenizer and exact version | `local_tokenizer`, cache selection | Actual tiktoken 0.12.0 measurements; six cache states exercised with network access intercepted |
| R5: seven workflow cases | `workflow_corpus`, `make_plan` | 42-run plan test and manual plan generation |
| R6: three matched repetitions | `make_plan`, paired trial validation, transport | Repetition/input checks and baseline/candidate argument terminator probes |
| R7: outcomes, usage, calls, retries, immutable identifiers | Schema, snapshots, imported trial records | Staged additions, renames, Unicode and quoted filenames captured from working bytes; source, usage, outcome, identity, and aggregate tests |
| R8: deterministic gate tests | Discovered unittest module | Final independent review: all 28 focused tests passed with optional dependencies; 27 passed in the ordinary environment |
| R9: dependency isolation and safe ordinary commands | Separate requirements and optional adapter import | Final independent review: 402 ordinary tests and lint passed without installing benchmark dependencies in their environment |

The task contains nine Required behavior bullets.

## Acceptance mapping

| Item | Implementation | Observed evidence |
| --- | --- | --- |
| A1: TEST-16 counts or explicit missing evidence | Tokenizer adapter and measurement command | Actual counts/version; alternate, disabled, absent, and corrupt cache checks |
| A2: TEST-17 deterministic gate boundaries | `synthetic_results`, `build_report` | Successful trials, ties, increases, lost success, timeouts, missing tests, insufficient repetitions, and source mismatches exercised |
| A3: synthetic fixture cannot promote | Derived provenance check | Synthetic report ineligible despite passing savings; regression test |
| A4: full comparable corpus | Workflow corpus, plan, separate transports | Seven cases, 42 independent arms, matched inputs, correct argument terminators, baseline TOON interviews and YAML templates |
| A5: reproducible report replay | Deterministic serialization and derived checks | CLI test and byte-identical manual replay |
| A6: visible partial results | Preserved evidence, incomplete status, condition kinds | Missing/invalid provenance now yields specific conditions, incomplete status, and null report provenance |
| A7: safe ordinary tests | Optional tokenizer and external adapter boundary | Ordinary suite and lint ran without provider credentials or model invocation |

## Independent verification pass 1 and dispositions

The maintainer supplied a fresh verifier report identifying G1–G4.
All four gaps were accepted within task scope and fixed.
No gap was rejected.
At the start of this follow-up, HEAD was still `02ebe833b278ba5889cbc4326520887e3cc92817` and all six task files remained untracked, alongside the initial unrelated files listed above.

| Gap | Fix | New-behavior coverage: observed red and green |
| --- | --- | --- |
| G1: alternate cache ignored | Cache selection follows TIKTOKEN_CACHE_DIR, DATA_GYM_CACHE_DIR, then the temporary default; empty values disable offline loading | `test_tokenizer_cache_matches_library_precedence_and_disabled_cache` failed on alternate/empty values, then passed; the original real-tokenizer network attempt was reproduced with the network intercepted, then all six real cache configurations passed |
| G2: selector after argument terminator | Candidate transport prepends its selector | `test_transport_preserves_example_name_after_argument_terminator` observed baseline exit 0 and candidate exit 2, then both succeeded |
| G3: unknown provenance labelled complete | Missing and invalid values add distinct evidence conditions, report null provenance, and remain incomplete | `test_missing_or_invalid_provenance_is_incomplete_and_preserves_evidence` failed for seven invalid values and one absent value, then passed; valid observed/synthetic reports remain complete |
| G4: cleanup skipped after failed wait | Evaluation interview fixtures use the existing InterviewHarness, with cleanup in finally and a registered backup cleanup | `test_interview_cleanup_stops_server_after_incomplete_answers_and_failed_wait` observed a live server after a failed wait, then passed with the server stopped; the backup cleanup also closed the server during the red run |

An additional discovered integration test, `test_real_tokenizer_rejects_empty_alternate_cache_despite_verified_default`, exercises G1 through the actual library.
Restoring the old inline cache lookup made this test fail on intercepted network access; restoring the fix made it pass.
This mutation proves that merely adding the cache selection helper without using it is caught.
The ordinary environment reports this test as skipped rather than claiming coverage without its dependencies.
Its exact execution command is documented in README.md.

Manual verification evidence for the fixes is in:
`/var/folders/gj/r365px1x66s54wjzw6b70bgm0000gn/T/toon-gap-fixes.uxNnAg/`.
The real tiktoken 0.12.0 probe intercepted network reads while exercising empty alternate caches, disabled caches, cache precedence, valid alternate caches, and the default cache.
Unavailable configurations produced missing dependency evidence; valid configurations produced actual token counts.
The full payload corpus was also measured using DATA_GYM_CACHE_DIR without TIKTOKEN_CACHE_DIR.
The actual baseline snapshot and current candidate both accepted `examples -- minimal-prd`.
Generated JSON and Markdown reports both marked missing and invalid provenance incomplete.
Synthetic JSON and Markdown report replays remained byte identical.

## Independent verification pass 2 and dispositions

The maintainer's second independent verifier confirmed the G1–G4 fixes and identified V1 and V2.
Both new gaps were accepted within task scope and fixed; none were rejected.
At the start of this follow-up, HEAD and the existing untracked file set matched the state recorded above.

| Gap | Fix | New-behavior coverage: observed red and green |
| --- | --- | --- |
| V1: staged additions and rename destinations omitted | Candidate enumeration unions HEAD paths, cached index paths, and permitted untracked paths, deduplicates them, and reads working bytes | `test_candidate_snapshot_includes_staged_additions_and_rename_destinations` first omitted both staged paths, then captured all four working files with their expected hashes and bytes; the removed rename source remained absent |
| V2: source paths alter payloads and token counts | Source paths use SOURCE markers; command arguments are normalized before quoting again; paths relative to the skill working directory are handled explicitly | `test_payload_corpus_and_measurements_survive_relocated_source_copies` first found different example paths between copies; the repository suite also exposed paths relative to the skill directory; after both fixes, all six source/directory combinations matched |

The V1 fixture mocks only Git read responses and uses real disposable working files.
No repository index or history mutation was needed.
The fixture also covers an existing path listed in both HEAD and the index, an untracked module, and working edits made after staging.
Removing the cached path enumeration loses the staged addition and rename destination in this test.
Removing source normalization or command argument normalization breaks the relocation test, including its source path with spaces and an apostrophe.

Manual verification evidence for V2 is in:
`/var/folders/gj/r365px1x66s54wjzw6b70bgm0000gn/T/toon-source-final.680rfL/`.
`source-manifest.json` records the reference snapshot, `measurements/` preserves six complete corpora and actual tokenizer results, and `comparison.json` records their common measurements.
All five payload families, fingerprints, and token counts matched across the working source, immutable reference, and writable execution copy from both working directories.
The tokenizer remained tiktoken 0.12.0 with the previously verified vocabulary and no model invocation.

## Independent verification pass 3 and dispositions

The third independent report identified two further gaps, called G1 and G2 in that report.
These labels belong to pass 3 and are separate from the pass 1 labels.
Both gaps were accepted within scope and fixed; none were rejected.
HEAD and the existing untracked file set matched the state recorded above when this follow-up began.

| Gap | Fix | New-behavior coverage: observed red and green |
| --- | --- | --- |
| Pass 3 G1: Git C quoting silently omits source files | HEAD, index, and untracked path enumeration all request NUL delimiters; a shared reader splits raw bytes and decodes filenames with os.fsdecode | `test_snapshot_captures_unicode_and_quoted_paths_from_all_git_lists` first captured only the ordinary file, then captured that file and the Unicode HEAD path, Unicode staged path, and quoted untracked path with all expected bytes and hashes |
| Pass 3 G2: conditions check ignores generated missing evidence | Evaluate the conditions check after all generated missing-evidence conditions have been appended | `test_conditions_check_includes_generated_missing_evidence_in_both_reports` first incorrectly passed the conditions check for five missing input families, then marked it failed in JSON and Markdown; complete input still passes |

The filename fixture uses real disposable files and mocked Git read responses that reproduce default C quoting unless NUL output is requested.
It separately exercises every path enumeration origin.
Removing the NUL option from any of the three enumeration commands causes the filename regression test to fail.
Moving the conditions check before missing-evidence generation causes the five missing-family cases to fail.
These tests also retain coverage for ordinary names, staged renames, deduplication, working edits, and complete evidence.

Manual verification evidence is in:
`/var/folders/gj/r365px1x66s54wjzw6b70bgm0000gn/T/toon-path-condition-fixes.Atkaov/`.
A real Git snapshot captured 118 source files into an immutable candidate snapshot and recorded its source manifest.
The missing-contract report CLI produced incomplete synthetic evidence with a failed conditions check in both JSON and Markdown.
All 27 focused tests passed with the real tokenizer environment, and the ordinary suite passed 401 tests with one optional skip.

## Source isolation follow-up and final independent verification

The next independent report classified every Required behavior and Acceptance item as covered but found one source isolation defect: candidate files could be read through a symlink in a parent directory.
The fix validates the lexical source root, rejects symlinks at the file and every ancestor through the source root, and checks resolved containment before reading bytes.
The maintainer's final independent review confirms that this gap is fixed and covered, with no further gaps in the fix.

- New-behavior coverage: all 28 focused tests passed; restoring the original guard in memory made the regression test fail in three cases.
- Manual verification: nine disposable probes rejected external, internal, nested, dangling, file, and source-root symlinks; ordinary files were captured and deleted files skipped.
- Regression coverage: the ordinary suite ran 403 tests, with 402 passed and the optional tokenizer test skipped.
- Manual verification: Python lint passed.

The final probe evidence is:
`/var/folders/gj/r365px1x66s54wjzw6b70bgm0000gn/T/toon-g1-review-n17tclvs/results.json`.
The preceding complete requirement review is recorded in the maintainer's report with evidence under `toon-verification.XVSWbp/`.
Together, that complete review and the final source isolation review cover every Required behavior, Acceptance item, and reported contract gap.

## Decisions, assumptions, and verification gaps

The README's Decision ledger records every delegated executor choice: tokenizer and adapter implementations, internal report layout, local tooling structure, and fixture orchestration.
The additional execution-copy choice follows observed bundle-copy permission behavior and preserves source bytes.
Assumptions: imported observed usage is honestly collected; the maintainer's adapter enforces the documented sandbox and authorization boundary; no report format can independently attest an external runner's unrecorded behavior.
The configured adapter protocol has received manual review only; no particular external adapter is shipped or exercised by this task.

Blocked task behavior: none.
Rejected gaps: none.
Unresolved verification gaps: none.
The maintainer extended independent verification by supplying the additional source isolation report and final clean review.
Every reported gap has a fix disposition, and the final review confirms the remaining fix is covered.
Task state: `done`.
