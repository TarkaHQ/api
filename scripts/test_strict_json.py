from __future__ import annotations

import unittest
from pathlib import Path

from strict_json import loads_json_object


class StrictJSONTests(unittest.TestCase):
    def test_accepts_unique_nested_object_keys(self) -> None:
        self.assertEqual(
            loads_json_object(
                '{"security":{"bearerAuth":[]}}',
                Path("contract.json"),
            ),
            {"security": {"bearerAuth": []}},
        )

    def test_rejects_duplicate_nested_object_keys(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "duplicate JSON object key 'security'",
        ):
            loads_json_object(
                '{"components":{"security":{},"security":{"disabled":true}}}',
                Path("contract.json"),
            )

    def test_rejects_non_object_contract_root(self) -> None:
        with self.assertRaisesRegex(ValueError, "document root must be an object"):
            loads_json_object("[]", Path("contract.json"))

    def test_invalid_json_error_does_not_echo_document_contents(self) -> None:
        secret = "never-echo-this-value"
        with self.assertRaises(ValueError) as caught:
            loads_json_object('{"secret":"' + secret + '"', Path("contract.json"))

        self.assertNotIn(secret, str(caught.exception))


if __name__ == "__main__":
    unittest.main()
