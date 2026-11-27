---
name: simplify
description: Simplify changed code in place while preserving behavior and edit scope.
disable-model-invocation: true
---

# Simplify Changed Code

Apply safe simplifications directly to the code.
Preserve intended behavior and the user's momentum.
Leave ambiguous or risky changes for the user.

An **edit region** is the smallest coherent unit that contains a changed hunk, such as a function, method, class member, test case, or local block.
Edit regions bound every finding and every edit.
Widen a region only for required helpers, imports, types, or adjacent duplicated branches.
Switch to whole files only on an explicit user request, and record it in the report.

Use another workflow for findings-only reviews, features, bug hunts, or architecture redesigns.

## 1. Determine scope

Treat text after the invocation as **focus** guidance.

Select files in this order:

1. Use any user-specified files, directories, commits, or revision ranges.
2. Otherwise, use staged files from `git diff --cached --name-only`.
3. Otherwise, use unstaged tracked files from `git diff --name-only`.
4. Otherwise, use the branch's commits from `git diff --name-only <merge-base> HEAD`.
5. Otherwise, use latest-commit files from `git show --name-only --pretty='' HEAD`.

For the branch source, take the merge base with the default branch: `origin/HEAD`, or else a local `main` or `master`.
Skip the branch source when no default branch exists or the current branch is the default branch.

Ask the user to stage any untracked file they name, because the before snapshot covers tracked files only.
Ask the user for files and stop when Git scope detection fails or produces an unusable result.

Exclude binary files, generated artifacts, lockfiles, and sourcemaps.
Also exclude vendored directories such as `node_modules/` and `vendor/`.

If no eligible files remain, respond exactly:

`No eligible files found in the selected scope.`

If the scope exceeds 15 files, list the files and request narrowing or batches.

Derive the selected diff and map each hunk to its edit region.
If the map is unavailable, ask for a current diff, revision range, or whole-file pass.

Before editing, record the **baseline**, the existing changes, as a **before snapshot** with `git stash create`.
Use `HEAD` as the before snapshot when the command prints nothing.
Preserve baseline changes and distinguish them from skill edits.

Scope is complete when every eligible file has an edit-region map, every excluded file has a recorded reason, and the before snapshot is recorded.

## 2. Load project rules

Load every rules file that governs each target file.
Search from the repository root through each target directory for `AGENTS.md`, `CLAUDE.md`, and `CLAUDE.local.md`.
Also load applicable `.github/copilot-instructions.md` and `.cursorrules` files.
Use repository-defined precedence when available.
Otherwise, let rules nearest the target override broader rules.

Extract enforceable rules: naming, structure, pattern, and prohibition rules that a specific line can break.
Treat general advice, such as "keep code readable", as context.
If no rules exist, use language conventions and standard linter guidance.

Rule loading is complete when every target file has a resolved rule set or the documented fallback.

## 3. Run four review passes

Run exactly four independent passes with the same input package.
Run the passes as parallel subagents when a subagent tool exists.
Otherwise, run them one after another in the current context.
Record how the passes ran, with the reason when a subagent tool existed but went unused.

Read [the finding template](references/finding-template.md) before running the passes.
Give every pass this input:

- The pass's own instructions from its section below.
- The edit-region map, the edit-region boundary rules, and sufficient surrounding context.
- Applicable project rules or `none found - use general best practices`.
- The user's focus guidance when present.
- Read-only access to search and read the repository.
- The finding template as the required output format.

### 3.1. Code Reuse

Find duplicated logic, repeated literals, useful shared helpers, and copied parameter-only branches.
Search shared or utility modules and files next to each target for existing helpers that the changed code re-implements.
Name the helper to call and the file that defines it.
Note any input, including edge cases, where the helper's behavior differs from the code it would replace.
Keep explicit test fixtures and small one-off paths when they are clearer.

### 3.2. Code Quality

Find weak names, mixed responsibilities, deep nesting, feature envy, and clever structures that direct code would make clearer.
Also find comment defects, dead code, and project-rule violations.
Report a project-rule violation only when you can quote the rule, name its file, and quote the line that breaks it.

