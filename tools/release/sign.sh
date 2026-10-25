#!/usr/bin/env bash
set -euo pipefail

checkout=${1:?Pass the distribution checkout}
if git -C "$checkout" diff --cached --quiet; then
  echo 'Distribution already matches this source commit.'
  exit 0
fi

: "${RELEASE_GPG_PRIVATE_KEY:?Set the private signing subkey}"
: "${RELEASE_GPG_PASSPHRASE:?Set the signing subkey passphrase}"
: "${RELEASE_SIGNING_KEY:?Set the signing subkey fingerprint}"
: "${RELEASE_SIGNING_EMAIL:?Set the verified signing email}"
message=${2:?Pass the generated release message file}

export GNUPGHOME
GNUPGHOME=$(mktemp -d)
chmod 700 "$GNUPGHOME"
cleanup() {
  gpgconf --homedir "$GNUPGHOME" --kill gpg-agent >/dev/null 2>&1 || true
  rm -rf "$GNUPGHOME"
}
trap cleanup EXIT

if ! printf '%s' "$RELEASE_GPG_PRIVATE_KEY" | gpg --batch --import >/dev/null 2>&1; then
  echo 'Could not import the release signing subkey.' >&2
  exit 1
fi
unset RELEASE_GPG_PRIVATE_KEY

# Git invokes GPG itself; a private file descriptor keeps the passphrase out of arguments.
umask 077
printf '%s\n' "$RELEASE_GPG_PASSPHRASE" > "$GNUPGHOME/passphrase"
unset RELEASE_GPG_PASSPHRASE
cat > "$GNUPGHOME/sign" <<'SIGNER'
#!/usr/bin/env bash
exec gpg --batch --pinentry-mode loopback --passphrase-fd 3 "$@" 3< "$GNUPGHOME/passphrase"
SIGNER
chmod 700 "$GNUPGHOME/sign"

# The suffix forces this exact signing subkey rather than GPG's automatic key selection.
git -C "$checkout" \
  -c user.name=dhohner \
  -c user.email="$RELEASE_SIGNING_EMAIL" \
  -c user.signingkey="$RELEASE_SIGNING_KEY!" \
  -c gpg.format=openpgp \
  -c gpg.program="$GNUPGHOME/sign" \
  commit -S -s --cleanup=verbatim -F "$message"

git -C "$checkout" -c gpg.format=openpgp -c gpg.program=gpg verify-commit HEAD
