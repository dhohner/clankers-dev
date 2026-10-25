"""Example catalog command for the PRD bundle CLI."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ..yaml_manifest import YamlError, loads
from .support import SKILL_DIR, CliFailure, bound_collection, bound_text, display_path, next_command


def command_examples(args: argparse.Namespace) -> dict[str, Any]:
    full = getattr(args, "full", False)
    paths = _example_paths()
    if args.name:
        paths = [path for path in paths if args.name in {path.stem, path.name}]
        if not paths:
            raise CliFailure(
                {
                    "status": "error",
                    "code": "example_unknown",
                    "example": args.name,
                    "errors": [
                        {
                            "path": "example",
                            "message": f"unknown example: {args.name}",
                            "fix": "Select a name listed by examples.",
                        }
                    ],
                    "next": [next_command("examples")],
                }
            )
    next_steps = (
        [
            next_command("validate", display_path(paths[0])),
            next_command("generate", display_path(paths[0])),
        ]
        if paths
        else [next_command("schema --authoring"), next_command("template --blocks design_tree")]
    )
    payload = {"status": "ok", "examples": paths, "next": next_steps}
    retrieval = next_command("examples", "--full", *(["--", args.name] if args.name else []))
    bound_collection(payload, "examples", full, retrieval)
    payload["examples"] = [_example_item(path) for path in payload["examples"]]
    for index, item in enumerate(payload["examples"]):
        if isinstance(item.get("title"), str):
            item["title"] = bound_text(
                payload, f"examples[{index}].title", item["title"], full, retrieval
            )
    return payload


def _example_paths() -> list[Path]:
    examples_dir = SKILL_DIR / "examples"
    paths = sorted(examples_dir.glob("*.yaml")) + sorted((examples_dir / "fixtures").glob("*.yaml"))
    return sorted(
        paths,
        key=lambda path: (
            path.stem != "minimal-prd",
            path.parent != examples_dir,
            path.name,
        ),
    )


def _example_item(path: Path) -> dict[str, Any]:
    item: dict[str, Any] = {"name": path.stem, "path": display_path(path)}
    try:
        raw = loads(path.read_text(encoding="utf-8"))
    except YamlError, OSError, UnicodeError:
        return item
    if isinstance(raw, dict):
        for field in ("title", "initiative_type"):
            if field in raw:
                item[field] = raw[field]
    return item


__all__ = ["command_examples"]
