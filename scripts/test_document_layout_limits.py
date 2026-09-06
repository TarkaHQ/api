from __future__ import annotations

import unittest

from validate_openapi import (
    INFERENCE_PATH,
    INFERENCE_V2_OPENAPI_PATH,
    INFERENCE_V2_PATH,
    load,
)


MAX_ENCODED_IMAGE_BYTES = 44_740_268
MAX_LABELS = 64
MAX_LABEL_CHARACTERS = 64
MAX_EXTRA_BODY_BYTES = 16_384


class DocumentLayoutLimitTests(unittest.TestCase):
    def test_authored_rest_contracts_publish_resource_limits(self) -> None:
        for path in (INFERENCE_PATH, INFERENCE_V2_OPENAPI_PATH):
            with self.subTest(path=path):
                request = load(path)["components"]["schemas"]["DocumentLayoutRequest"]
                properties = request["properties"]
                self.assertEqual(properties["image"]["minLength"], 1)
                self.assertEqual(properties["image"]["maxLength"], MAX_ENCODED_IMAGE_BYTES)
                self.assertEqual(properties["labels"]["maxItems"], MAX_LABELS)
                self.assertTrue(properties["labels"]["uniqueItems"])
                self.assertEqual(properties["labels"]["items"]["minLength"], 1)
                self.assertEqual(
                    properties["labels"]["items"]["maxLength"],
                    MAX_LABEL_CHARACTERS,
                )
                self.assertEqual(
                    properties["extra_body"]["x-tarka-max-serialized-bytes"],
                    MAX_EXTRA_BODY_BYTES,
                )

    def test_generated_grpc_gateway_contract_publishes_field_limits(self) -> None:
        request = load(INFERENCE_V2_PATH)["definitions"]["v2DocumentLayoutRequest"]
        properties = request["properties"]
        self.assertEqual(properties["image"]["minLength"], 1)
        self.assertEqual(properties["image"]["maxLength"], MAX_ENCODED_IMAGE_BYTES)
        self.assertEqual(properties["labels"]["maxItems"], MAX_LABELS)
        self.assertTrue(properties["labels"]["uniqueItems"])
        self.assertEqual(properties["labels"]["items"]["minLength"], 1)
        self.assertEqual(
            properties["labels"]["items"]["maxLength"],
            MAX_LABEL_CHARACTERS,
        )
        self.assertIn("16 KiB", properties["extra_body"]["description"])


if __name__ == "__main__":
    unittest.main()
