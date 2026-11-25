# Write a spec

The `to-spec` skill turns a product idea or spec review note into a validated local review bundle.
The agent makes product decisions, checks repository evidence, records uncertainty, and selects blocks.
The generator validates the schema and structure, escapes content, renders the canonical output, copies assets, and publishes the bundle atomically.

## Output

```text
action-items/SPEC-<slug>/
├── index.html
├── spec.yaml
└── assets/
    ├── app.js
    ├── favicon.svg
    ├── styles.css
    └── fonts/
```

`spec.yaml` is the normalized planning source and records the interview design tree beside the decisions.
Reviewers open `index.html` to review the spec.
The page is a sign-off summary for a product reader.
It shows the problem, goals, non-goals, requirements, scope, risks, rollout, testing strategy, and open questions.
The other blocks, such as decisions, the design tree, and contracts, stay in `spec.yaml` for `to-issues` and `to-agent-tasks`.
The bundle includes its assets, including the Manrope font under the OFL license and its license text.
Reviewers need no plugin and see identical typography on every machine.

The bundle is for viewing on screen and does not support printing.
The page loads nothing from the network.

## Workflow

`SKILL.md` defines the loop: check evidence for the decision, write the manifest, publish and inspect the bundle, and wait for review.
The agent asks each interview round in the local browser with `interview ask` and waits for review in the chat.
Acceptance sets `status: Accepted` in the published `spec.yaml`, which `to-issues` and `to-agent-tasks` read.
For feedback on an existing spec, the agent revises a scratch copy of `spec.yaml` and repeats the loop.
[references/manifest-contract.md](references/manifest-contract.md) describes the manifest versions and the rules the CLI does not print.

## CLI

From the root of this repository, publish a bundle with the commands below.
In another repository, replace `plugins/project-advisor/skills/to-spec` with the directory that holds `SKILL.md`.

```sh
python3 plugins/project-advisor/skills/to-spec/scripts/__main__.py validate plugins/project-advisor/skills/to-spec/examples/minimal-spec.yaml
python3 plugins/project-advisor/skills/to-spec/scripts/__main__.py generate plugins/project-advisor/skills/to-spec/examples/minimal-spec.yaml
python3 plugins/project-advisor/skills/to-spec/scripts/__main__.py inspect action-items/SPEC-minimal-spec/
```

Commands:

- `status`: workspace dashboard and the no-argument default.
- `schema [block ...]`: manifest fields, supported blocks, and block examples.
- `template --blocks <block ...>`: valid placeholder manifest for the selected blocks.
- `examples [name]`: bundled manifest examples.
- `validate <spec.yaml>`: validate without writing.
- `generate <spec.yaml>`: generate after validation.
- `inspect <bundle-dir>`: summarize generated structure, assets, anchors, traceability, and validation.
  `traceability.held` lists each entity that still misses a connection, such as a requirement without a decision or risk.
