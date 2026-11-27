#!/bin/sh
# Prepares `<workspace>/repo` with the shop repository and one scenario from `changes/`.
# Commits the fixture on `main`, then applies the scenario's overlays in this order:
# - A `branch` file names a branch to create and switch to.
# - Each `commit*/` directory, in name order, becomes one commit.
# - `staged/` goes into the index.
# - `unstaged/` stays in the working tree.
# Usage:
# ```sh
# setup-simplify-eval.sh <workspace> <scenario>
# ```
# `<scenario>` names the `changes/` entry in the eval's `files`, such as `table-status`.
# Start the run in `<workspace>/repo`.
set -eu

if [ $# -ne 2 ]; then
  echo "usage: $0 <workspace> <scenario>" >&2
  exit 2
fi

here=$(cd "$(dirname "$0")" && pwd)
workspace=$1
scenario=$2
changes="$here/changes/$scenario"
repo="$workspace/repo"

if [ ! -d "$changes" ]; then
  echo "unknown scenario $scenario; expected a directory in $here/changes" >&2
  exit 2
fi

if [ -e "$repo" ]; then
  echo "refusing to overwrite $repo" >&2
  exit 1
fi

mkdir -p "$workspace"
cp -R "$here/shop-repo" "$repo"

cd "$repo"
# Global and system settings, such as commit signing and hook paths, can prevent fixture commits on developer machines.
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
commit_all() {
  git add -A
  git -c user.name=fixture -c user.email=fixture@example.invalid commit -q -m "$1"
}
git -c init.defaultBranch=main init -q
commit_all "Add shop fixture"

if [ -f "$changes/branch" ]; then
  git switch -q -c "$(cat "$changes/branch")"
fi
for overlay in "$changes"/commit*/; do
  [ -d "$overlay" ] || continue
  cp -R "$overlay." .
  commit_all "Change $scenario ($(basename "$overlay"))"
done
if [ -d "$changes/staged" ]; then
  cp -R "$changes/staged/." .
  git add -A
fi
if [ -d "$changes/unstaged" ]; then
  cp -R "$changes/unstaged/." .
fi
