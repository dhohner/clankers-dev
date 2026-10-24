#!/usr/bin/env bash
set -euo pipefail

staging=$(cd "${1:?Pass the generated distribution directory}" && pwd -P)
checkout=$(cd "${2:?Pass the disposable distribution checkout}" && pwd -P)

if [ ! -f "$staging/SOURCE_REVISION" ] || [ -e "$staging/.git" ]; then
  echo 'Expected a generated distribution without Git metadata.' >&2
  exit 1
fi
if [ ! -d "$checkout/.git" ] || [ "$checkout" != "$(git -C "$checkout" rev-parse --show-toplevel)" ]; then
  echo 'Destination must be the root of a disposable Git checkout.' >&2
  exit 1
fi
if [[ "$staging/" == "$checkout/"* ]] || [[ "$checkout/" == "$staging/"* ]]; then
  echo 'Generated files and the destination checkout must not overlap.' >&2
  exit 1
fi

cd "$checkout"
git rm -r --ignore-unmatch -- .
cp -a "$staging/." .
git add --all
if git ls-files | grep -E '(^|/)(test|tests|evals|\.github)(/|$)|\.(whl|pyc)$'; then
  echo 'Development files remain in the distribution.' >&2
  exit 1
fi