- `interview <command>`: browser interview rounds, described in [Interview](#interview).

Options:

- `--output-root <directory>` changes the bundle parent for `status` and `generate`.
- `--force` replaces an existing bundle with the same slug after the new output validates.
- `--format yaml|text` selects the output format, and non-template commands default to YAML.
  The `interview` commands take no `--format`.
- `--full` expands large `validate` and `inspect` output.

The CLI needs Python 3.14 or newer, without a virtual environment, package installation, or Node.js.
An older interpreter stops with a message that names a `uv run` command to use instead.
The `next` lines name the interpreter that ran the CLI.
`validate` and `inspect` print `warnings` for sentences over twenty words and for research evidence they cannot find.
Only `interview ask` and `interview open` use a browser, and they open the local default browser.

## Interview

The `interview` commands present each round of a session on a local page.
A session directory is a scratch directory outside `action-items/`.
It holds the scratch `spec.yaml`, the round files, and the `interview/` directory with the answers and the server state.
Each spec and each revision starts a new session.

```sh
python3 plugins/project-advisor/skills/to-spec/scripts/__main__.py interview ask <session-dir> <round-file>
python3 plugins/project-advisor/skills/to-spec/scripts/__main__.py interview open <session-dir>
python3 plugins/project-advisor/skills/to-spec/scripts/__main__.py interview status <session-dir>
python3 plugins/project-advisor/skills/to-spec/scripts/__main__.py interview end <session-dir>
```

- `interview ask <session-dir> <round-file>` validates the round file and starts the session server when none runs.
  - It opens the page when the session gets its first server or a new port, so a closed tab needs `interview open`.
  - It blocks until the round has a result, and prints `answered`, `browser_disconnected`, or `ended`.
  - An `answered` result includes each answer with its `parent` node and its design tree `record`.
    It also gives the `instructions` for recording the answers.
  - Asking an already answered round prints the stored answers immediately.
  - `interview ask --help` prints the round file fields and an example.
- `interview open <session-dir>` opens the page again, and starts the server again when it has stopped.
- `interview status <session-dir>` prints the session state, whether the server runs, and the counts of asked rounds, answered rounds, and deferred questions.
- `interview end <session-dir>` ends the session and stops its server.
  - A second `interview end` on the same session succeeds.

Each `interview` command prints results and errors to stdout in TOON format.
Both include `next` lines listing the commands that can follow.

Exit codes:

- `0`: success, including `browser_disconnected` and `ended`.
- `1`: error, such as an invalid round file or a session inside `action-items/`.
- `2`: unknown flag or usage error.

`status` lists the live interview sessions of the current workspace under `interview_sessions`, with the session directory and state of each.
A live session has a running server started by a command in the current directory.

With `TO_SPEC_INTERVIEW_BROWSER_LOG` set to a file path, the commands append the page link to that file and open no browser.

### Page checklist

Use `playwright-cli` to check a live interview session in this order:

1. [Conversation and drafts](references/interview-page-checklist.md), including setup.
2. [Connection and submission](references/interview-submission-checklist.md).
3. [Lifecycle and policy](references/interview-lifecycle-checklist.md).

The test suite does not need `playwright-cli` or a browser.

## References

- `references/manifest-contract.md`: manifest versions and rules the CLI schema does not print.
- `references/review-checklist.md`: full bundle checklist when inspection is insufficient.
- `references/interview-page-checklist.md`: browser setup, conversation, and draft checks with `playwright-cli`.
- `references/interview-submission-checklist.md`: connection, submission, and competing tab checks.
- `references/interview-lifecycle-checklist.md`: round history, session lifecycle, and page policy checks.
- `examples/minimal-spec.yaml`: smallest valid manifest.
- `examples/basic-spec.yaml`: broad mixed-initiative example.
- `examples/fixtures/*.yaml`: focused examples by initiative type.
- `bundle/`: canonical HTML shell and versioned assets.
- `evals/`: regression prompts and expectations.

## Test

Run the suite from the repository root with [uv](https://docs.astral.sh/uv/) installed.
The test commands use uv to select Python 3.14, downloading it if needed.
They run in a temporary virtual environment so child commands also use that Python version.
`pnpm test:py:fast` skips the harness self-tests of the time limits and the watchdog.

```sh
pnpm test:py
pnpm test:py:fast
```

The runner starts one `unittest` process for each `tests/test_spec_bundle_*.py` module, including the `interview` modules.
It prints the full output of each failing module, lists each skipped test with its reason, and ends with the ten slowest tests.
It also runs single modules or tests, each in its own process:

```sh
cd plugins/project-advisor/skills/to-spec
uv run --no-project --isolated --python 3.14 python tests/run_parallel.py
uv run --no-project --isolated --python 3.14 python tests/run_parallel.py test_spec_bundle_interview_toon
uv run --no-project --isolated --python 3.14 python tests/run_parallel.py test_spec_bundle_interview_toon.ToonWriterTests.test_prints_scalars_as_key_value_lines
```

The tests import their helpers as top-level modules, so plain `unittest` needs the tests directory on `PYTHONPATH`, or `discover` for the whole suite:

```sh
cd plugins/project-advisor/skills/to-spec
PYTHONPATH=tests uv run --no-project --isolated --python 3.14 python -m unittest --durations 10 test_spec_bundle_interview_toon
uv run --no-project --isolated --python 3.14 python -m unittest discover --durations 10 tests 'test_spec_bundle_*.py'
```

The interview tests fail any test that runs longer than about a second.
On a slow or loaded machine, set `TO_SPEC_TEST_TIME_SCALE` to a positive factor for every time limit, such as `3`:

```sh
TO_SPEC_TEST_TIME_SCALE=3 pnpm test:py
```

Lint and format the CLI with [ruff](https://docs.astral.sh/ruff/), configured in `ruff.toml`:

```sh
cd plugins/project-advisor/skills/to-spec
uvx ruff check .
uvx ruff format --check .
```

Ruff is a development tool only, so the CLI still runs with a bare `python3`.
