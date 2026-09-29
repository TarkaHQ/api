from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any

from strict_json import load_json_object


ROOT = Path(__file__).resolve().parents[1]
AUTHORED_CONTRACTS = (
    (ROOT / "openapi" / "tarka-inference-v1.openapi.json", "v1"),
    (ROOT / "openapi" / "tarka-inference-v2.openapi.json", "v2"),
)
GENERATED_CONTRACT = ROOT / "openapi" / "tarka-inference-v2.swagger.json"

AUTHORED_MODEL_REQUEST_SCHEMAS = (
    "ChatCompletionRequest",
    "ResponseCreateRequest",
    "OCRRequest",
    "DocumentLayoutRequest",
    "TranscriptionRequest",
    "TranslationRequest",
    "SpeechRequest",
    "VoiceCloneRequest",
)
GENERATED_MODEL_REQUEST_SCHEMAS = (
    "v2ChatCompletionRequest",
    "v2OCRRequest",
    "v2DocumentLayoutRequest",
    "v2AudioTranscriptionRequest",
    "v2AudioTranslationRequest",
    "v2SpeechRequest",
    "v2VoiceCloneRequest",
)

IDENTIFIERS = {
    "model": {
        "pattern": r"^[a-z0-9][a-z0-9._/-]{1,126}[a-z0-9]$",
        "minLength": 3,
        "maxLength": 128,
    },
    "response_id": {
        "pattern": r"^resp_[A-Za-z0-9_-]{16,128}$",
        "minLength": 21,
        "maxLength": 133,
    },
    "voice_id": {
        "pattern": r"^voice_[0-9a-f]{32}$",
        "minLength": 38,
        "maxLength": 38,
    },
}


def operation_parameter(
    document: dict[str, Any], route: str, method: str, name: str
) -> dict[str, Any]:
    path_item = document["paths"][route]
    operation = path_item[method]
    parameters = [
        parameter
        for parameter in (
            *path_item.get("parameters", []),
            *operation.get("parameters", []),
        )
        if parameter.get("in") == "path" and parameter.get("name") == name
    ]
    if len(parameters) != 1:
        raise AssertionError(
            f"{method.upper()} {route}: expected exactly one {name} path parameter, "
            f"got {len(parameters)}"
        )
    return parameters[0]


class IdentifierContractTests(unittest.TestCase):
    def assert_model_alias_schema(self, schema: dict[str, Any]) -> None:
        for keyword, expected in IDENTIFIERS["model"].items():
            self.assertEqual(schema.get(keyword), expected)

    def assert_identifier(
        self,
        document: dict[str, Any],
        route: str,
        method: str,
        name: str,
        *,
        openapi3: bool,
    ) -> None:
        parameter = operation_parameter(document, route, method, name)
        self.assertIs(parameter.get("required"), True)
        schema = parameter["schema"] if openapi3 else parameter
        self.assertEqual(schema.get("type"), "string")
        self.assertEqual(schema.get("pattern"), IDENTIFIERS[name]["pattern"])
        if openapi3:
            self.assertEqual(
                schema.get("minLength"), IDENTIFIERS[name]["minLength"]
            )
            self.assertEqual(
                schema.get("maxLength"), IDENTIFIERS[name]["maxLength"]
            )

    def assert_version(
        self, document: dict[str, Any], version: str, *, openapi3: bool
    ) -> None:
        expectations = (
            (f"/{version}/models/{{model}}", "get", "model"),
            (f"/{version}/responses/{{response_id}}", "get", "response_id"),
            (f"/{version}/responses/{{response_id}}", "delete", "response_id"),
            (
                f"/{version}/responses/{{response_id}}/cancel",
                "post",
                "response_id",
            ),
            (f"/{version}/audio/voice-clones/{{voice_id}}", "get", "voice_id"),
            (f"/{version}/audio/voice-clones/{{voice_id}}", "delete", "voice_id"),
        )
        for route, method, name in expectations:
            with self.subTest(
                version=version, route=route, method=method, name=name
            ):
                self.assert_identifier(
                    document, route, method, name, openapi3=openapi3
                )

    def test_authored_contracts_publish_exact_identifier_bounds(self) -> None:
        for path, version in AUTHORED_CONTRACTS:
            with self.subTest(path=path.name):
                self.assert_version(load_json_object(path), version, openapi3=True)

    def test_generated_contract_preserves_bounded_identifier_patterns(self) -> None:
        # grpc-gateway's Swagger 2 generator does not emit minLength/maxLength
        # for path parameters. These anchored patterns encode the same bounds,
        # and guard both the v1 compatibility routes and the v2 routes.
        document = load_json_object(GENERATED_CONTRACT)
        for version in ("v1", "v2"):
            self.assert_version(document, version, openapi3=False)

    def test_authored_requests_publish_model_alias_bounds(self) -> None:
        for path, _ in AUTHORED_CONTRACTS:
            schemas = load_json_object(path)["components"]["schemas"]
            for schema_name in AUTHORED_MODEL_REQUEST_SCHEMAS:
                with self.subTest(path=path.name, schema=schema_name):
                    self.assert_model_alias_schema(
                        schemas[schema_name]["properties"]["model"]
                    )

    def test_generated_requests_preserve_model_alias_bounds(self) -> None:
        definitions = load_json_object(GENERATED_CONTRACT)["definitions"]
        for schema_name in GENERATED_MODEL_REQUEST_SCHEMAS:
            with self.subTest(schema=schema_name):
                self.assert_model_alias_schema(
                    definitions[schema_name]["properties"]["model"]
                )


if __name__ == "__main__":
    unittest.main()
