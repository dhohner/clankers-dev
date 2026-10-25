"""CLI argument parsing and execution for PRD bundle workflows."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from . import interview
from .commands import COMMANDS
from .response import FormatError, ResponseParser, UsageError, emit, usage_payload
from .support import DESCRIPTION, CliFailure, command_context


def _build_parser() -> argparse.ArgumentParser:
    parser = ResponseParser(
        prog="to-prd",
        description=DESCRIPTION,
        epilog="Run browser interview rounds with `interview`; see interview --help.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status", help="show the workspace dashboard")
    status.add_argument("--output-root", type=Path, default=Path("action-items"))

    validate = subparsers.add_parser("validate", help="validate a PRD YAML manifest")
    validate.add_argument("manifest", type=Path)
    validate.add_argument(
        "--full",
        action="store_true",
        help="show all validation detail",
    )

    generate = subparsers.add_parser("generate", help="generate a PRD bundle from YAML")
    generate.add_argument("manifest", type=Path)
    generate.add_argument("--output-root", type=Path, default=Path("action-items"))
    generate.add_argument(
        "--force",
        action="store_true",
        help="replace an existing generated bundle",
    )

    inspect = subparsers.add_parser("inspect", help="inspect a generated PRD bundle")
    inspect.add_argument("bundle", type=Path)
    inspect.add_argument(
        "--full",
        action="store_true",
        help="include normalized manifest and full lists",
    )

    schema = subparsers.add_parser("schema", help="show manifest schema summary")
    schema.add_argument("blocks", nargs="*", help="optional block names, such as requirements")
    schema.add_argument(
        "--authoring",
        action="store_true",
        help="show the compact initiative and block selection guide",
    )

    template = subparsers.add_parser("template", help="emit a placeholder PRD manifest")
    template.add_argument(
        "--blocks",
        nargs="+",
        required=True,
        help="block names to include",
    )

    examples = subparsers.add_parser("examples", help="list bundled example manifests")
    examples.add_argument("name", nargs="?", help="optional example name or stem")
    subparsers.add_parser("interview", help="browser interview commands")

    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    raw, output_format = _extract_format(list(sys.argv[1:] if argv is None else argv))
    if not raw:
        raw = ["status"]
    args = _build_parser().parse_args(raw)
    if args.command == "interview":
        raise UsageError("use the interview parser for interview commands")
    args.format = output_format[1] if output_format else "yaml"
    return args


def _extract_format(raw: list[str]) -> tuple[list[str], list[str]]:
    remaining: list[str] = []
    selectors: list[str] = []
    index = 0
    while index < len(raw):
        value = raw[index]
        if value == "--":
            remaining.extend(raw[index:])
            break
        if value == "--format":
            if index + 1 == len(raw) or raw[index + 1].startswith("--"):
                raise FormatError("--format requires toon or yaml")
            selectors.append(raw[index + 1])
            index += 2
            continue
        if value.startswith("--format="):
            selectors.append(value.split("=", 1)[1])
            index += 1
            continue
        remaining.append(value)
        index += 1
    if any(value not in {"toon", "yaml"} for value in selectors):
        raise FormatError("--format accepts only toon or yaml")
    if len(set(selectors)) > 1:
        raise FormatError("conflicting --format selectors; select one response format")
    return remaining, ["--format", selectors[0]] if selectors else []


def _run(args: argparse.Namespace) -> dict[str, Any]:
    command = COMMANDS.get(args.command)
    if command is None:
        raise RuntimeError(f"unsupported command: {args.command}")
    return command(args)


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    try:
        remaining, selector = _extract_format(raw)
    except FormatError as error:
        emit(usage_payload(str(error), raw), "toon")
        return 2
    is_interview = remaining[:1] == ["interview"]
    output_format = selector[1] if selector else ("toon" if is_interview else "yaml")
    explicit_format = selector[1] if selector else None
    if remaining[:1] == ["template"] and explicit_format == "yaml":
        explicit_format = None
    with command_context(explicit_format):
        try:
            if is_interview:
                payload = interview.run(remaining[1:])
            else:
                args = parse_args(raw)
                payload = _run(args)
                if args.command == "template":
                    output_format = "yaml"
            exit_code = 0
        except UsageError as error:
            payload = usage_payload(str(error), remaining)
            exit_code = 2
        except (CliFailure, interview.InterviewFailure) as error:
            payload = error.payload
            exit_code = error.exit_code if isinstance(error, CliFailure) else 1
    emit(payload, output_format)
    return exit_code


__all__ = ["main", "parse_args"]
