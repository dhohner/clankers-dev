"""Prepare a distribution commit only for new revisions with changed runtime files."""

from __future__ import annotations

import argparse
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from build import build
from message import git, release_message, release_revisions


@dataclass(frozen=True)
class Preparation:
    previous: str
    revision: str
    status: Literal["publish", "already_published", "superseded", "unchanged"]
    counts: tuple[int, int, int] | None = None

    @property
    def reason(self) -> str:
        return {
            "publish": "Publication required.",
            "already_published": "Source revision is already published.",
            "superseded": "Source revision has been superseded by a published revision.",
            "unchanged": "Runtime files are unchanged.",
        }[self.status]

    def report(self) -> None:
        print(self.reason)
        if output := os.environ.get("GITHUB_OUTPUT"):
            with Path(output).open("a", encoding="utf-8") as handle:
                handle.write(f"publish={str(self.status == 'publish').lower()}\n")
        if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
            with Path(summary).open("a", encoding="utf-8") as handle:
                handle.write(
                    "## Distribution release\n\n"
                    f"Source: [{self.previous[:7]}..{self.revision[:7]}]"
                    "(https://github.com/dhohner/clankers-dev/compare/"
                    f"{self.previous}...{self.revision})\n\n"
                )
                if self.counts is not None:
                    added, modified, deleted = self.counts
                    handle.write(
                        f"Runtime files: {added} added, {modified} modified, "
                        f"{deleted} deleted.\n\n"
                    )
                handle.write(f"{self.reason}\n")


def prepare_release(
    source: Path, distribution: Path, revision: str, output: Path, message: Path
) -> Preparation:
    if git(source, "rev-parse", "HEAD") != revision:
        raise ValueError(f"Source checkout does not match tested revision {revision}.")
    previous, ancestor = release_revisions(source, distribution, revision)
    if previous == revision:
        return Preparation(previous, revision, "already_published")
    if ancestor == revision:
        return Preparation(previous, revision, "superseded")

    build(source, output, revision)
    subprocess.run(
        [
            "bash",
            str(Path(__file__).with_name("replace.sh")),
            str(output),
            str(distribution),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    # Ignore provenance alone, but retain file additions, removals, and mode changes.
    changes = git(
        distribution,
        "diff",
        "--cached",
        "--name-status",
        "--no-renames",
        "-z",
        "--",
        ".",
        ":(top,exclude)SOURCE_REVISION",
    )
    if not changes:
        git(
            distribution,
            "restore",
            "--source=HEAD",
            "--staged",
            "--worktree",
            "--",
            "SOURCE_REVISION",
        )
        return Preparation(previous, revision, "unchanged", (0, 0, 0))
    statuses = changes.rstrip("\0").split("\0")[::2]
    message.write_text(
        release_message(source, distribution, revision), encoding="utf-8"
    )
    return Preparation(
        previous,
        revision,
        "publish",
        counts=(
            statuses.count("A"),
            sum(status not in ("A", "D") for status in statuses),
            statuses.count("D"),
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--distribution", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--message", type=Path, required=True)
    args = parser.parse_args()
    try:
        preparation = prepare_release(
            args.source, args.distribution, args.revision, args.output, args.message
        )
        preparation.report()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        details = ""
        if isinstance(error, subprocess.CalledProcessError) and error.stderr:
            details = f"\n{error.stderr.strip()}"
        parser.exit(
            1, f"Could not prepare distribution for {args.revision}: {error}{details}\n"
        )


if __name__ == "__main__":
    main()
