# Release Clankers

Develop in `dhohner/clankers-dev` and publish generated runtime files to `dhohner/clankers`.
The checkout directory can keep its existing name.
`origin` points to `clankers-dev`; `dist` points to `clankers`.

## Configure GitHub once

1. In `clankers-dev`, create an Actions environment named `distribution`.
   Restrict deployment branches to `main` and configure a required reviewer if your GitHub plan supports it.
2. Create a fine-grained personal access token owned by the person publishing releases.
   Select only `dhohner/clankers` and grant repository **Contents: read and write** and **Workflows: read and write**.
   Workflow permission is required because the first release deletes existing workflow files from the distribution repository.
   Set an expiration date and rotate the token before it expires.
3. Add the token as the `DIST_TOKEN` secret in the `distribution` environment of `clankers-dev`.
   Keep the token out of files, command arguments, and logs.
4. Check branch rules on `clankers`.
   Allow the token owner to publish normal commits to `main`.
   Remove requirements for the distribution repository's old CI checks, because its workflows will be deleted.
   Keep development branch protection and required CI checks in `clankers-dev`.

The development repository's default `GITHUB_TOKEN` cannot publish to the separate distribution repository.
The workflow uses it only to read development files and CI results.
The distribution token is used to check out and push to `dhohner/clankers`.

## Preview locally

Use Python 3.14, as required by the operational Python CLI.
These commands write only to temporary directories and run no publishing steps.

```bash
uv run --no-project --isolated --python 3.14 python -m unittest discover -s tools/release/tests -v
output=$(mktemp -d)
uv run --no-project --isolated --python 3.14 python tools/release/build.py --output "$output"
find "$output" -type f
```

The builder selects tracked paths and reads their current working tree contents.
Local previews can therefore include uncommitted changes to tracked files.
Untracked files are excluded, so add new runtime files to Git before previewing them.
The release workflow checks out the selected commit, so published content comes from that commit.

## Publish

1. Review and commit development changes, then push them to `main` in `clankers-dev`.
2. Wait for the **CI** workflow's push run for that exact commit to pass.
   Its required `ci-ok` job includes the distribution tests.
3. In `clankers-dev`, open **Actions → Release distribution → Run workflow**, selecting `main`.
4. Approve the `distribution` environment deployment if approval is configured.
5. Check the resulting commit on `dhohner/clankers` and its `SOURCE_REVISION` file.

The release workflow accepts only `dhohner/clankers-dev` on `main`.
It checks for a successful CI push run for the selected SHA, repeats the distribution tests, and builds the runtime file set.
It then removes all tracked files in a fresh distribution checkout and copies the generated files into it.
This removes old tests, evaluation cases, development tooling, and every `.github` file, including the old test workflow and Dependabot configuration.
The distribution contains no Actions workflows, including the release workflow itself.

Publishing creates a normal commit attributed to the person who triggered the workflow and pushes it to `clankers/main`.
It creates no tags or GitHub Releases.
Repeating a release for the same source revision produces no commit if the distribution already matches.
Concurrent release runs queue, and a competing remote update causes the ordinary push to fail rather than overwrite history.
If a release fails before the push, fix the cause and rerun it.

## Maintain the file allowlist

`tools/release/files.json` defines the runtime paths.
It includes marketplace and plugin manifests, skills, references, templates, examples, scripts, assets, and Pi extension sources.
Examples under `to-prd/examples/fixtures/` are runtime authoring examples and remain included.
Tests under `tests/`, TypeScript `test/` directories, and development `evals/` directories are excluded.

The builder rejects development files even if a future allowlist pattern selects them.
It also rejects symlinks, unsafe patterns, and output directories that are nonempty or overlap the source checkout.
Executable file modes are preserved.

Generated package manifests omit scripts and development dependencies.
Their npm `files` lists are rebuilt from the actual distribution contents, including the security guard's `src/` files.
The development lockfile is excluded because it describes the development dependency graph.
Runtime dependency ranges and optional host peer declarations are preserved.
Every copied README points contributors to `clankers-dev` for development instructions.

When adding runtime files outside existing patterns, update the allowlist and add a focused distribution assertion.
The distribution tests check file boundaries, package paths, marketplace roots, deterministic output, executable modes, isolated Python CLI execution, and removal of files from a checkout containing the previous development tree.

## History and installation

Existing Claude Code, Codex, and Pi installation URLs continue to use `dhohner/clankers`.
The marketplace names and plugin paths remain the same.
Users need to update their marketplace or Pi installation to receive the generated revision.

The first release removes tests and workflows from the current distribution tree.
Previous commits still contain those files, so a full Git clone can download them through history.
Removing historical content would require a separate, explicitly authorized history migration.
An older installed revision can also retain its test files until it is updated.
