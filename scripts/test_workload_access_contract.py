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
        self.assertEqual(set(access), {"version", "inference", "databases", "identity", "storage", "git", "gateway", "compute", "environment"})
        inference = self.definitions["v1WorkloadInferenceAccess"]["properties"]
        self.assertEqual(set(inference), {"enabled", "allowed_models"})
        databases = self.definitions["v1WorkloadDatabaseAccess"]["properties"]
        self.assertEqual(set(databases), {"enabled", "mode", "own", "project_default", "grants"})
        self.assertEqual(databases["grants"]["items"]["$ref"], "#/definitions/v1WorkloadDatabaseGrant")
        grant = self.definitions["v1WorkloadDatabaseGrant"]["properties"]
        self.assertEqual(set(grant), {"database", "actions"})
        self.assertEqual(set(self.definitions["v1WorkloadIdentity"]["properties"]), {"principal_id", "act_as_invoking_user"})

    def test_storage_and_git_are_switched_on_and_granted_by_name(self):
        access = self.definitions["v1WorkloadAccess"]["properties"]
        self.assertEqual(access["storage"]["$ref"], "#/definitions/v1WorkloadStorageAccess")
        self.assertEqual(access["git"]["$ref"], "#/definitions/v1WorkloadGitAccess")
        for capability, grant, target in (("Storage", "v1WorkloadStorageGrant", "bucket"), ("Git", "v1WorkloadGitGrant", "repository")):
            block = self.definitions[f"v1Workload{capability}Access"]["properties"]
            self.assertEqual(set(block), {"enabled", "grants"})
            self.assertEqual(block["enabled"]["type"], "boolean")
            self.assertEqual(block["grants"]["items"]["$ref"], f"#/definitions/{grant}")
            self.assertEqual(set(self.definitions[grant]["properties"]), {target, "actions"})
            self.assertEqual(self.definitions[grant]["properties"]["actions"]["items"]["type"], "string")

    def test_capabilities_keep_their_field_numbers(self):
        proto = (ROOT / "proto/tarka/provisioning/v1/container.proto").read_text(encoding="utf-8")
        message = proto.split("message WorkloadAccess {", 1)[1].split("}", 1)[0]
        self.assertIn("WorkloadStorageAccess storage = 5;", message)
        self.assertIn("WorkloadGitAccess git = 6;", message)
        self.assertIn("WorkloadGatewayAccess gateway = 7;", message)
        self.assertIn("WorkloadComputeAccess compute = 8;", message)
        self.assertIn("WorkloadEnvironmentAccess environment = 9;", message)
        self.assertNotIn("= 10;", message)
        identity = proto.split("message WorkloadIdentity {", 1)[1].split("}", 1)[0]
        self.assertIn("optional bool act_as_invoking_user = 2;", identity)

    def test_gateway_compute_and_environment_are_switched_on_and_named(self):
        access = self.definitions["v1WorkloadAccess"]["properties"]
        self.assertEqual(access["gateway"]["$ref"], "#/definitions/v1WorkloadGatewayAccess")
        self.assertEqual(access["compute"]["$ref"], "#/definitions/v1WorkloadComputeAccess")
        self.assertEqual(access["environment"]["$ref"], "#/definitions/v1WorkloadEnvironmentAccess")
        gateway = self.definitions["v1WorkloadGatewayAccess"]["properties"]
        self.assertEqual(set(gateway), {"enabled", "gateways"})
        compute = self.definitions["v1WorkloadComputeAccess"]["properties"]
        self.assertEqual(set(compute), {"enabled", "functions", "jobs", "sessions"})
        self.assertEqual(compute["jobs"]["type"], "boolean")
        self.assertEqual(compute["sessions"]["type"], "boolean")
        environment = self.definitions["v1WorkloadEnvironmentAccess"]["properties"]
        self.assertEqual(set(environment), {"enabled", "secrets"})
        for block, field in ((gateway, "gateways"), (compute, "functions"), (environment, "secrets")):
            self.assertEqual(block["enabled"]["type"], "boolean")
            self.assertEqual(block[field]["items"]["type"], "string")

    def test_project_secrets_are_write_only(self):
        secret = self.definitions["v1ProjectSecret"]["properties"]
        self.assertEqual(set(secret), {"project_id", "name", "version", "created_at", "updated_at"})
        collection = "/control/v1/orgs/{org_id}/projects/{project_id}/secrets"
        self.assertEqual(set(self.document["paths"][collection]), {"get"})
        item = self.document["paths"][collection + "/{name}"]
        self.assertEqual(set(item), {"put", "delete"})
        body = self.definitions["ProvisioningServiceSetProjectSecretBody"]["properties"]
        self.assertEqual(set(body), {"value", "expected_version"})
        self.assertEqual(body["value"].get("format"), "password")
        self.assertEqual(body["value"].get("maxLength"), 65536)
        for method in ("put", "delete"):
            self.assertEqual(item[method]["responses"]["200"]["schema"]["$ref"], "#/definitions/v1ProjectSecret")

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

    def test_in_workload_contract_documents_storage_and_git(self):
        contract = (ROOT / "contracts/compute/README.md").read_text(encoding="utf-8")
        for required in (
            "http://tarka/storage/{bucket}/{key}",
            "POST http://tarka/storage/{bucket}/{key}:presign",
            "http://tarka/git/{repository}.git/*",
            "info/refs?service=git-upload-pack",
            "git-receive-pack",
            "| `storage` | disabled | disabled |",
            "| `git` | disabled | disabled |",
            "http.http://tarka/.extraHeader",
            "GIT_CONFIG_COUNT",
            "bucket_not_found",
            "object_not_found",
            "repository_not_found",
            "length_required",
            "payload_too_large",
            "precondition_failed",
            "range_not_satisfiable",
        ):
            self.assertIn(required, contract)
        self.assertNotIn("Object storage, Hosted Git", contract)

    def test_in_workload_contract_documents_gateway_compute_secrets_and_delegation(self):
        contract = (ROOT / "contracts/compute/README.md").read_text(encoding="utf-8")
        for required in (
            "http://tarka/mcp",
            "http://tarka/gateways/{gateway}/mcp",
            "http://tarka/compute/functions/{name}/*",
            "POST /compute/jobs/{name}/runs",
            "POST /compute/sessions/{session_id}/exec",
            "GET http://tarka/environment",
            "GET http://tarka/secrets/{name}",
            "Tarka-Act-As: invoking-user",
            "Tarka-Call-Depth",
            "| `gateway` | disabled | disabled |",
            "| `compute` | disabled | disabled |",
            "| `environment` | disabled | disabled |",
            "gateway_not_found",
            "gateway_required",
            "identity_required",
            "function_not_found",
            "job_run_active",
            "session_not_found",
            "secret_not_found",
            "invoking_user_unavailable",
            "call_depth_exceeded",
            "rate_limited",
        ):
            self.assertIn(required, contract)
        self.assertNotIn("not part of this\ncontract yet", contract)


if __name__ == "__main__":
    unittest.main()