### 3.3. Efficiency

Find avoidable loop work, repeated I/O, and redundant computation.
Also find dead paths and material complexity improvements.
Find independent operations that run one after another, and blocking work added to startup, import time, or hot paths.
Find long-lived objects, such as closures, callbacks, and caches, that keep more state alive than they use, and name the smaller state they need.
Use batching, caching, streaming, or lazy evaluation only for practical, material gains.

### 3.4. Altitude

Find changes that patch a symptom instead of fixing the root cause at the right depth.
Treat special cases layered on shared infrastructure as a sign that the fix belongs deeper.
Name the simpler, more general change to the underlying mechanism.

Review is complete when all four passes cover each edit region and return the required output.

## 4. Resolve findings

Process findings in this order:

1. Merge findings about the same line, symbol, or cause, keep the clearest suggestion, and record every pass that reported it.
2. Resolve conflicts in favor of the smaller, safer change.
3. Leave unresolved conflicts unchanged and report both suggestions.
4. Prioritize findings that match the user's focus.

Verify each finding that the rules below would apply against the current code:

- Re-read the cited lines and confirm that the issue exists there.
- Confirm that every helper, symbol, or rule the finding names exists and does what the finding claims.
- Check that the suggestion keeps results, side effects, and errors the same for every input the code accepts.
  Judge accepted inputs from type hints, docstrings, callers, and tests.
  A different error for an input the code already rejects, such as `None` where it needs a string, is not a behavior change.

Lower the confidence or raise the risk when verification contradicts the rating.

Apply findings by confidence and risk:

- Apply `high` confidence and `safe` risk findings.
- Apply `medium` confidence and `safe` risk findings only with targeted deterministic coverage.
- Leave `low` confidence, `caution`, and `risky` findings unchanged.
- Leave a finding unchanged with a `refuted` reason when its issue does not exist.
- Leave a finding unchanged with a `cost` reason when its stated cost is too small to justify the edit.
- Leave a finding outside the edit regions unchanged with a `scope` reason.

Resolution is complete when every finding that would be applied is verified and every distinct finding has one apply or leave-unchanged decision.

## 5. Apply fixes

Preserve public APIs, exports, signatures, and intended behavior.
Change them only on an explicit user request.

Update tests only when the refactor requires focused matching changes.
Preserve test intent, coverage, and assertion strength.
Keep skill edits unstaged.

Editing is complete when each apply decision is implemented and the baseline remains intact.

## 6. Validate

Find the project's validation commands in these sources, in order:

1. Commands that the loaded project rules name.
2. Targets and scripts in task runners and manifests, such as `Makefile`, `justfile`, `package.json`, `pyproject.toml`, `tox.ini`, or `Cargo.toml`.
3. Commands that CI workflows run, such as those under `.github/workflows/`.
4. Commands in `README` and `CONTRIBUTING` files.

Fall back to the language's standard test runner and linters only when no source names a command.

Run the narrowest relevant tests, type checks, linters, and custom project checks that cover the target files.
Inspect commands first and use only local validation without remote or shared side effects.
For each applied medium-confidence fix, run [the negative control](references/negative-control.md) after its targeted test passes.

Fix or reverse only the responsible skill edit when validation fails.
When causality is unclear, reverse the candidate edit and rerun the failed check.
If the failure persists, restore the candidate edit and report the failure as unrelated.

When any skill edit remains, record an **after snapshot** with `git stash create`.
The diff between the two snapshots must contain only skill edits.

Validation is complete when every applicable check has a recorded result, every gap in coverage is recorded, and the after snapshot exists whenever a skill edit remains.

## 7. Report completion

Follow one report template exactly:

- Read [standard report](references/standard-report.md) when a fix or unchanged finding exists.
- Read [no-change report](references/no-change-report.md) when no meaningful finding exists.

Replace its placeholders with observed values.

Reporting is complete when the report accounts for every finding, edit, check, and exclusion.
