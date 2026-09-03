from __future__ import annotations

import copy
import unittest

from validate_openapi import (
    CONTROL_PATH,
    INFERENCE_PATH,
    load,
    validate_authenticated_tls_surface,
)


class OpenAPISecurityTests(unittest.TestCase):
    def test_rejects_query_string_credentials_in_openapi(self) -> None:
        document = copy.deepcopy(load(INFERENCE_PATH))
        document["components"]["securitySchemes"]["bearerAuth"] = {
            "type": "apiKey",
            "in": "query",
            "name": "api_key",
        }

        with self.assertRaisesRegex(ValueError, "HTTP bearer scheme"):
            validate_authenticated_tls_surface(document, INFERENCE_PATH)

    def test_rejects_nonstandard_authorization_header_in_swagger(self) -> None:
        document = copy.deepcopy(load(CONTROL_PATH))
        document["securityDefinitions"]["bearerAuth"]["name"] = "X-Api-Key"

        with self.assertRaisesRegex(ValueError, "Authorization header"):
            validate_authenticated_tls_surface(document, CONTROL_PATH)


if __name__ == "__main__":
    unittest.main()
