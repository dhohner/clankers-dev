"""Build a distribution from tracked runtime files, without changing the source tree."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

MANIFEST = Path(__file__).with_name("files.json")
DEVELOPMENT_PARTS = {
    ".git",
    ".github",
    "test",
    "tests",
    "evals",
    "node_modules",
    "__pycache__",
    ".ruff_cache",
    "coverage",
}
DEVELOPMENT_SUFFIXES = (".pyc", ".whl", ".test.ts", ".test.js", ".spec.ts", ".spec.js")
DEVELOPMENT_NOTICE = (
    "> This repository contains generated distribution files.\n"
    "> For development instructions, tests, and contributions, use "
    "[clankers-dev](https://github.com/dhohner/clankers-dev).\n\n"
)


def git(source: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(source), *args], text=True)


def runtime_files(source: Path, patterns: list[str]) -> list[Path]:
    tracked = set(git(source, "ls-files", "-z").rstrip("\0").split("\0"))
    selected: set[Path] = set()
    for pattern in patterns:
        if Path(pattern).is_absolute() or ".." in Path(pattern).parts:
            raise ValueError(f"Unsafe distribution pattern: {pattern}")
        for path in source.glob(pattern):
            relative = path.relative_to(source)
            if relative.as_posix() not in tracked:
                continue
            if DEVELOPMENT_PARTS.intersection(relative.parts) or relative.name.endswith(
                DEVELOPMENT_SUFFIXES
            ):
                raise ValueError(
                    f"Development file selected for distribution: {relative}"
                )
            if (
                path.is_symlink()
                or not path.is_file()
                or not path.resolve().is_relative_to(source)
            ):
                raise ValueError(
                    f"Distribution requires a regular file inside source: {relative}"
                )
            selected.add(relative)
    if not selected:
        raise ValueError("No tracked runtime files matched the distribution allowlist")
    return sorted(selected)


def require_path(root: Path, relative: str) -> Path:
    path = root / relative
    if not path.resolve().is_relative_to(root) or not path.exists():
        raise ValueError(f"Missing or unsafe runtime path: {relative}")
    return path


def prepare_packages(output: Path) -> None:
    for path in [output / "package.json", *output.glob("plugins/*/package.json")]:
        package = json.loads(path.read_text(encoding="utf-8"))
        package.pop("scripts", None)
        package.pop("devDependencies", None)
        # Exact paths also replace stale source-package globs in the npm file list.
        package["files"] = sorted(
            item.relative_to(path.parent).as_posix()
            for item in path.parent.rglob("*")
            if item.is_file() and item != path
        )
        path.write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8")


def validate_distribution(output: Path) -> None:
    require_path(output, "LICENSE")
    require_path(output, "README.md")
    for path in output.rglob("*"):
        relative = path.relative_to(output)
        if DEVELOPMENT_PARTS.intersection(relative.parts) or relative.name.endswith(
            DEVELOPMENT_SUFFIXES
        ):
            raise ValueError(f"Development file in distribution: {relative}")
    for catalog in (
        ".claude-plugin/marketplace.json",
        ".agents/plugins/marketplace.json",
    ):
        data = json.loads(require_path(output, catalog).read_text(encoding="utf-8"))
        for plugin in data["plugins"]:
            source = plugin["source"]
            relative = source if isinstance(source, str) else source["path"]
            root = require_path(output, relative)
            manifest = (
                ".claude-plugin/plugin.json"
                if catalog.startswith(".claude")
                else ".codex-plugin/plugin.json"
            )
            require_path(output, str(root.relative_to(output) / manifest))
    for path in [output / "package.json", *output.glob("plugins/*/package.json")]:
        package = json.loads(path.read_text(encoding="utf-8"))
        for paths in package.get("pi", {}).values():
            for relative in paths:
                require_path(output, str(path.parent.relative_to(output) / relative))
        for relative in package["files"]:
            require_path(output, str(path.parent.relative_to(output) / relative))


def build(
    source: Path, output: Path, revision: str, patterns: list[str] | None = None
) -> int:
    source, output = source.resolve(), output.resolve()
    if (
        output == source
        or source.is_relative_to(output)
        or output.is_relative_to(source)
    ):
        raise ValueError("Distribution output must be outside the source checkout")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError(f"Distribution output must be empty: {output}")
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Source revision must be a full Git commit SHA")
    if patterns is None:
        patterns = json.loads(MANIFEST.read_text(encoding="utf-8"))
    files = runtime_files(source, patterns)
    output.mkdir(parents=True, exist_ok=True)
    for relative in files:
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / relative, target)
    for path in output.rglob("README.md"):
        path.write_text(
            DEVELOPMENT_NOTICE + path.read_text(encoding="utf-8"), encoding="utf-8"
        )
    (output / "SOURCE_REVISION").write_text(revision + "\n", encoding="utf-8")
    prepare_packages(output)
    validate_distribution(output)
    return len(files)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    revision = git(args.source, "rev-parse", "HEAD").strip()
    try:
        count = build(args.source, args.output, revision)
    except ValueError as error:
        parser.exit(1, f"Distribution build failed: {error}\n")
    print(f"Built {count} runtime files from {revision} in {args.output}")


if __name__ == "__main__":
    main()
