from __future__ import annotations

import os
import secrets
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SIGNER = ROOT / "tools/release/sign.sh"
EMAIL = "43063759+dhohner@users.noreply.github.com"


class SigningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(prefix="clankers-sign-", dir="/tmp")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.key_home = cls.root / "keys"
        cls.key_home.mkdir(mode=0o700)
        cls.passphrase = secrets.token_urlsafe(24)
        cls.environment = {
            **os.environ,
            "GNUPGHOME": str(cls.key_home),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
        }
        cls.addClassCleanup(
            subprocess.run,
            ["gpgconf", "--homedir", str(cls.key_home), "--kill", "gpg-agent"],
            capture_output=True,
            check=False,
            timeout=10,
        )
        cls.gpg(
            "--quick-generate-key",
            f"dhohner (Release test) <{EMAIL}>",
            "ed25519",
            "cert",
            "1d",
        )
        cls.primary = cls.fingerprints()[0]
        cls.gpg("--quick-add-key", cls.primary, "ed25519", "sign", "1d")
        cls.subkey = cls.fingerprints()[1]
        cls.private_key = cls.gpg(
            "--armor", "--export-secret-subkeys", cls.subkey + "!"
        )

    @classmethod
    def gpg(cls, *args: str) -> str:
        result = subprocess.run(
            [
                "gpg",
                "--batch",
                "--pinentry-mode",
                "loopback",
                "--passphrase-fd",
                "0",
                *args,
            ],
            input=cls.passphrase + "\n",
            env=cls.environment,
            text=True,
            capture_output=True,
            check=True,
            timeout=30,
        )
        return result.stdout

    @classmethod
    def fingerprints(cls) -> list[str]:
        listing = cls.gpg(
            "--with-colons", "--with-subkey-fingerprint", "--list-secret-keys"
        )
        return [
            line.split(":")[9]
            for line in listing.splitlines()
            if line.startswith("fpr:")
        ]

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(dir=self.root)
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.checkout = self.directory / "distribution"
        self.signing_temp = self.directory / "signing"
        self.signing_temp.mkdir()
        self.env = {
            **self.environment,
            "TMPDIR": str(self.signing_temp),
            "RELEASE_GPG_PRIVATE_KEY": self.private_key,
            "RELEASE_GPG_PASSPHRASE": self.passphrase,
            "RELEASE_SIGNING_KEY": self.subkey,
            "RELEASE_SIGNING_EMAIL": EMAIL,
            "SOURCE_REVISION": "1" * 40,
        }
        self.git("init", "--quiet", str(self.checkout))

    def git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(self.directory), *args],
            env=self.env,
            text=True,
            capture_output=True,
            check=True,
            timeout=15,
        )

    def stage(self) -> None:
        (self.checkout / "SOURCE_REVISION").write_text(
            "1" * 40 + "\n", encoding="utf-8"
        )
        self.git("-C", str(self.checkout), "add", "--all")

    def sign(self) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            ["bash", str(SIGNER), str(self.checkout)],
            env=self.env,
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
        self.assertEqual(
            list(self.signing_temp.iterdir()), [], "Signing keyring was not removed"
        )
        output = result.stdout + result.stderr
        self.assertFalse(
            self.private_key in output, "Private key appeared in signing output"
        )
        self.assertFalse(
            self.passphrase in output, "Passphrase appeared in signing output"
        )
        return result

    def assert_no_commit(self) -> None:
        result = subprocess.run(
            ["git", "-C", str(self.checkout), "rev-parse", "--verify", "HEAD"],
            env=self.env,
            capture_output=True,
            check=False,
            timeout=10,
        )
        self.assertNotEqual(result.returncode, 0)

    def test_signs_with_exported_subkey_and_verified_email(self) -> None:
        self.stage()
        result = self.sign()
        self.assertEqual(result.returncode, 0, result.stderr)
        verified = self.git(
            "-C",
            str(self.checkout),
            "-c",
            "gpg.program=gpg",
            "-c",
            "gpg.format=openpgp",
            "verify-commit",
            "--raw",
            "HEAD",
        )
        self.assertIn("[GNUPG:] VALIDSIG " + self.subkey, verified.stderr)
        identities = self.git(
            "-C",
            str(self.checkout),
            "log",
            "-1",
            "--format=%an <%ae>%n%cn <%ce>",
        ).stdout.splitlines()
        self.assertEqual(identities, [f"dhohner <{EMAIL}>"] * 2)
        message = self.git("-C", str(self.checkout), "log", "-1", "--format=%B").stdout
        self.assertEqual(message.splitlines()[0], "release: clankers 1111111")
        self.assertEqual(
            message.strip().splitlines()[-1], f"Signed-off-by: dhohner <{EMAIL}>"
        )

    def test_wrong_passphrase_fails_without_creating_a_commit(self) -> None:
        self.stage()
        self.env["RELEASE_GPG_PASSPHRASE"] = secrets.token_urlsafe(24)
        self.assertNotEqual(self.sign().returncode, 0)
        self.assert_no_commit()

    def test_invalid_key_fails_without_creating_a_commit(self) -> None:
        self.stage()
        self.env["RELEASE_GPG_PRIVATE_KEY"] = "invalid private key"
        result = self.sign()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Could not import", result.stderr)
        self.assert_no_commit()

    def test_missing_secret_fails_without_creating_a_commit(self) -> None:
        self.stage()
        del self.env["RELEASE_GPG_PASSPHRASE"]
        self.assertNotEqual(self.sign().returncode, 0)
        self.assert_no_commit()

    def test_no_changes_need_no_signing_secrets(self) -> None:
        del self.env["RELEASE_GPG_PRIVATE_KEY"]
        del self.env["RELEASE_GPG_PASSPHRASE"]
        result = self.sign()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("already matches", result.stdout)
        self.assert_no_commit()


if __name__ == "__main__":
    unittest.main()
