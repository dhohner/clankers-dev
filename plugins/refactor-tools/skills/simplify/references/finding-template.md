# Finding Format

Format every finding as follows.
Return an empty list when none are meaningful.

```md
- **pass**: reuse | quality | efficiency | altitude
  **file**: `path/to/file`
  **line**: L or L-L range
  **issue**: one-sentence description of the problem
  **cost**: what the issue costs, such as duplicated logic, wasted work, harder reading or maintenance, or the broken rule
  **rule**: `path/to/rules-file` - "quoted rule text" (project-rule violations only)
  **suggestion**: concrete code change or refactor to apply
  **confidence**: high | medium | low
  **risk**: safe | caution | risky
```

`safe` preserves behavior.
`caution` may change behavior.
`risky` changes public APIs or semantics.
