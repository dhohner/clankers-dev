from __future__ import annotations

import contextlib
import io
import os
import re
import subprocess
import sys
import tempfile
import threading
from collections.abc import Iterator
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Literal
from unittest import mock

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT_DIR = SKILL_DIR / "scripts"
ENTRYPOINT = SCRIPT_DIR / "__main__.py"
EXAMPLE = SKILL_DIR / "examples" / "basic-spec.yaml"
SOURCE_ASSETS = SKILL_DIR / "bundle" / "assets"
EVIDENCE_REFERENCE = "plugins/project-advisor/skills/to-spec/scripts/bundle.py::generate_bundle"
# The interview opener appends page URLs to the file this variable names instead of opening
# a browser, so no CLI test opens a real browser.
BROWSER_LOG_ENV = "TO_SPEC_INTERVIEW_BROWSER_LOG"
# Every interview server a test starts records itself in the registry this variable names,
# so the tests and their child processes never touch the user's registry.
REGISTRY_ENV = "TO_SPEC_INTERVIEW_REGISTRY"
_REGISTRY_DIR = tempfile.TemporaryDirectory(prefix="to-spec-registry-")
os.environ[REGISTRY_ENV] = str(Path(_REGISTRY_DIR.name) / "interview-sessions.json")
NO_BROWSER_ENV = {**os.environ, BROWSER_LOG_ENV: os.devnull}

if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

import scripts as BUNDLE
from scripts.bundle import bundle_dir_name
from scripts.cli import main as cli_main


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the CLI in the test process the way `python -m scripts` runs it.

    The CLI reads the working directory for display paths and `sys.argv[0]` for the commands
    it suggests, so both match a run from the skill directory. `run_cli_process` covers the
    entry point itself.
    """
    argv = list(args)
    # Under an `InterviewHarness` the browser variable already names the harness log. Help
    # text wraps at the terminal width, which a process with piped output reads as 80.
    defaults = {BROWSER_LOG_ENV: os.devnull, "COLUMNS": "80"}
    environment = {name: value for name, value in defaults.items() if name not in os.environ}
    with (
        contextlib.chdir(SKILL_DIR),
        mock.patch.object(sys, "argv", [str(ENTRYPOINT), *argv]),
        mock.patch.dict(os.environ, environment),
        thread_output("stdout") as stdout,
        thread_output("stderr") as stderr,
    ):
        try:
            returncode = cli_main(argv)
        except SystemExit as error:
            returncode = _exit_status(error)
    return subprocess.CompletedProcess(
        [sys.executable, "-m", "scripts", *argv], returncode, stdout.getvalue(), stderr.getvalue()
    )


def run_cli_process(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the CLI as its own `python -m scripts` process."""
    return subprocess.run(
        [sys.executable, "-m", "scripts", *args],
        check=False,
        capture_output=True,
        text=True,
        cwd=SKILL_DIR,
        env=NO_BROWSER_ENV,
    )


def _exit_status(error: SystemExit) -> int:
    """Return the exit status of a process that raised this error, as the interpreter would."""
    if error.code is None:
        return 0
    if isinstance(error.code, int):
        return error.code
    print(error.code, file=sys.stderr)
    return 1


class ThreadOutput(io.TextIOBase):
    """Send each capturing thread's writes to its own buffer, and other writes through."""

    def __init__(self, fallback: Any) -> None:
        self._fallback = fallback
        self._local = threading.local()

    def capture(self) -> LineBuffer:
        buffer = LineBuffer()
        self._local.buffer = buffer
        return buffer

    @contextlib.contextmanager
    def captured(self) -> Iterator[LineBuffer]:
        """Capture this thread's writes until the block ends, then restore its earlier target."""
        previous = getattr(self._local, "buffer", None)
        try:
            yield self.capture()
        finally:
            self._local.buffer = previous

    def writable(self) -> bool:
        return True

    def write(self, text: str) -> int:
        buffer = getattr(self._local, "buffer", None)
        return (buffer or self._fallback).write(text)

    def flush(self) -> None:
        buffer = getattr(self._local, "buffer", None)
        (buffer or self._fallback).flush()


class LineBuffer(io.StringIO):
    """A text buffer that signals when a full line arrives."""

    def __init__(self) -> None:
        super().__init__()
        self.line_written = threading.Event()

    def write(self, text: str) -> int:
        count = super().write(text)
        if "\n" in text:
            self.line_written.set()
        return count


@contextlib.contextmanager
def thread_output(name: Literal["stdout", "stderr"]) -> Iterator[LineBuffer]:
    """Capture this thread's writes to `sys.stdout` or `sys.stderr`.

    Interview commands of an `InterviewHarness` may still write on their own threads, so
    their output keeps going to their own buffers.
    """
    stream = getattr(sys, name)
    routed = stream if isinstance(stream, ThreadOutput) else ThreadOutput(stream)
    setattr(sys, name, routed)
    try:
        with routed.captured() as buffer:
            yield buffer
    finally:
        setattr(sys, name, stream)


def run_generator(
    manifest: Path,
    output_root: Path,
    *extra_args: str,
) -> subprocess.CompletedProcess[str]:
    return run_cli(
        "generate",
        str(manifest),
        "--output-root",
        str(output_root),
        *extra_args,
    )


