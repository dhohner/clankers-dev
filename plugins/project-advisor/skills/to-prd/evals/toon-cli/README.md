# Evaluate the TOON promotion gate

This development tool measures serialization and imports paired workflow evidence.
It never launches a configured agent.
Python 3.14 and Git are required.
Token measurement optionally requires the separately pinned dependencies in `requirements.txt`.
Operational Python commands and ordinary tests require no tokenizer package, credentials, or provider access.
[SCHEMA.md](SCHEMA.md) defines version 1 of the input and report formats.

## Offline commands

Run from the repository root with Python 3.14 already installed.
The commands write only to a disposable local evidence directory and create no servers.
Keep evidence outside `action-items/`, because interview sessions cannot live there.

```sh
T=plugins/project-advisor/skills/to-prd/evals/toon-cli
PY=$(uv python find 3.14)
E=$(mktemp -d "${TMPDIR:-/tmp}/toon-evidence.XXXXXX")
"$PY" "$T/evaluate.py" synthetic --output "$E/synthetic"
"$PY" "$T/evaluate.py" report --input "$E/synthetic/results.json" --output "$E/replay"
cmp "$E/synthetic/report.json" "$E/replay/report.json"
"$PY" "$T/evaluate.py" measure --output "$E/measurement"
"$PY" "$T/evaluate.py" plan --repetitions 3 --output "$E/experiment"
```

`synthetic/results.json` contains 21 fabricated pairs covering seven cases with three repetitions.
Its baseline workflow total is 4,200 tokens and candidate total is 3,360 tokens.
The savings check passes, but synthetic provenance prevents promotion.
These values prove report arithmetic only.
The fixture's nested observed markers model the shape of imported measurements; the enclosing synthetic marker always blocks eligibility.

Every report command writes `report.json` and `report.md` in the selected directory.
Malformed and partial evidence produces an incomplete report with reasons and retains supplied records.
The command's exit status describes successful report construction; read `promotion_eligible` for the gate result.
Missing tokenizer installation or vocabulary cache produces `measurement/measurements.json` with a `missing_dependency` condition and no estimated counts.
`measurement/payloads.json` preserves the measured complete values.

`plan` creates immutable source manifests, files with write permissions removed under `experiment/sources/`, and 42 separate arm workspaces under `experiment/runs/`.
Its baseline comes directly from commit `236cd788400d3e8d63bb850b6aca6cf0f482cb2b` through Git read operations.
The candidate captures working file bytes, their SHA-256 digests, and the current base revision without requiring a commit.
Candidate enumeration combines paths from HEAD and the current Git index, including staged additions and rename destinations, with the permitted untracked files.
All Git path lists use NUL delimiters and filesystem decoding so Unicode and quoted filenames retain their actual names.
Snapshots capture each existing path's working bytes, including edits made after staging.
The source policy includes tracked runtime, bundle, example, test, and evaluation files, plus untracked Python modules under scripts/tests and this tooling's named source files.
Each run executes a separate copy with identical bytes and normal writable asset modes.
This avoids propagating snapshot directory permissions into generated bundles, where they would prevent replacement and cleanup.
The immutable reference snapshots remain read-only.
The adapter must deny agent writes to execution sources and compare their bytes with the source manifests before and after each trial.
Do not put untracked runtime assets outside that manifest policy; add their explicit source paths to the snapshot policy before evaluating them.
The snapshot excludes arbitrary untracked evidence and local configuration files.
Never edit snapshots during trials.

## Install the real tokenizer

The installed adapter supports the immutable model version `gpt-4o-2024-08-06` with `tiktoken` and `o200k_base`.
It records the exact installed package version.
Other model adapters must use that model's actual tokenizer and retain the same measurement contract.
Unsupported models produce missing dependency evidence.

These optional preparation commands download public Python packages and the public tokenizer vocabulary.
They do not invoke a model or read provider credentials.
Run them separately from ordinary tests and from offline measurement.

```sh
uv venv --python 3.14 "$E/tokenizer-venv"
uv pip install --python "$E/tokenizer-venv/bin/python" -r "$T/requirements.txt"
export TIKTOKEN_CACHE_DIR="$E/tokenizer-cache"
"$E/tokenizer-venv/bin/python" -c 'import tiktoken; tiktoken.encoding_for_model("gpt-4o-2024-08-06")'
"$E/tokenizer-venv/bin/python" "$T/evaluate.py" measure --model gpt-4o-2024-08-06 --output "$E/measured"
```

