from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any

from strict_json import load_json_object


ROOT = Path(__file__).resolve().parents[1]
CONTROL_CONTRACT = ROOT / "openapi" / "tarka-control-v1.swagger.json"
MAX_ALLOWED_MODEL_ALIASES = 128
MODEL_ALIAS_SCHEMA = {
    "type": "string",
    "pattern": r"^[a-z0-9][a-z0-9._/-]{1,126}[a-z0-9]$",
    "minLength": 3,
    "maxLength": 128,
}
REQUEST_SCHEMAS = (
    "ProvisioningServiceCreateApiKeyBody",
    "ProvisioningServiceUpdateQuotaPolicyBody",
)


class ControlRequestLimitTests(unittest.TestCase):
    def assert_allowed_model_aliases(self, schema: dict[str, Any]) -> None:
        aliases = schema["properties"]["allowed_model_aliases"]
        self.assertEqual(aliases.get("type"), "array")
        self.assertEqual(aliases.get("maxItems"), MAX_ALLOWED_MODEL_ALIASES)
        for keyword, expected in MODEL_ALIAS_SCHEMA.items():
            self.assertEqual(aliases["items"].get(keyword), expected)

    def test_model_allowlists_publish_exact_bounds(self) -> None:
        definitions = load_json_object(CONTROL_CONTRACT)["definitions"]
        for schema_name in REQUEST_SCHEMAS:
            with self.subTest(schema=schema_name):
                self.assert_allowed_model_aliases(definitions[schema_name])


if __name__ == "__main__":
    unittest.main()
