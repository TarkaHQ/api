from pathlib import Path
import unittest

from strict_json import load_json_object

ROOT = Path(__file__).resolve().parents[1]


class AgentHostModelEndpointContract(unittest.TestCase):
    def definitions(self):
        return load_json_object(ROOT / "openapi/tarka-control-v1.swagger.json")["definitions"]

    def test_runtime_configuration_offers_an_endpoint_beside_the_tarka_alias(self):
        runtime = self.definitions()["v1AgentHostRuntimeConfiguration"]["properties"]
        self.assertIn("primary_model_alias", runtime)
        self.assertEqual(runtime["model_endpoint"]["$ref"], "#/definitions/v1AgentHostModelEndpoint")
        self.assertIn("Mutually exclusive", runtime["model_endpoint"]["description"])

    def test_endpoint_fields_are_bounded_and_the_key_is_write_only(self):
        endpoint = self.definitions()["v1AgentHostModelEndpoint"]["properties"]
        self.assertEqual(set(endpoint), {"base_url", "model", "api_key", "preserve_existing_api_key"})
        self.assertEqual(endpoint["base_url"]["maxLength"], 512)
        self.assertEqual(endpoint["model"]["maxLength"], 256)
        self.assertEqual(endpoint["model"]["pattern"], "^[!-~]{1,256}$")
        self.assertEqual(endpoint["api_key"]["format"], "password")
        self.assertEqual(endpoint["api_key"]["maxLength"], 4096)
        self.assertEqual(endpoint["preserve_existing_api_key"]["type"], "boolean")

    def test_configuration_reads_return_the_same_runtime_shape(self):
        definitions = self.definitions()
        configuration = definitions["v1AgentHostConfiguration"]["properties"]
        self.assertEqual(configuration["runtime"]["$ref"], "#/definitions/v1AgentHostRuntimeConfiguration")
        create = definitions["ProvisioningServiceCreateAgentHostBody"]["properties"]
        self.assertEqual(create["runtime"]["$ref"], "#/definitions/v1AgentHostRuntimeConfiguration")


if __name__ == "__main__":
    unittest.main()
