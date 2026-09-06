from __future__ import annotations

import unittest

from validate_openapi import (
    INFERENCE_PATH,
    INFERENCE_V2_OPENAPI_PATH,
    INFERENCE_V2_PATH,
    load,
)


MAX_ENCODED_IMAGE_BYTES = 44_740_268
MAX_IMAGES = 32
MAX_REST_JSON_BYTES = 8_388_608


class OCRLimitTests(unittest.TestCase):
    def test_authored_rest_contracts_publish_resource_limits(self) -> None:
        for path in (INFERENCE_PATH, INFERENCE_V2_OPENAPI_PATH):
            with self.subTest(path=path):
                request = load(path)["components"]["schemas"]["OCRRequest"]
                properties = request["properties"]
                self.assertEqual(
                    request["oneOf"],
                    [{"required": ["image"]}, {"required": ["images"]}],
                )
                self.assertNotIn("anyOf", request)
                self.assertEqual(
                    request["x-tarka-max-rest-json-bytes"],
                    MAX_REST_JSON_BYTES,
                )
                self.assertIn("8 MiB", request["description"])
                self.assertEqual(properties["image"]["minLength"], 1)
                self.assertEqual(
                    properties["image"]["maxLength"],
                    MAX_ENCODED_IMAGE_BYTES,
                )
                self.assertEqual(properties["images"]["minItems"], 1)
                self.assertEqual(properties["images"]["maxItems"], MAX_IMAGES)
                self.assertEqual(properties["images"]["items"]["minLength"], 1)
                self.assertEqual(
                    properties["images"]["items"]["maxLength"],
                    MAX_ENCODED_IMAGE_BYTES,
                )

    def test_generated_grpc_gateway_contract_publishes_resource_limits(self) -> None:
        request = load(INFERENCE_V2_PATH)["definitions"]["v2OCRRequest"]
        properties = request["properties"]
        self.assertIn("8 MiB", request["description"])
        self.assertEqual(properties["image"]["minLength"], 1)
        self.assertEqual(
            properties["image"]["maxLength"],
            MAX_ENCODED_IMAGE_BYTES,
        )
        self.assertEqual(properties["images"]["maxItems"], MAX_IMAGES)
        self.assertEqual(properties["images"]["items"]["minLength"], 1)
        self.assertEqual(
            properties["images"]["items"]["maxLength"],
            MAX_ENCODED_IMAGE_BYTES,
        )


if __name__ == "__main__":
    unittest.main()
