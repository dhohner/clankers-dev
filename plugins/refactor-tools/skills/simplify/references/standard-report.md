# Standard Report

```md
**RESULT**

- Fixes applied: N
- Findings left unchanged: N
- Confidence: High | Medium | Low

**SCOPE**

- Source: staged changes | unstaged changes | branch commits since `<merge-base>` | last commit | user-specified scope
- Edit scope: edit regions | widened for correctness | whole-file by user request
- Files processed: N
- Files skipped: 0 | N (`path` - reason; ...)
- Project rules: `paths` | none - general best practices applied
- Focus: `<user focus text>` | none
- Passes: subagents | inline in this session (reason)
- Baseline changes preserved: yes | no (details)

**PASS FINDINGS**

- Code Reuse: N findings (N high, N medium, N low)
- Code Quality: N findings (N high, N medium, N low)
- Efficiency: N findings (N high, N medium, N low)
- Altitude: N findings (N high, N medium, N low)

**APPLIED FIXES**

- `file:line` - change - cost removed - confidence - passes: pass names

**LEFT UNCHANGED**

- `file:line` - suggestion - reason (confidence | risk | conflict | cost | refuted | scope | validation) - passes: pass names | none

**VALIDATION**

- `command` (source: project rules | file that defines it | language default) - outcome and covered behavior
- Negative control: `file:line` - deliberate break - test that failed | none needed
- Untested: behavior | none

**REVERSAL**

- Snapshots: before `<commit>` | `HEAD`, after `<commit>`
- Undo only the skill's edits: `git diff <before> <after> | git apply -R`
- Run it before `git gc` prunes the unreferenced snapshots, which takes about two weeks by default.
```

Count each pass's findings in `PASS FINDINGS` before merging.
List every pass that reported a merged finding, and use `passes: none` for a finding the skill noticed outside the passes.
Omit empty `APPLIED FIXES` and `LEFT UNCHANGED` sections, and omit `REVERSAL` when no skill edit remains.
