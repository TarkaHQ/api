from __future__ import annotations

import unittest

from check_public_boundary import contract_path_allowed, secret_findings


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


if __name__ == "__main__":
    unittest.main()
