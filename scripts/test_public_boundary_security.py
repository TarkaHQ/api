from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import check_public_boundary
from check_public_boundary import (
    APPROVED_REMOTE_PLUGIN,
    contract_path_allowed,
    history_secret_findings,
    remote_plugin_findings,
    secret_findings,
)


class PublicBoundarySecretTests(unittest.TestCase):
    def test_detects_provider_credentials_without_returning_values(self) -> None:
        credential = "".join(("xsmtpsib-", "A" * 48))
        findings = secret_findings("fixture.txt", f"password={credential}".encode())

        self.assertEqual(findings, ["possible Brevo credential in fixture.txt:1"])
        self.assertNotIn(credential, repr(findings))

    def test_detects_multiline_private_keys(self) -> None:
        header = "".join(("-----BEGIN ", "PRIVATE KEY-----"))

        self.assertEqual(
            secret_findings("fixture.pem", f"comment\n{header}\nmaterial".encode()),
            ["possible private key in fixture.pem:2"],
        )

    def test_allows_documentation_placeholders(self) -> None:
        placeholders = "\n".join(
            ("Authorization: Bearer <token>", "tk_live_...", "sk-YOUR_KEY", "hf_example")
        )

        self.assertEqual(secret_findings("README.md", placeholders.encode()), [])

    def test_detects_ascii_credentials_inside_binary_files(self) -> None:
        credential = "".join(("cfat_", "B" * 48)).encode()

        findings = secret_findings("asset.bin", b"\x00" + credential)

        self.assertEqual(findings, ["possible Cloudflare API token in asset.bin:1"])
        self.assertNotIn(credential.decode(), repr(findings))

    def test_detects_credentials_removed_from_the_worktree(self) -> None:
        credential = "".join(("hf_", "C" * 40))
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
            subprocess.run(
                ["git", "config", "user.name", "Security Test"],
                cwd=repository,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.email", "security@test.invalid"],
                cwd=repository,
                check=True,
            )
            leaked = repository / "removed-contract.txt"
            leaked.write_text(f"token={credential}\n")
            subprocess.run(["git", "add", leaked.name], cwd=repository, check=True)
            subprocess.run(
                ["git", "commit", "-q", "-m", "add removed contract"],
                cwd=repository,
                check=True,
            )
            leaked.unlink()
            subprocess.run(["git", "add", "-u"], cwd=repository, check=True)
            subprocess.run(
                ["git", "commit", "-q", "-m", "remove contract"],
                cwd=repository,
                check=True,
            )

            findings = history_secret_findings(repository)

        self.assertEqual(len(findings), 1)
        self.assertIn("possible Hugging Face token in historical blob", findings[0])
        self.assertNotIn(credential, findings[0])

    def test_detects_credentials_removed_from_binary_history(self) -> None:
        credential = "".join(("cfat_", "D" * 48))
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
            subprocess.run(
                ["git", "config", "user.name", "Security Test"],
                cwd=repository,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.email", "security@test.invalid"],
                cwd=repository,
                check=True,
            )
            leaked = repository / "removed-binary.bin"
            leaked.write_bytes(b"\x00token=" + credential.encode() + b"\n")
            subprocess.run(["git", "add", leaked.name], cwd=repository, check=True)
            subprocess.run(
                ["git", "commit", "-q", "-m", "add removed binary"],
                cwd=repository,
                check=True,
            )
            leaked.unlink()
            subprocess.run(["git", "add", "-u"], cwd=repository, check=True)
            subprocess.run(
                ["git", "commit", "-q", "-m", "remove binary"],
                cwd=repository,
                check=True,
            )

            findings = history_secret_findings(repository)

        self.assertEqual(len(findings), 1)
        self.assertIn("possible Cloudflare API token in historical blob", findings[0])
        self.assertNotIn(credential, findings[0])

    def test_rejects_an_excessive_reachable_object_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
            subprocess.run(
                ["git", "config", "user.name", "Security Test"],
                cwd=repository,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.email", "security@test.invalid"],
                cwd=repository,
                check=True,
            )
            (repository / "contract.txt").write_text("bounded\n")
            subprocess.run(["git", "add", "."], cwd=repository, check=True)
            subprocess.run(
                ["git", "commit", "-q", "-m", "initial contract"],
                cwd=repository,
                check=True,
            )

            with patch.object(check_public_boundary, "MAX_HISTORY_OBJECTS", 1):
                with self.assertRaisesRegex(ValueError, "object count exceeds"):
                    history_secret_findings(repository)

    def test_rejects_an_oversized_historical_blob_before_reading(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
            subprocess.run(
                ["git", "config", "user.name", "Security Test"],
                cwd=repository,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.email", "security@test.invalid"],
                cwd=repository,
                check=True,
            )
            (repository / "contract.txt").write_text("ninebytes")
            subprocess.run(["git", "add", "."], cwd=repository, check=True)
            subprocess.run(
                ["git", "commit", "-q", "-m", "oversized contract"],
                cwd=repository,
                check=True,
            )

            with patch.object(check_public_boundary, "MAX_HISTORY_BLOB_BYTES", 8):
                with self.assertRaisesRegex(ValueError, "blob exceeds scanner limit"):
                    history_secret_findings(repository)

    def test_rejects_excessive_aggregate_historical_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
            subprocess.run(
                ["git", "config", "user.name", "Security Test"],
                cwd=repository,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.email", "security@test.invalid"],
                cwd=repository,
                check=True,
            )
            (repository / "contract.txt").write_text("bounded\n")
            subprocess.run(["git", "add", "."], cwd=repository, check=True)
            subprocess.run(
                ["git", "commit", "-q", "-m", "aggregate contract"],
                cwd=repository,
                check=True,
            )

            with patch.object(
                check_public_boundary, "MAX_HISTORY_TOTAL_BLOB_BYTES", 1
            ):
                with self.assertRaisesRegex(ValueError, "blob bytes exceed"):
                    history_secret_findings(repository)

    def test_allows_only_public_contract_file_types(self) -> None:
        self.assertTrue(contract_path_allowed("proto/tarka/inference/v2/api.proto"))
        self.assertTrue(contract_path_allowed("contracts/agent-hosts/catalog.json"))
        self.assertTrue(contract_path_allowed("scripts/validate_openapi.py"))
        self.assertFalse(contract_path_allowed("runtime/server.mjs"))
        self.assertFalse(contract_path_allowed("scripts/bootstrap.sh"))
        self.assertFalse(contract_path_allowed("contracts/runtime.wasm"))

    def test_rejects_unsafe_path_components(self) -> None:
        self.assertFalse(contract_path_allowed("contracts/bad\nname.json"))
        self.assertFalse(contract_path_allowed("contracts/path with space/spec.json"))

    def test_accepts_revision_pinned_approved_remote_plugin(self) -> None:
        content = (
            "version: v2\nplugins:\n"
            f"  - remote: {APPROVED_REMOTE_PLUGIN}\n"
            "    revision: 1\n"
            "    out: openapi\n"
        )

        self.assertEqual(remote_plugin_findings(content), [])

    def test_rejects_revisionless_remote_plugin(self) -> None:
        content = (
            "version: v2\nplugins:\n"
            f"  - remote: {APPROVED_REMOTE_PLUGIN}\n"
            "    out: openapi\n"
        )

        self.assertEqual(
            remote_plugin_findings(content),
            [
                "remote generator is not revision-pinned: "
                + APPROVED_REMOTE_PLUGIN
            ],
        )

    def test_rejects_unapproved_or_local_plugin(self) -> None:
        content = (
            "version: v2\nplugins:\n"
            "  - remote: buf.build/example/unreviewed:v1.0.0\n"
            "    revision: 1\n"
            "    out: openapi\n"
            "  - local: protoc-gen-example\n"
            "    out: generated\n"
        )

        self.assertEqual(
            remote_plugin_findings(content),
            [
                "unapproved remote generator: buf.build/example/unreviewed:v1.0.0",
                "only canonical remote protobuf generators are allowed",
            ],
        )


if __name__ == "__main__":
    unittest.main()
