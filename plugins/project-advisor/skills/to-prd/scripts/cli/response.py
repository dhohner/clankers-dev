"""Operational response encoding and usage rejection."""

from __future__ import annotations

import argparse
from typing import Any, NoReturn

from ..toon import dumps as dump_toon
from ..yaml_manifest import dumps as dump_yaml
from .support import next_command


class UsageError(Exception):
    pass


class FormatError(UsageError):
    """A selector cannot select a usable error encoding."""


NEXT_ACTIONS = {
    "to-prd": "status; schema --authoring; interview --help.",
    "to-prd status": "inspect <bundle-dir>; validate <prd.yaml>; interview status <session-dir>.",
    "to-prd validate": "generate <prd.yaml> after repair; validate <prd.yaml> --full for details.",
    "to-prd generate": "inspect <bundle-dir>; on refusal inspect before choosing replacement.",
    "to-prd inspect": "validate <prd.yaml>; repair before explicitly authorizing generate --force.",
    "to-prd schema": "template --blocks <block ...>; examples minimal-prd.",
    "to-prd template": "save the YAML document, replace placeholders, then validate <prd.yaml>.",
    "to-prd examples": "validate <prd.yaml>; generate <prd.yaml> using a listed path.",
    "to-prd interview": "interview ask <session-dir> <round-file>; interview status <session-dir>.",
    "to-prd interview ask": "record answers, ask the next round, or interview end <session-dir>.",
    "to-prd interview open": "interview status <session-dir>; resume ask for the open round.",
    "to-prd interview status": "interview open <session-dir>; resume ask or end the session.",
    "to-prd interview end": "interview ask <new-session-dir> <round-file> for a new session.",
}


class ResponseParser(argparse.ArgumentParser):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        epilog = kwargs.pop("epilog", "")
        contract = (
            "Migration: --format toon|yaml (also --format=value) selects responses "
            "before or after the command. "
            "TOON is the interview default; the other commands print YAML by default. "
            "Successful template output is always a YAML document. "
            "Exit codes: 0 success, 1 operation failure, 2 usage error. "
            "One response goes to stdout; progress goes to stderr. No terminal input. "
            "See references/cli-migration.md."
        )
        if kwargs.get("prog") == "to-prd template":
            contract += " --format yaml selects the document representation."
        next_actions = NEXT_ACTIONS.get(kwargs.get("prog", ""), "")
        super().__init__(
            *args,
            allow_abbrev=False,
            epilog=f"{epilog}\n{contract}\nNext: {next_actions}".strip(),
            **kwargs,
        )
        self.add_argument(
            "--format",
            choices=("toon", "yaml"),
            default="yaml",
            help=(
                "YAML document representation on success; response encoding on failure"
                if self.prog == "to-prd template"
                else "operational response encoding during migration"
            ),
        )

    def error(self, message: str) -> NoReturn:
        raise UsageError(message)


def emit(payload: dict[str, Any], output_format: str) -> None:
    encoded = dump_toon(payload) if output_format == "toon" else dump_yaml(payload)
    print(encoded.rstrip("\n"))


def usage_payload(message: str, argv: list[str]) -> dict[str, Any]:
    command = argv[:1]
    if command == ["interview"]:
        command += argv[1:2] if argv[1:2] in (["ask"], ["open"], ["status"], ["end"]) else []
    elif command not in (
        ["status"],
        ["schema"],
        ["examples"],
        ["validate"],
        ["generate"],
        ["inspect"],
        ["template"],
    ):
        command = []
    help_command = next_command(" ".join([*command, "--help"]))
    return {
        "status": "error",
        "code": "usage_error",
        "errors": [
            {"path": "arguments", "message": message, "fix": f"Run {help_command} for the usage."}
        ],
        "next": [help_command],
    }
