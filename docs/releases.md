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
5. Add the release key's public certificate, including its signing subkey, to `dhohner` under GitHub **Settings → SSH and GPG keys**.
   Ensure `43063759+dhohner@users.noreply.github.com` is associated with the account and the key.
6. Add two more secrets to the `distribution` environment:
   - `RELEASE_GPG_PRIVATE_KEY`: the armored private signing subkey, copied on macOS with `gpg --armor --export-secret-subkeys '<signing-subkey-fingerprint>!' | pbcopy`.
     Keep the primary private key off CI and keep private exports out of terminal output, chat, and Git.
   - `RELEASE_GPG_PASSPHRASE`: the passphrase protecting that signing subkey.

The workflow pins signing subkey `FF0E64E593E001E1EFD4A71ED5ABAA62E29AC2F9` from primary key `4A56B73FA8B37BB3C3D6C933B3C68A5AB1EF0230`.
This key expires on 2027-10-24.
When rotating keys, register the replacement public certificate, update both environment secrets, and update `RELEASE_SIGNING_KEY` in `.github/workflows/release.yml`.
Update `RELEASE_SIGNING_EMAIL` too if the verified signing address changes.

The development repository's default `GITHUB_TOKEN` cannot publish to the separate distribution repository.
The workflow uses it only to read development files and CI results.
The distribution token is used to check out and push to `dhohner/clankers`.

## Preview locally

Use Python 3.14, as required by the operational Python CLI, and install GnuPG with both `gpg` and `gpgconf` available on `PATH`.
The signing tests generate disposable keys in temporary keyrings and create local test commits without accessing your personal keys or publishing.
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
   If the distribution has no committed `SOURCE_REVISION` yet, set `initial_base` to the full source commit SHA immediately before the changes you want included in the first release.
   That commit is excluded from the changelog.
   Later releases read their starting revision from the distribution's committed `SOURCE_REVISION` and ignore this input.
4. Approve the `distribution` environment deployment if approval is configured.
5. Check the resulting commit on `dhohner/clankers` and its `SOURCE_REVISION` file.

The release workflow accepts only `dhohner/clankers-dev` on `main`.
It checks for a successful CI push run for the selected SHA, repeats the distribution tests, and builds the runtime file set.
It then removes all tracked files in a fresh distribution checkout and copies the generated files into it.
This removes old tests, evaluation cases, development tooling, and every `.github` file, including the old test workflow and Dependabot configuration.
The distribution contains no Actions workflows, including the release workflow itself.

Publishing uses `git commit -S -s` to create a GPG-signed commit as `dhohner <43063759+dhohner@users.noreply.github.com>` with a matching `Signed-off-by` trailer, then pushes it to `clankers/main`.
The commit subject is `release: clankers <short source hash>`, using the first seven characters of the source commit SHA.
The body lists every source commit since the previous release as a bullet, with descriptions indented beneath their subjects in source history order.
A final `Source: <previous short hash>..<current short hash>` line records the release range.
Both hashes use seven characters.
Source `Signed-off-by` lines are removed; dependency updates with `build(deps):` or `build(deps-dev):` subjects retain only their subjects.
The release commit receives its own signing trailer.
The workflow fetches the full source history and reads the previous revision from the distribution's committed `SOURCE_REVISION` before replacing files.
Missing or invalid source revisions and histories that have diverged stop publication.
Publishing an ancestor of the previous revision records a rollback with both revisions and the removed changes.
The signing step imports the private subkey into a temporary keyring and supplies its passphrase through a private file descriptor.
It forces the configured signing subkey, verifies the commit signature locally, then stops its GPG agent and deletes the temporary keyring and passphrase file.
An import or signing failure stops publication.
The signing secrets are available only to the signing step; the publishing step receives only `DIST_TOKEN`.
GitHub should display **Verified** when the public key and signing email are registered on the account.
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
README files are copied without changing their contents.

When adding runtime files outside existing patterns, update the allowlist and add a focused distribution assertion.
The distribution tests check file boundaries, package paths, marketplace roots, deterministic output, executable modes, isolated Python CLI execution, and removal of files from a checkout containing the previous development tree.
Message tests use local Git repositories to verify release boundaries, description preservation, metadata removal, the first release, invalid revisions, and rollbacks.
Signing tests verify the generated body in a real commit made with an exported signing subkey, the configured author and committer email, temporary keyring cleanup, rejection of invalid or missing secrets, rejection of a wrong passphrase, and handling of an unchanged distribution.

## History and installation

Existing Claude Code, Codex, and Pi installation URLs continue to use `dhohner/clankers`.
The marketplace names and plugin paths remain the same.
Users need to update their marketplace or Pi installation to receive the generated revision.

The first release removes tests and workflows from the current distribution tree.
Previous commits still contain those files, so a full Git clone can download them through history.
Removing historical content would require a separate, explicitly authorized history migration.
An older installed revision can also retain its test files until it is updated.
