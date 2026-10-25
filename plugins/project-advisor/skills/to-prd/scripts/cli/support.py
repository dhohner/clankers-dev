"""Shared helpers for the PRD bundle CLI."""

from __future__ import annotations

import re
import shlex
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from ..manifest_types import NormalizedManifest
from ..spec import CURRENT_SCHEMA_VERSION
from ..validation import ManifestError, validate_manifest
from ..yaml_manifest import YamlError, loads

SKILL_DIR = Path(__file__).resolve().parents[2]
ENTRYPOINT = SKILL_DIR / "scripts" / "__main__.py"
DESCRIPTION = "Validate, generate, inspect, and template YAML PRD review bundles."
_response_format: ContextVar[str | None] = ContextVar("response_format", default=None)
GERMAN_CANDIDATE = re.compile(
    r"[äöüÄÖÜß]|\b(und|oder|nicht|für|mit|ohne|wenn|dann|ist|sind)\b",
    re.IGNORECASE,
)


class CliFailure(Exception):
    def __init__(self, payload: dict[str, Any], exit_code: int = 1) -> None:
        self.payload = payload
        self.exit_code = exit_code


def display_executable() -> str:
    path = Path(sys.argv[0]).resolve()
    try:
        return str(Path("~") / path.relative_to(Path.home()))
    except ValueError:
        return str(path)


def display_path(path: Path) -> str:
    try:
        displayed = str(path.resolve().relative_to(Path.cwd().resolve()))
    except OSError, ValueError:
        displayed = str(path)
    return f"./{displayed}" if displayed.startswith("-") else displayed


@contextmanager
def command_context(response_format: str | None) -> Iterator[None]:
    token = _response_format.set(response_format)
    try:
        yield
    finally:
        _response_format.reset(token)


def next_command(
    command: str,
    *arguments: str | Path,
    output_root: Path | None = None,
    force: bool = False,
) -> str:
    target = command.split()[0]
    values = list(arguments)
    if output_root is not None and target in {"status", "generate"}:
        values.extend(("--output-root", display_path(output_root)))
    if force and target == "generate":
        values.append("--force")
    selector = _response_format.get()
    if selector and target != "template":
        option_end = values.index("--") if "--" in values else len(values)
        values[option_end:option_end] = ["--format", selector]
    literals = "".join(f" {shlex.quote(str(value))}" for value in values)
    return f"{_cli_name()} {command}{literals}"


def _cli_name() -> str:
    entrypoint = Path(sys.argv[0])
    if entrypoint.suffix == ".py":
        return f"{shlex.quote(sys.executable)} {shlex.quote(display_path(entrypoint))}"
    return shlex.quote(display_path(entrypoint))


def load_manifest(path: Path, full: bool = False) -> NormalizedManifest:
    try:
        raw = loads(path.read_text(encoding="utf-8"))
    except YamlError as error:
        raise CliFailure(
            {
                "status": "error",
                "code": "yaml_invalid",
                "manifest": display_path(path),
                "errors": [
                    {
                        "path": "manifest",
                        "message": f"line {error.line}, {error}",
                        "fix": "Repair the YAML syntax, then validate again.",
                    }
                ],
                "next": [
                    next_command("validate", display_path(path)),
                    next_command("examples"),
                ],
            }
        ) from error
    except FileNotFoundError as error:
        raise CliFailure(
            {
                "status": "error",
                "code": "file_not_found",
                "manifest": display_path(path),
                "errors": [
                    {
                        "path": "manifest",
                        "message": f"{display_path(path)} does not exist",
                        "fix": "Pass an existing YAML manifest path.",
                    }
                ],
                "next": [
                    next_command("validate", display_path(path)),
                    next_command("examples"),
                ],
            }
        ) from error
    except (OSError, UnicodeError) as error:
        raise CliFailure(
            {
                "status": "error",
                "code": "manifest_unreadable",
                "manifest": display_path(path),
                "errors": [
                    {
                        "path": "manifest",
                        "message": str(error),
                        "fix": "Pass a readable UTF-8 YAML or JSON manifest file.",
                    }
                ],
                "next": [next_command("validate", display_path(path))],
            }
        ) from error

    try:
        return validate_manifest(raw)
    except ManifestError as error:
        items = [_manifest_error_item(message) for message in error.errors]
        payload: dict[str, Any] = {
            "status": "error",
            "code": "manifest_invalid",
            "manifest": display_path(path),
            "total_errors": len(items),
            "errors": items,
            "next": [
                next_command("validate", display_path(path)),
                next_command("schema requirements"),
                next_command("examples api-heavy"),
            ],
        }
        bound_collection(
            payload, "errors", full, next_command("validate", display_path(path), "--full")
        )
        payload["truncated"] = payload["collection_metadata"]["errors"]["truncated"]
        raise CliFailure(payload) from error