For measurements tied to the frozen candidate, run its captured `evals/toon-cli/evaluate.py` in the last command instead of the working tree script.
The actual measurement command uses a previously cached vocabulary and never substitutes character counts.
Cache selection follows tiktoken: `TIKTOKEN_CACHE_DIR` takes precedence over `DATA_GYM_CACHE_DIR`, followed by the default temporary cache.
An explicitly empty cache variable disables caching and produces missing dependency evidence for offline measurement.
`measure()` also accepts a token sequence adapter for deterministic tests.
Synthetic adapter results remain synthetic experiment evidence and cannot authorize promotion.
Run the focused suite in the evaluation environment to include the real tokenizer integration test:

```sh
"$E/tokenizer-venv/bin/python" -m unittest discover -s plugins/project-advisor/skills/to-prd/tests -p test_prd_bundle_promotion_eval.py
```

That integration test intercepts network reads and checks an empty alternate cache against a verified default cache.
Ordinary test commands skip it when the optional package or prefetched vocabulary is unavailable.

## Payload corpus

The tool obtains complete schema and example list values using `--full`, constructs a validation failure from a deliberately invalid fixture, and generates and fully inspects a disposable bundle from `examples/minimal-prd.yaml`.
It validates 30 fixture interview answers and constructs the same complete answer response used by the CLI.
No interview browser or server is needed for measurement.
Before either encoding is constructed, payload workspace prefixes become `FIXTURE`, source prefixes become `SOURCE`, and the invoking executable becomes `to-prd`.
Recovery command arguments are parsed, normalized, and quoted again so relocating sources into paths with spaces or apostrophes preserves the same complete payload.
Both YAML and TOON encoders receive each identical complete value, before response reduction.
The report gives raw counts and changes for all five families; individual payload increases do not fail the gate.
Template documents use YAML in both workflow arms and are outside the operational serialization comparison.

## Controlled workflow trials

`plan.json` contains exact prompt strings, fixture contents, permission identity, and repetition count.
Its seven cases cover discovery, authoring, validation repair, publication, inspection, complete retrieval, and interview replay/recovery.
The authoring case covers writing and validating a document, extending the authoring scenarios in `../evals.json` without treating their expected outcomes as observations.
Fixtures include a minimal valid PRD, an invalid PRD preserving a known title, a valid interview round, and complete answers for every question.
The interview workspaces are seeded through each source arm's own round and answer validators and persistence functions.
A persisted active state without a server represents a recoverable session and allows replay followed by `interview end` without a browser or credential.
Every arm has a separate workspace, output root, session directory, and registry.
No plan command starts a server.

Use an external trial adapter that implements the following import contract.
Choosing and authorizing the configured agent is a maintainer action.
The import boundary lets maintainers use their existing agent runner without adding provider dependencies to operational code.

1. Freeze one exact agent version, one exact model version, all sampling settings, timeout policy, tool permissions, and repetition count before starting.
2. Run each plan row in its own workspace with fresh agent state.
   Supply the same prompt bytes to both arms, and make the same fixtures and command permissions available.
   Supply identical harness context in both arms: invoke `python ../to-prd.py`, publish into `../out`, and use `../sessions` for interviews.
   Include that harness context and all system prompts in the recorded prompt identity.
3. Expose the generated `to-prd.py` transport as the CLI entrypoint with identical permissions in both arms.
   The candidate transport prepends `--format toon` outside the prompt for operational commands, before any `--` argument terminator.
   It leaves successful templates as YAML.
   The baseline transport adds no selector: its existing interview TOON behavior remains the real baseline.
   Both transports disable bytecode writes, suppress browser opening, and use the run's isolated registry.
4. For interviews, replay the seeded round with `interview ask ../sessions round.json`, confirm all 30 fixture answers, inspect session status, and end the session.
   Use fixture answers for any recovery; never ask a real user for decisions.
   If an adapter exercises an open/recovery path that creates a local server, issue `interview end ../sessions` in a `finally` cleanup, including on timeout or adapter failure.
   Verify no recorded server remains alive before accepting that row.
5. Judge success against observable artifacts: discovery returns complete contracts; authored and repaired documents validate; publication creates valid local assets and manifest; inspection reports the generated document; retrieval reaches final entries; interview replay returns the last answer and closes the session.
   Keep the judgement rule identical across arms.
