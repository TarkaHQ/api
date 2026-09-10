from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any

from strict_json import load_json_object


ROOT = Path(__file__).resolve().parents[1]
AUTHORED_CONTRACTS = (
    ROOT / "openapi" / "tarka-inference-v1.openapi.json",
    ROOT / "openapi" / "tarka-inference-v2.openapi.json",
)
GENERATED_CONTRACT = ROOT / "openapi" / "tarka-inference-v2.swagger.json"

FIELD_LIMITS = {
    "ChatCompletionRequest": {
        "max_tokens": {"minimum": 1, "maximum": 32768},
        "max_completion_tokens": {"minimum": 1, "maximum": 32768},
        "n": {"minimum": 1, "maximum": 8},
    },
    "SpeechRequest": {
        "input": {"minLength": 1, "maxLength": 4096},
        "instructions": {"maxLength": 4096},
    },
    "VoiceCloneRequest": {
        "name": {"minLength": 1, "maxLength": 255},
        "consent_signed_by": {"minLength": 1, "maxLength": 255},
    },
}

UTF8_BYTE_LIMITS = {
    "SpeechRequest": {"input": 4096, "instructions": 4096},
    "VoiceCloneRequest": {"name": 255, "consent_signed_by": 255},
}

GENERATED_ONLY_LIMITS = {
    "v2VoiceCloneRequest": {
        "filename": {"maxLength": 255},
        "content_type": {"maxLength": 255},
    }
}


def assert_limits(
    testcase: unittest.TestCase,
    schemas: dict[str, Any],
    *,
    generated: bool,
) -> None:
    for schema_name, fields in FIELD_LIMITS.items():
        resolved_name = f"v2{schema_name}" if generated else schema_name
        properties = schemas[resolved_name]["properties"]
        for field_name, expected in fields.items():
            with testcase.subTest(schema=resolved_name, field=field_name):
                field = properties[field_name]
                for keyword, value in expected.items():
                    testcase.assertEqual(field.get(keyword), value)


class InferenceRequestLimitContractTests(unittest.TestCase):
    def test_authored_contracts_publish_server_enforced_limits(self) -> None:
        for path in AUTHORED_CONTRACTS:
            with self.subTest(path=path.name):
                document = load_json_object(path)
                assert_limits(self, document["components"]["schemas"], generated=False)
                sample = document["components"]["schemas"]["VoiceCloneRequest"][
                    "properties"
                ]["sample"]
                self.assertEqual(sample.get("x-tarka-max-bytes"), 30 * 1024 * 1024)
                for schema_name, fields in UTF8_BYTE_LIMITS.items():
                    properties = document["components"]["schemas"][schema_name][
                        "properties"
                    ]
                    for field_name, expected in fields.items():
                        with self.subTest(
                            path=path.name, schema=schema_name, field=field_name
                        ):
                            self.assertEqual(
                                properties[field_name].get("x-tarka-max-bytes"),
                                expected,
                            )

    def test_generated_contract_preserves_typed_rpc_limits(self) -> None:
        document = load_json_object(GENERATED_CONTRACT)
        definitions = document["definitions"]
        assert_limits(self, definitions, generated=True)
        for schema_name, fields in GENERATED_ONLY_LIMITS.items():
            properties = definitions[schema_name]["properties"]
            for field_name, expected in fields.items():
                with self.subTest(schema=schema_name, field=field_name):
                    for keyword, value in expected.items():
                        self.assertEqual(properties[field_name].get(keyword), value)


if __name__ == "__main__":
    unittest.main()