def validation_payload(
    manifest: NormalizedManifest, manifest_path: Path, full: bool = False
) -> dict[str, Any]:
    manifest_summary = summary(manifest)
    german_candidates = manifest_summary["untranslated_german_candidates"]
    warnings = []
    if german_candidates:
        warnings.append(f"review {german_candidates} possible untranslated German string(s)")
    payload = {
        "status": "ok",
        "manifest": display_path(manifest_path),
        "manifest_version": manifest["schema_version"],
        "normalized_slug": manifest["slug"],
        "review_surfaces": manifest["review_surfaces"],
        "selected_blocks": list(manifest["blocks"]),
        "missing_traceability": [],
        "summary": manifest_summary,
        "warnings": warnings,
        "next": [
            next_command("generate", display_path(manifest_path)),
            next_command("schema requirements"),
        ],
    }
    retrieval = next_command("validate", display_path(manifest_path), "--full")
    for name in ("review_surfaces", "selected_blocks", "missing_traceability", "warnings"):
        bound_collection(payload, name, full, retrieval)
    return payload


def summary(manifest: NormalizedManifest) -> dict[str, int]:
    blocks = manifest["blocks"]
    return {
        "blocks": len(blocks),
        "requirements": len(blocks.get("requirements", [])),
        "tests": len(blocks.get("testing_strategy", [])),
        "risks": len(blocks.get("risks", [])),
        "open_questions": len(blocks.get("open_questions", [])),
        "untranslated_german_candidates": _count_german_candidates(manifest),
        "broken_references": 0,
    }


def bound_collection(payload: dict[str, Any], name: str, full: bool, retrieval: str) -> None:
    """Bound one discovery collection; callers must exclude authoritative content."""
    items = payload[name]
    shown, truncated = truncate(items, full)
    payload[name] = shown
    payload.setdefault("collection_metadata", {})[name] = {
        "total_count": len(items),
        "shown_count": len(shown),
        "truncated": truncated,
    }
    if truncated and retrieval not in payload["next"]:
        payload["next"].insert(0, retrieval)


def bound_text(payload: dict[str, Any], path: str, text: str, full: bool, retrieval: str) -> str:
    shown = text if full else text[:200]
    truncated = len(shown) < len(text)
    payload.setdefault("text_metadata", {})[path] = {
        "total_characters": len(text),
        "shown_characters": len(shown),
        "truncated": truncated,
        "command": retrieval,
    }
    if truncated and retrieval not in payload["next"]:
        payload["next"].insert(0, retrieval)
    return shown


def truncate(items: list[Any], full: bool, limit: int = 20) -> tuple[list[Any], bool]:
    if full or len(items) <= limit:
        return items, False
    return items[:limit], True


def _manifest_error_item(message: str) -> dict[str, str]:
    return {"path": _error_path(message), "message": message, "fix": _fix_for(message)}


def _error_path(message: str) -> str:
    if message.startswith("duplicate entity id"):
        return "blocks"
    markers = (" must ", " is ", " are ", " contains ", " requires ", " references ")
    for marker in markers:
        if marker in message:
            path = message.split(marker, 1)[0].split()[0]
            return path.rstrip(":")
    return "manifest"


def _fix_for(message: str) -> str:
    if (
        "must reference a TEST entity id" in message
        or "must connect to a validation outcome" in message
    ):
        return "Add a matching testing_strategy item or set an explicit exception."
    if "references missing entity id" in message:
        return "Add the referenced entity or remove the reference."
    if message.startswith("blocks.design_tree is required"):
        return "Add the design_tree block that this manifest version requires."
    if message.startswith("schema_version"):
        return (
            f"Set schema_version: {CURRENT_SCHEMA_VERSION} for a new manifest, "
            "or 1 for an existing manifest without a design tree."
        )
    if message.startswith("slug"):
        return "Use lowercase kebab-case."
    if "review_surfaces" in message:
        return "Include document and the initiative-specific review surface."
    if "must be a non-empty" in message:
        return "Provide the required value."
    return "Repair the value using the schema and validate the manifest again."


def _count_german_candidates(value: Any) -> int:
    if isinstance(value, str):
        return int(bool(GERMAN_CANDIDATE.search(value)))
    if isinstance(value, dict):
        return sum(_count_german_candidates(item) for item in value.values())
    if isinstance(value, list):
        return sum(_count_german_candidates(item) for item in value)
    return 0


__all__ = [
    "ENTRYPOINT",
    "SKILL_DIR",
    "CliFailure",
    "bound_collection",
    "bound_text",
    "display_path",
    "load_manifest",
    "next_command",
    "summary",
    "truncate",
    "validation_payload",
]
