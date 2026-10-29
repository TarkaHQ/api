from pathlib import Path
import unittest

from strict_json import load_json_object

ROOT = Path(__file__).resolve().parents[1]


class RegistryCredentialContracts(unittest.TestCase):
    def test_registry_tests_have_org_scoped_lifecycle_routes(self):
        contract = load_json_object(ROOT / "openapi/tarka-control-v1.swagger.json")
        root = "/control/v1/orgs/{org_id}/agent-host-registry-tests"
        self.assertIn("post", contract["paths"][root])
        for method in ("get", "delete"):
            self.assertIn(method, contract["paths"][root + "/{test_id}"])

    def test_secret_input_is_bounded_and_not_part_of_read_responses(self):
        definitions = load_json_object(ROOT / "openapi/tarka-control-v1.swagger.json")["definitions"]
        secret = definitions["v1AgentHostRegistryCredentialInput"]["properties"]["token"]
        self.assertEqual(secret["format"], "password")
        self.assertEqual(secret["maxLength"], 4096)
        metadata = definitions["v1AgentHostRegistryCredential"]["properties"]
        self.assertNotIn("token", metadata)
        result = definitions["v1AgentHostRegistryTest"]["properties"]["credentials"]
        self.assertEqual(result["items"]["$ref"], "#/definitions/v1AgentHostRegistryCredential")

    def test_host_apply_uses_test_reference_and_keeps_legacy_input(self):
        definitions = load_json_object(ROOT / "openapi/tarka-control-v1.swagger.json")["definitions"]
        properties = definitions["ProvisioningServiceCreateAgentHostBody"]["properties"]
        self.assertIn("registry_test_id", properties)
        self.assertIn("github_registry_credentials", properties)


if __name__ == "__main__":
    unittest.main()
