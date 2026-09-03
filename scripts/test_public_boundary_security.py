from __future__ import annotations

import unittest

from check_public_boundary import secret_findings


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


if __name__ == "__main__":
    unittest.main()