def load_example_manifest() -> dict[str, Any]:
    return BUNDLE.load_yaml(EXAMPLE.read_text(encoding="utf-8"))


# The review page is a sign-off summary for a product reader, in canonical block order.
REVIEW_BLOCKS = [
    "problem",
    "goals",
    "non_goals",
    "requirements",
    "scope",
    "risks",
    "rollout",
    "testing_strategy",
    "open_questions",
]


def rendered_sections(document: str) -> list[str]:
    """Return the ids of the page's block sections, in page order."""
    return re.findall(r'<section id="([a-z_]+)" class="section"', document)


def generate_bundle_dir(manifest: dict[str, Any], root: Path) -> Path:
    """Generate the manifest's bundle under root and return the bundle directory."""
    manifest_path = root / "spec.yaml"
    manifest_path.write_text(dump_yaml(manifest), encoding="utf-8")
    result = run_generator(manifest_path, root / "action-items")
    if result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    return root / "action-items" / bundle_dir_name(manifest["slug"])


def generate_example(manifest: dict[str, Any] | None = None) -> str:
    """Generate the example spec, or the given manifest, and return its index.html."""
    manifest = manifest or load_example_manifest()
    with tempfile.TemporaryDirectory() as temporary_directory:
        bundle = generate_bundle_dir(manifest, Path(temporary_directory))
        return (bundle / "index.html").read_text(encoding="utf-8")


def _without_deferred_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kept = []
    for node in nodes:
        if node["status"] == "deferred":
            continue
        if "children" in node:
            node["children"] = _without_deferred_nodes(node["children"])
            if not node["children"]:
                del node["children"]
        kept.append(node)
    return kept


def example_without_open_questions() -> dict[str, Any]:
    manifest = load_example_manifest()
    del manifest["blocks"]["open_questions"]
    # A deferred node must name an open question, so it cannot outlive that block.
    manifest["blocks"]["design_tree"] = _without_deferred_nodes(manifest["blocks"]["design_tree"])
    return manifest


# The smallest design tree, which every manifest must carry.
DESIGN_TREE_ROOT = {
    "id": "NODE-01",
    "label": "Output surface",
    "question": "Where is the design tree stored?",
    "status": "settled",
    "answer": "In spec.yaml beside the decisions.",
    "source": "user",
    "rationale": "Downstream skills read the tree from spec.yaml.",
}


def sample_block(name: str) -> Any:
    spec = BUNDLE.BLOCK_SPECS[name]
    if spec.kind == "summary":
        return {
            "metrics": [
                {
                    "label": "Current",
                    "value": "One fixed output",
                    "description": "A representative summary metric.",
                }
            ],
            "recommendation": "Use the generated review bundle.",
        }
    if spec.kind == "problem":
        return {"statement": "A clear problem.", "evidence": ["Observed evidence."]}
    if spec.kind == "scope":
        return {"in": ["Included behavior."], "out": ["Excluded behavior."]}
    if spec.kind == "table":
        return {"columns": ["From", "To"], "rows": [["A", "B"]]}
    if spec.kind == "questions":
        return [{"question": "What still needs a decision?"}]
    if spec.kind == "tree":
        return [
            {
                **DESIGN_TREE_ROOT,
                "children": [
                    {
                        "id": "NODE-02",
                        "label": "Node styling",
                        "question": "Which colours mark a pruned branch?",
                        "status": "pruned",
                        "reason": "Styling is an implementation choice.",
                    }
                ],
            }
        ]
    if spec.kind == "list":
        return ["Intentionally excluded outcome."]
    if spec.kind == "code":
        return [
            {
                "reference": "src/example.py",
                "language": "python",
                "code": "result = build()",
                "annotation": "Existing contract evidence.",
            }
        ]
    item = {field: f"{field.replace('_', ' ')} value" for field in spec.fields}
    if name == "requirements":
        item["exception"] = "Validation target is selected in a later block when present."
    return [item]


def base_manifest(
    initiative_type: str = "small-feature",
    surfaces: list[str] | None = None,
) -> dict[str, Any]:
    """Return a valid manifest whose only block is the design tree; tests add theirs to it."""
    return {
        "schema_version": 3,
        "slug": "catalog-fixture",
        "title": "Catalog fixture",
        "summary": "A focused manifest for block selection tests.",
        "status": "Draft",
        "initiative_type": initiative_type,
        "review_surfaces": surfaces or ["document"],
        "metadata": {"Owner": "Test"},
        "blocks": {"design_tree": [dict(DESIGN_TREE_ROOT)]},
    }


class AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.fragment_links: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        attributes = dict(attrs)
        identity = attributes.get("id")
        if identity:
            self.ids.append(identity)
        href = attributes.get("href")
        if tag == "a" and href and href.startswith("#") and len(href) > 1:
            self.fragment_links.append(href[1:])


def present[T](value: T | None) -> T:
    """Return a value the test fixture guarantees, and fail the test when it is missing."""
    if value is None:
        raise AssertionError("expected a value from the fixture, got None")
    return value


def dump_yaml(value: object) -> str:
    return BUNDLE.dump_yaml(value)


def load_yaml(value: str) -> Any:
    return BUNDLE.load_yaml(value)
