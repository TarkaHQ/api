from __future__ import annotations

import unittest

from check_public_boundary import (
    APPROVED_REMOTE_PLUGIN,
    contract_path_allowed,
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

    def test_ignores_binary_files(self) -> None:
        credential = "".join(("cfat_", "B" * 48)).encode()

        self.assertEqual(secret_findings("asset.bin", b"\x00" + credential), [])

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
