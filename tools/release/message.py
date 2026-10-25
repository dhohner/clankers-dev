from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path


def git(repository: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repository), *args],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


def release_message(
    source: Path, distribution: Path, revision: str, initial_base: str
) -> str:
    if git(distribution, "ls-tree", "--name-only", "HEAD", "--", "SOURCE_REVISION"):
        previous = git(distribution, "show", "HEAD:SOURCE_REVISION")
    elif initial_base:
        previous = initial_base
    else:
        raise ValueError(
            "First release requires --initial-base with a source commit SHA."
        )
    for label, value in (
        ("Previous revision", previous),
        ("Source revision", revision),
    ):
        if not re.fullmatch(r"[0-9a-f]{40}", value):
            raise ValueError(f"{label} must be a full source commit SHA: {value!r}")
        git(source, "cat-file", "-e", f"{value}^{{commit}}")
    ancestor = git(source, "merge-base", previous, revision)
    sections = [f"release: clankers {revision[:7]}"]
    if ancestor == previous:
        commit_range = f"{previous}..{revision}"
    elif ancestor == revision:
        commit_range = f"{revision}..{previous}"
        sections.extend(
            [f"Rollback from {previous[:7]} to {revision[:7]}.", "Removed changes:"]
        )
    else:
        raise ValueError(f"Release revisions are not ancestors: {previous}, {revision}")
    messages = git(source, "log", "--reverse", "-z", "--format=%B", commit_range)
    changes = []
    for message in messages.split("\0"):
        message = re.sub(r"(?im)^Signed-off-by:.*\n?", "", message).strip()
        if not message:
            continue
        subject, _, body = message.partition("\n")
        changes.append(f"- {subject}")
        if re.match(r"build\(deps(?:-dev)?\):", subject):
            continue
        body = body.strip()
        if body:
            description = "\n".join(
                f"  {line}" if line else "" for line in body.splitlines()
            )
            changes.extend(["", description, ""])
    if changes:
        sections.append("\n".join(changes).rstrip())
    sections.append(f"Source: {previous[:7]}..{revision[:7]}")
    return "\n\n".join(sections) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a distribution commit message."
    )
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--distribution", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--initial-base", default="")
    args = parser.parse_args()
    try:
        message = release_message(
            args.source, args.distribution, args.revision, args.initial_base
        )
    except (ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Could not generate release message: {error}\n")
    print(message, end="")


if __name__ == "__main__":
    main()
