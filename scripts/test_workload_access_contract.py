"""Check the generated contract for platform access from compute workloads."""
import unittest
from pathlib import Path

from strict_json import load_json_object

ROOT = Path(__file__).resolve().parents[1]
ACCESS_PATH = "/control/v1/orgs/{org_id}/compute/workloads/{workload_id}/access"


class WorkloadAccessContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = load_json_object(ROOT / "openapi/tarka-control-v1.swagger.json")
        cls.definitions = cls.document["definitions"]

    def test_every_profile_shares_one_access_block_on_the_create_envelope(self):
        body = self.definitions["ProvisioningServiceCreateComputeWorkloadBody"]["properties"]
        self.assertEqual(body["access"]["$ref"], "#/definitions/v1WorkloadAccess")
        self.assertEqual(body["project_id"]["type"], "string")
        # The access block belongs to the envelope, never to a single profile.
        for profile in ("v1CreateAgentHostRequest", "v1CreateJobRequest", "v1CreateCodeSandboxRequest", "v1HTTPServiceSpec"):
            self.assertNotIn("access", self.definitions[profile]["properties"])
        workload = self.definitions["v1ComputeWorkload"]["properties"]
        self.assertEqual(workload["access"]["$ref"], "#/definitions/v1WorkloadAccess")

    def test_access_names_inference_databases_and_identity(self):
        access = self.definitions["v1WorkloadAccess"]["properties"]
        self.assertEqual(set(access), {"version", "inference", "databases", "identity"})
        inference = self.definitions["v1WorkloadInferenceAccess"]["properties"]
        self.assertEqual(set(inference), {"enabled", "allowed_models"})
        databases = self.definitions["v1WorkloadDatabaseAccess"]["properties"]
        self.assertEqual(set(databases), {"enabled", "mode", "own", "project_default", "grants"})
        self.assertEqual(databases["grants"]["items"]["$ref"], "#/definitions/v1WorkloadDatabaseGrant")
        grant = self.definitions["v1WorkloadDatabaseGrant"]["properties"]
        self.assertEqual(set(grant), {"database", "actions"})
        self.assertEqual(set(self.definitions["v1WorkloadIdentity"]["properties"]), {"principal_id"})

    def test_access_is_read_and_replaced_per_workload_with_a_version(self):
        operations = self.document["paths"][ACCESS_PATH]
        self.assertEqual(set(operations), {"get", "put"})
        for method in ("get", "put"):
            operation = operations[method]
            paths = {p["name"] for p in operation["parameters"] if p["in"] == "path"}
            self.assertEqual(paths, {"org_id", "workload_id"})
            self.assertEqual(operation["responses"]["200"]["schema"]["$ref"], "#/definitions/v1WorkloadAccess")
            self.assertEqual(operation.get("security", self.document["security"]), [{"bearerAuth": []}])
        body = self.definitions["ProvisioningServiceSetWorkloadAccessBody"]["properties"]
        self.assertEqual(set(body), {"access", "expected_version"})

    def test_databases_report_ownership_and_schema_mode(self):
        database = self.definitions["v1ManagedDatabase"]["properties"]
        for field in ("owner_workload_id", "project_default", "schema_mode"):
            self.assertIn(field, database)

    def test_manifest_returns_the_implicitly_defined_collections(self):
        manifest = self.definitions["v1DatabaseManifest"]["properties"]
        self.assertEqual(manifest["implicit_collections_json"]["type"], "string")
        self.assertEqual(manifest["implicit_collections_truncated"]["type"], "boolean")

    def test_in_workload_contract_documents_routes_header_and_errors(self):
        contract = (ROOT / "contracts/compute/README.md").read_text(encoding="utf-8")
        for required in (
            "http://tarka/v1",
            "http://tarka/database/api/*",
            "http://tarka/project/database/api/*",
            "http://tarka/databases/{name}/api/*",
            "Tarka-Workload: 1",
            "platform_header_required",
            "forwarded_request_refused",
            "capability_disabled",
            "workload_unbound",
            "database_starting",
        ):
            self.assertIn(required, contract)


if __name__ == "__main__":
    unittest.main()