6. Record task outcomes, actual total input/output tokens, tool calls, and retries from the agent's usage accounting, including recovery and retries.
   Match the plan's source, prompt, fixture, and permission fingerprints.
   Never fill absent measurements with zero.
   An infrastructure failure becomes a `failed_run` condition; a completed task attempt may have outcome `failure` or `timeout` with measured usage.
7. Run the candidate operational contract suite against its source snapshot and record its source fingerprint, exact command, and outcome.
   Use a separate execution copy with normal asset permissions for these tests.
   The commands below construct that copy and run both contract modules.
   Baseline contract results may be retained as supplementary evidence; candidate results are mandatory.
8. Merge `plan.json` source identities, actual `measurements.json`, and the collected trials into an input following [SCHEMA.md](SCHEMA.md).
   Set `provenance: observed` only for actual collected evidence.
   Leave missing rows visible and record missing authorization, dependencies, and evidence separately.

Prepare and test the candidate contract source locally:

```sh
PYTHONPATH="$T" "$PY" -c 'from pathlib import Path; from evaluate import prepare_execution_source; import sys; prepare_execution_source(Path(sys.argv[1]), Path(sys.argv[2]))' "$E/experiment/sources/candidate" "$E/contract-source"
PYTHONDONTWRITEBYTECODE=1 "$PY" -B -m unittest discover -s "$E/contract-source/tests" -p test_prd_bundle_response_contract.py
PYTHONDONTWRITEBYTECODE=1 "$PY" -B -m unittest discover -s "$E/contract-source/tests" -p test_prd_bundle_discovery.py
```

A maintainer supplied adapter executable can expose this command interface:

```sh
# Requires approval for the named provider, credential use, budget, and local effects.
# TRIAL_ADAPTER names the maintainer's installed runner; this repository supplies no provider launcher.
"$TRIAL_ADAPTER" --plan "$E/experiment/plan.json" --results "$E/observed.json" --approval-reference "$APPROVAL_REFERENCE"
"$PY" "$T/evaluate.py" report --input "$E/observed.json" --output "$E/observed-report"
```

The first command may read configured credentials, contact a model provider, incur cost, write local agent sessions, and start loopback interview servers.
It requires explicit authorization naming those effects and a cost limit before execution.
A plan or a listed command does not supply authorization.
If approval is missing, record `missing_authorization` and generate an incomplete report instead.
The report command performs local reads and writes only.
Never store credentials, authentication URLs, environment dumps, provider transcripts, or local secret contents in the imported evidence.
Store only safe identities, outcome judgements, and numeric usage; review adapter output before importing it.

## Decision ledger

- Tokenizer implementation: use the optional pinned `tiktoken` adapter for one named immutable model and a cached vocabulary, because exact token counts require the evaluated model's tokenizer.
- Trial adapter implementation: import versioned result JSON from a maintainer supplied runner, because this repository has no configured agent adapter and actual model execution is outside this task.
- Report layout: use schema 1 JSON plus Markdown, preserve supplied partial records, and derive every gate decision from identities and numeric evidence.
  Missing or invalid provenance produces an incomplete report with `provenance: null` and a specific evidence condition.
- Local structure: keep all evaluation code and dependencies here, with one discovered standard library unittest module under `tests/`.
- Fixture orchestration: use disposable directories, source snapshots, separate transports and registries, and persisted fixture answers for replay so ordinary commands need no browser or server.
  Source enumeration includes staged additions and rename destinations and always captures working bytes.
  Measurement fixtures normalize source and workspace identities before encoding, including shell command arguments.
- Outcome interpretation: distinguish a measured negative task outcome from a failed evidence collection; only retained baseline successes define the task regression gate.

## Local validation

```sh
pnpm test:py:fast
pnpm lint:py
```

`tests/test_prd_bundle_promotion_eval.py` exercises report replay, corpus generation, token adapters, isolation, source manifests, transport selection, complete interview fixtures, and gate boundaries with synthetic results.
These commands start no configured agent and require no provider credentials.
The operational suite may start isolated local interview servers and closes them through its existing test harness.
Evaluation interview tests use that harness inside a `finally` cleanup, including when fixture answers are missing or a wait fails.
Actual agent evidence and promotion are separate follow-up tasks.
