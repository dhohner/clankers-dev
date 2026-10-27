"""Local development evidence tooling; never invokes an agent."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2]
REPO = SKILL.parents[3]

BASELINE = "236cd788400d3e8d63bb850b6aca6cf0f482cb2b"
FAMILIES = ("schema", "examples", "validation", "inspection", "answers")


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


TASKS = ("discovery", "authoring", "repair", "publication", "inspection", "retrieval", "interview")


def payload_corpus():
    if str(SKILL) not in sys.path:
        sys.path.insert(0, str(SKILL))
    from scripts.cli import _run, parse_args
    from scripts.cli.interview import _answered_payload
    from scripts.cli.support import CliFailure, _cli_name, display_path
    from scripts.interview.answers import validate_submit
    from scripts.interview.rounds import validate_round

    fixtures = workflow_corpus()["fixtures"]
    round_ = validate_round(json.loads(fixtures["round.json"]))
    answers = validate_submit(round_, json.loads(fixtures["answers.json"]))

    with tempfile.TemporaryDirectory(prefix="toon-payloads-") as directory:
        root = Path(directory)
        manifest = root / "prd.yaml"
        shutil.copyfile(SKILL / "examples/minimal-prd.yaml", manifest)
        generated = _run(
            parse_args(["generate", str(manifest), "--output-root", str(root / "out")])
        )
        bundles = list((root / "out").glob("*/prd.yaml"))
        if len(bundles) != 1:
            raise ValueError(f"fixture generation failed: {generated.get('status')}")
        inspection = _run(parse_args(["inspect", str(bundles[0].parent), "--full"]))
        invalid = root / "invalid.yaml"
        invalid.write_text("schema_version: invalid\n", encoding="utf-8")
        try:
            _run(parse_args(["validate", str(invalid), "--full"]))
        except CliFailure as error:
            validation = error.payload
        else:
            raise ValueError("invalid fixture unexpectedly validated")

        # Paths are fixture identities, not machine-specific evidence.
        cli_name = _cli_name()
        example_prefix = display_path(SKILL / "examples") + "/"
        prefixes = {
            str(root.resolve()): "FIXTURE",
            str(root): "FIXTURE",
            str(SKILL.resolve()): "SOURCE",
            str(SKILL): "SOURCE",
            display_path(SKILL): "SOURCE",
        }
        replacements = sorted(
            ((prefix, marker) for prefix, marker in prefixes.items() if prefix not in ("", ".")),
            key=lambda item: len(item[0]),
            reverse=True,
        )

        def normalize(text):
            text = text.replace(cli_name, "to-prd")
            if text.startswith(example_prefix):
                text = "SOURCE/examples/" + text[len(example_prefix) :]
            for prefix, marker in replacements:
                text = text.replace(prefix, marker)
            return text

        def stable(value, commands=False):
            if isinstance(value, str):
                if commands:
                    arguments = shlex.split(value.replace(cli_name, "to-prd"))
                    return shlex.join(normalize(argument) for argument in arguments)
                return normalize(value)
            if isinstance(value, dict):
                return {key: stable(item, commands=key == "next") for key, item in value.items()}
            if isinstance(value, list):
                return [stable(item, commands=commands) for item in value]
            return value

        return {
            "schema": stable(_run(parse_args(["schema", "--full"]))),
            "examples": stable(_run(parse_args(["examples", "--full"]))),
            "validation": stable(validation),
            "inspection": stable(inspection),
            "answers": stable(_answered_payload(Path("FIXTURE/session"), round_, answers)),
        }


def measure(corpus, tokenizer, identity):
    result = {"tokenizer": identity, "payloads": [], "conditions": []}
    if tokenizer is None:
        result["conditions"].append(
            {
                "kind": "missing_dependency",
                "reason": "Install evals/toon-cli/requirements.txt and prefetch tokenizer cache; "
                "see README.md",
            }
        )
        return result
    if str(SKILL) not in sys.path:
        sys.path.insert(0, str(SKILL))
    from scripts.toon import dumps as toon
    from scripts.yaml_manifest import dumps as yaml

    for family, payload in corpus.items():
        result["payloads"].append(
            {
                "family": family,
                "provenance": "observed",
                "complete": True,
                "payload": digest(payload),
                "yaml_tokens": len(tokenizer(yaml(payload))),
                "toon_tokens": len(tokenizer(toon(payload))),
            }
        )
    return result


def workflow_corpus():
    fixture = (SKILL / "examples/minimal-prd.yaml").read_text(encoding="utf-8")
    prompts = {
        "discovery": "Discover the available schema blocks and examples. "
        "Explain the authoring contract.",
        "authoring": "Create prd.yaml for a shared household task planner "
        "using the supplied minimal PRD as a starting point. Validate it.",
        "repair": "Repair invalid.yaml until validation succeeds, preserving its initiative title.",
        "publication": "Generate a review bundle from prd.yaml in the supplied "
        "output root and validate its artifacts.",
        "inspection": "Publish prd.yaml, then inspect the resulting review bundle "
        "and report its requirements and traceability.",
        "retrieval": "Retrieve the complete schema and example documents and the complete "
        "manifest from a generated bundle; report the final entries.",
        "interview": "Replay an interview using round.json and answers.json without asking "
        "the user. Retrieve all answers, recover the session, and close it.",
    }
    answers = {
        "round": "ROUND-01",
        "answers": [
            {"node": f"NODE-{i:02}", "choice": "written", "written": f"fixture answer {i}"}
            for i in range(1, 31)
        ],
    }
    fixtures = {
        "prd.yaml": fixture,
        "invalid.yaml": "schema_version: invalid\ninitiative:\n  title: Household task planner\n",
        "answers.json": json.dumps(answers, sort_keys=True),
        "round.json": json.dumps(
            {
                "id": "ROUND-01",
                "questions": [
                    {
                        "node": f"NODE-{i:02}",
                        "label": f"Decision {i}",
                        "question": f"Fixture question {i}",
                        "multi_select": False,
                        "options": [
                            {
                                "label": "Default",
                                "description": "Fixture default",
                                "recommended": True,
                            }
                        ],
                    }
                    for i in range(1, 31)
                ],
            },
            sort_keys=True,
        ),
    }
    return {
        "prompts": prompts,
        "fixtures": fixtures,
        "permissions": "local CLI and fixture files; loopback interview only; "
        "no network providers except approved model transport; no browser; close every session",
    }


def prepare_execution_source(source, destination):
    shutil.copytree(source, destination)
    destination.chmod(0o755)
    for path in destination.rglob("*"):
        path.chmod(0o755 if path.is_dir() else 0o644)
    return destination


def seed_interview(run, source):
    code = (
        "import json,sys\nfrom pathlib import Path\n"
        "sys.dont_write_bytecode=True\n"
        "sys.path.insert(0,sys.argv[1])\n"
        "from scripts.interview.rounds import validate_round\n"
        "from scripts.interview.answers import validate_submit\n"
        "from scripts.interview.session import SessionFiles,store_round,store_answers,write_state\n"
        "workspace=Path(sys.argv[2])\n"
        "round_=validate_round(json.loads((workspace/'round.json').read_text()))\n"
        "answers=validate_submit(round_,json.loads((workspace/'answers.json').read_text()))\n"
        "files=SessionFiles(Path(sys.argv[3]))\n"
        "store_round(files,round_)\nstore_answers(files,answers)\n"
        "write_state(files,{'state':'active'})\n"
    )
    subprocess.run(
        [sys.executable, "-c", code, str(source), run["workspace"], run["session_dir"]],
        check=True,
        capture_output=True,
    )


def write_transport(root, source, arm):
    path = root / "to-prd.py"
    path.write_text(
        "import os, sys\n"
        "sys.dont_write_bytecode = True\n"
        f"sys.path.insert(0, {str(source.resolve())!r})\n"
        f"os.environ['TO_PRD_INTERVIEW_REGISTRY'] = {str(root.resolve() / 'registry.json')!r}\n"
        "os.environ['TO_PRD_INTERVIEW_BROWSER_LOG'] = os.devnull\n"
        "from scripts.cli import main\n"
        "args = sys.argv[1:]\n"
        f"if {arm!r} == 'candidate' and args[:1] != ['template']:\n"
        "    args = ['--format', 'toon', *args]\n"
        "raise SystemExit(main(args))\n",
        encoding="utf-8",
    )
    return path


def make_plan(root, repetitions):
    if type(repetitions) is not int or repetitions < 3:
        raise ValueError("at least three repetitions required")
    corpus = workflow_corpus()
    fixture = digest(corpus["fixtures"])
    permissions = digest(corpus["permissions"])
    runs = []
    for case in TASKS:
        prompt = digest(corpus["prompts"][case])
        for repetition in range(1, repetitions + 1):
            for arm in ("baseline", "candidate"):
                run = root.resolve() / "runs" / case / str(repetition) / arm
                workspace = run / "workspace"
                workspace.mkdir(parents=True, exist_ok=False)
                for name, content in corpus["fixtures"].items():
                    (workspace / name).write_text(content, encoding="utf-8")
                for name in ("out", "sessions"):
                    (run / name).mkdir()
                source = root.resolve() / "sources" / arm
                if source.is_dir():
                    source = prepare_execution_source(source, run / "source")
                transport = write_transport(run, source, arm)
                runs.append(
                    {
                        "transport": str(transport),
                        "execution_source": str(source),
                        "case": case,
                        "repetition": repetition,
                        "arm": arm,
                        "workspace": str(workspace),
                        "output_root": str(run / "out"),
                        "session_dir": str(run / "sessions"),
                        "registry": str(run / "registry.json"),
                        "prompt": prompt,
                        "fixture": fixture,
                        "permissions": permissions,
                        "operational_selector": ["--format", "toon"] if arm == "candidate" else [],
                    }
                )
    return {"schema_version": 1, "corpus": corpus, "repetitions": repetitions, "runs": runs}


def git_paths(arguments):
    output = subprocess.check_output(["git", *arguments], cwd=REPO)
    return [os.fsdecode(path) for path in output.split(b"\0") if path]


def snapshot(destination, arm):
    if arm not in ("baseline", "candidate"):
        raise ValueError("invalid source arm")
    revision = (
        BASELINE
        if arm == "baseline"
        else subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    )
    prefix = str(SKILL.relative_to(REPO)) + "/"
    paths = git_paths(["ls-tree", "-r", "-z", "--name-only", revision, "--", prefix])
    if arm == "candidate":
        paths.extend(git_paths(["ls-files", "--cached", "-z", "--", prefix]))
        untracked = git_paths(["ls-files", "--others", "--exclude-standard", "-z", "--", prefix])
        for path in untracked:
            relative = path.removeprefix(prefix)
            if (
                relative.startswith(("scripts/", "tests/")) and path.endswith(".py")
            ) or relative in (
                "evals/toon-cli/evaluate.py",
                "evals/toon-cli/README.md",
                "evals/toon-cli/SCHEMA.md",
                "evals/toon-cli/requirements.txt",
            ):
                paths.append(path)
    files = {}
    destination.mkdir(parents=True, exist_ok=False)
    for path in sorted(set(paths)):
        relative = path.removeprefix(prefix)
        if not (
            relative.startswith(("scripts/", "examples/", "bundle/", "tests/", "evals/"))
            or relative in ("README.md", "SKILL.md")
        ):
            continue
        source = REPO / path
        if arm == "candidate":
            if not source.is_relative_to(SKILL):
                raise ValueError(f"source outside permitted root: {relative}")
            current = source
            while current != SKILL.parent:
                if current.is_symlink():
                    raise ValueError(f"source symlink forbidden: {relative}")
                current = current.parent
            if not source.resolve().is_relative_to(SKILL.resolve()):
                raise ValueError(f"source outside permitted root: {relative}")
            if not source.exists():
                continue
        content = (
            source.read_bytes()
            if arm == "candidate"
            else subprocess.check_output(["git", "show", f"{revision}:{path}"], cwd=REPO)
        )
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        target.chmod(0o444)
        files[relative] = hashlib.sha256(content).hexdigest()
    for directory in destination.rglob("*"):
        if directory.is_dir():
            directory.chmod(0o555)
    destination.chmod(0o555)
    return {"base_revision": revision, "files": files, "fingerprint": digest(files)}


def synthetic_results():
    sources = {}
    for arm in ("baseline", "candidate"):
        files = {"scripts/x.py": digest(arm)}
        sources[arm] = {"base_revision": BASELINE, "files": files, "fingerprint": digest(files)}
    trials = []
    for case in TASKS:
        for repetition in range(1, 4):
            pair = {"case": case, "repetition": repetition}
            for arm in sources:
                pair[arm] = {
                    "source": sources[arm]["fingerprint"],
                    "agent": "fixture-agent@1",
                    "model": "fixture-model@1",
                    "prompt": digest(case),
                    "fixture": digest("fixture"),
                    "permissions": digest("local-only"),
                    "outcome": "success",
                    "input_tokens": 100 if arm == "baseline" else 80,
                    "output_tokens": 100 if arm == "baseline" else 80,
                    "total_tokens": 200 if arm == "baseline" else 160,
                    "tool_calls": 2,
                    "retries": 0,
                }
            trials.append(pair)
    return {
        "schema_version": 1,
        "provenance": "synthetic",
        "sources": sources,
        "contract_tests": {
            "outcome": "success",
            "source": sources["candidate"]["fingerprint"],
            "command": "fixture contract tests",
        },
        "tokenizer": {"name": "fixture", "version": "1", "model": "fixture-model@1"},
        "payloads": [
            {
                "family": family,
                "provenance": "observed",
                "complete": True,
                "payload": digest(family),
                "yaml_tokens": 10,
                "toon_tokens": 11,
            }
            for family in FAMILIES
        ],
        "trials": trials,
        "conditions": [],
    }


def write_json(path, value):
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def tokenizer_cache_directory(environ):
    for name in ("TIKTOKEN_CACHE_DIR", "DATA_GYM_CACHE_DIR"):
        if name in environ:
            return Path(environ[name]) if environ[name] else None
    return Path(tempfile.gettempdir()) / "data-gym-cache"


def local_tokenizer(model):
    # Only this pinned adapter is supported; loading an uncached vocabulary must not fetch it.
    identity = {"name": "tiktoken/o200k_base", "model": model}
    if model != "gpt-4o-2024-08-06":
        return None, identity
    try:
        import tiktoken

        identity["version"] = importlib.metadata.version("tiktoken")
        if identity["version"] != "0.12.0":
            return None, identity
        url = "https://openaipublic.blob.core.windows.net/encodings/o200k_base.tiktoken"
        cache = tokenizer_cache_directory(os.environ)
        if cache is None:
            return None, identity
        vocabulary = cache / hashlib.sha1(url.encode()).hexdigest()
        expected = "446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d"
        if (
            not vocabulary.is_file()
            or hashlib.sha256(vocabulary.read_bytes()).hexdigest() != expected
        ):
            return None, identity
        identity["vocabulary_sha256"] = expected
        encoding = tiktoken.encoding_for_model(model)
        return lambda text: encoding.encode(text, disallowed_special=()), identity
    except ImportError, OSError, ValueError:
        return None, identity


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("synthetic", "report", "measure", "plan"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--model", default="gpt-4o-2024-08-06")
    parser.add_argument("--repetitions", type=int, default=3)
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)
    if args.command == "plan":
        sources = {
            arm: snapshot(args.output / "sources" / arm, arm) for arm in ("baseline", "candidate")
        }
        plan = make_plan(args.output, args.repetitions)
        plan["sources"] = sources
        for run in plan["runs"]:
            if run["case"] == "interview":
                seed_interview(run, Path(run["execution_source"]))
        write_json(args.output / "plan.json", plan)
        return 0
    if args.command == "measure":
        corpus = payload_corpus()
        write_json(args.output / "payloads.json", corpus)
        tokenizer, identity = local_tokenizer(args.model)
        write_json(args.output / "measurements.json", measure(corpus, tokenizer, identity))
        return 0
    if args.command == "synthetic":
        data = synthetic_results()
        write_json(args.output / "results.json", data)
    else:
        if args.input is None:
            parser.error("report requires --input")
        try:
            data = json.loads(args.input.read_text(encoding="utf-8"))
        except OSError, ValueError:
            data = {
                "conditions": [{"kind": "malformed_evidence", "reason": "cannot read result JSON"}]
            }
    report = build_report(data)
    write_json(args.output / "report.json", report)
    lines = [
        "# Promotion evidence",
        "",
        f"Provenance: {report['provenance']}.",
        f"Completeness: {report['completeness']}.",
        f"Promotion eligible: {report['promotion_eligible']}.",
        "",
        (
            f"Workflow tokens: baseline {report['totals']['baseline']}; "
            f"candidate {report['totals']['candidate']}."
        ),
        "",
    ]
    lines.extend(
        f"- {name}: {'PASS' if check['passed'] else 'FAIL'} ({check['reason']})."
        for name, check in report["checks"].items()
    )
    lines.extend(f"- {item['kind']}: {item['reason']}." for item in report["conditions"])
    (args.output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


def count(value):
    return type(value) is int and value >= 0


def fingerprint(value):
    return (
        isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)
    )


def identifier(value):
    return isinstance(value, str) and bool(value.strip()) and not any(ord(c) < 32 for c in value)


def build_report(data):
    try:
        return derive_report(data)
    except TypeError, KeyError, AttributeError, ValueError:
        return {
            "schema_version": 1,
            "provenance": None,
            "completeness": "incomplete",
            "conditions": [{"kind": "malformed_evidence", "reason": "invalid evidence structure"}],
            "evidence": data,
            "totals": {"baseline": 0, "candidate": 0},
            "checks": {"structure": {"passed": False, "reason": "invalid evidence structure"}},
            "payload_changes": [],
            "promotion_eligible": False,
        }


def derive_report(data):
    checks = {}
    conditions = data.get("conditions", [])
    if not isinstance(conditions, list) or not all(
        isinstance(item, dict)
        and item.get("kind")
        in (
            "missing_authorization",
            "missing_dependency",
            "failed_run",
            "missing_evidence",
            "malformed_evidence",
        )
        and identifier(item.get("reason"))
        for item in conditions
    ):
        raise ValueError("invalid evidence conditions")
    conditions = list(conditions)
    totals = {"baseline": 0, "candidate": 0}

    def check(name, passed, reason):
        checks[name] = {"passed": bool(passed), "reason": "satisfied" if passed else reason}

    provenance = data.get("provenance")
    if "provenance" not in data:
        conditions.append({"kind": "missing_evidence", "reason": "evidence provenance is missing"})
    elif provenance not in ("synthetic", "observed"):
        conditions.append({"kind": "malformed_evidence", "reason": "invalid evidence provenance"})
    check("observed", provenance == "observed", "synthetic or missing provenance")
    check(
        "schema",
        type(data.get("schema_version")) is int and data["schema_version"] == 1,
        "unsupported evidence schema",
    )
    sources = data.get("sources", {})
    valid_sources = True
    for arm in totals:
        source = sources.get(arm, {})
        files = source.get("files", {})
        revision = source.get("base_revision", "")
        valid_sources &= (
            isinstance(files, dict)
            and bool(files)
            and all(
                identifier(k)
                and not k.startswith("/")
                and ".." not in k.split("/")
                and fingerprint(v)
                for k, v in files.items()
            )
            and source.get("fingerprint") == digest(files)
            and isinstance(revision, str)
            and len(revision) == 40
            and all(c in "0123456789abcdef" for c in revision)
            and (arm != "baseline" or revision == BASELINE)
        )
    check("sources", valid_sources, "missing or inconsistent source manifests")
    tests = data.get("contract_tests", {})
    check(
        "contract_tests",
        tests.get("outcome") == "success"
        and identifier(tests.get("command"))
        and fingerprint(tests.get("source"))
        and tests.get("source") == sources.get("candidate", {}).get("fingerprint"),
        "missing, failed, or mismatched candidate contract tests",
    )
    tokenizer = data.get("tokenizer", {})
    payloads = data.get("payloads", [])
    valid_payloads = (
        all(identifier(tokenizer.get(key)) for key in ("name", "version", "model"))
        and len(payloads) == len(FAMILIES)
        and {p.get("family") for p in payloads} == set(FAMILIES)
        and all(
            p.get("provenance") == "observed"
            and p.get("complete") is True
            and fingerprint(p.get("payload"))
            and count(p.get("yaml_tokens"))
            and count(p.get("toon_tokens"))
            for p in payloads
        )
    )
    check(
        "payload_measurements",
        valid_payloads,
        "missing actual complete payload measurements or tokenizer identity",
    )
    trials = data.get("trials", [])
    seen = set()
    repetitions = {case: set() for case in TASKS}
    valid_trials = True
    retained_success = True
    identities = set()
    case_inputs = {}
    for pair in trials:
        case, repetition = pair.get("case"), pair.get("repetition")
        key = (case, repetition)
        if case not in TASKS or not count(repetition) or repetition < 1 or key in seen:
            valid_trials = False
            continue
        seen.add(key)
        inputs = tuple(
            pair.get("baseline", {}).get(k) for k in ("prompt", "fixture", "permissions")
        )
        valid_trials &= case_inputs.setdefault(case, inputs) == inputs
        repetitions[case].add(repetition)
        baseline = pair.get("baseline", {})
        candidate = pair.get("candidate", {})
        for arm in totals:
            row = pair.get(arm, {})
            counts = all(
                count(row.get(k))
                for k in ("input_tokens", "output_tokens", "total_tokens", "tool_calls", "retries")
            )
            valid_trials &= counts
            if counts:
                total = row["input_tokens"] + row["output_tokens"]
                totals[arm] += total
                valid_trials &= total == row["total_tokens"]
            valid_trials &= row.get("outcome") in ("success", "failure", "timeout")
            valid_trials &= fingerprint(row.get("source")) and row.get("source") == sources.get(
                arm, {}
            ).get("fingerprint")
            valid_trials &= all(
                fingerprint(row.get(k)) for k in ("prompt", "fixture", "permissions")
            )
            valid_trials &= all(identifier(row.get(k)) for k in ("agent", "model"))
            valid_trials &= row.get("model") == tokenizer.get("model")
            identities.add((row.get("agent"), row.get("model")))
        valid_trials &= all(
            baseline.get(k) == candidate.get(k)
            for k in ("agent", "model", "prompt", "fixture", "permissions")
        )
        retained_success &= (
            baseline.get("outcome") != "success" or candidate.get("outcome") == "success"
        )
    sets = list(repetitions.values())
    valid_trials &= (
        len(identities) == 1
        and len(sets[0]) >= 3
        and sets[0] == set(range(1, len(sets[0]) + 1))
        and all(s == sets[0] for s in sets)
    )
    check(
        "paired_trials",
        valid_trials,
        "missing, malformed, duplicated, or incomparable paired repetitions",
    )
    check("task_success", retained_success, "baseline success lost to candidate failure or timeout")
    check(
        "savings",
        totals["candidate"] < totals["baseline"],
        "candidate aggregate input plus output tokens must be strictly lower",
    )
    if (
        not valid_trials
        or not valid_payloads
        or not valid_sources
        or not checks["contract_tests"]["passed"]
        or not checks["schema"]["passed"]
    ):
        conditions.append({"kind": "missing_evidence", "reason": "see derived gate checks"})
    check("conditions", not conditions, "unresolved evidence conditions")
    return {
        "schema_version": 1,
        "provenance": provenance if provenance in ("synthetic", "observed") else None,
        "completeness": "complete" if not conditions else "incomplete",
        "evidence": data,
        "conditions": conditions,
        "totals": totals,
        "checks": checks,
        "payload_changes": [
            {"family": p.get("family"), "token_delta": p["toon_tokens"] - p["yaml_tokens"]}
            for p in payloads
            if count(p.get("toon_tokens")) and count(p.get("yaml_tokens"))
        ],
        "promotion_eligible": all(c["passed"] for c in checks.values()),
    }


if __name__ == "__main__":
    raise SystemExit(main())
