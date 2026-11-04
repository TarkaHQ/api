from __future__ import annotations

import unittest

from validate_openapi import (
    INFERENCE_PATH,
    INFERENCE_V2_OPENAPI_PATH,
    INFERENCE_GRPC_PATH,
    load,
)


class AudioTemperatureLimitTests(unittest.TestCase):
    def test_authored_rest_contracts_publish_temperature_range(self) -> None:
        for path in (INFERENCE_PATH, INFERENCE_V2_OPENAPI_PATH):
            with self.subTest(path=path):
                schemas = load(path)["components"]["schemas"]
                for request_name in ("TranscriptionRequest", "TranslationRequest"):
                    with self.subTest(request=request_name):
                        temperature = schemas[request_name]["properties"]["temperature"]
                        self.assertEqual(temperature["minimum"], 0)
                        self.assertEqual(temperature["maximum"], 1)

    def test_generated_grpc_gateway_contract_publishes_temperature_range(self) -> None:
        definitions = load(INFERENCE_GRPC_PATH)["definitions"]
        for request_name in ("v1AudioTranscriptionRequest", "v1AudioTranslationRequest"):
            with self.subTest(request=request_name):
                temperature = definitions[request_name]["properties"]["temperature"]
                self.assertEqual(temperature["maximum"], 1)
                self.assertIn("0 through 1", temperature["description"])


if __name__ == "__main__":
    unittest.main()
