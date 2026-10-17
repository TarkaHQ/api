"""Check the generated public contract's retry, placement and result boundaries."""
import unittest
from pathlib import Path

from strict_json import load_json_object

ROOT = Path(__file__).resolve().parents[1]


class ComputeLifecycleContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = load_json_object(ROOT / "openapi/tarka-control-v1.swagger.json")
        cls.definitions = cls.document["definitions"]

    def test_create_stays_wire_compatible_and_adds_typed_admission(self):
        create = self.document["paths"]["/control/v1/orgs/{org_id}/jobs"]["post"]
        self.assertEqual(create["responses"]["200"]["schema"]["$ref"], "#/definitions/v1ProvisionedResource")
        body = self.definitions["ProvisioningServiceCreateJobBody"]["properties"]
        self.assertEqual(body["resources"]["$ref"], "#/definitions/v1JobResources")
        self.assertEqual(body["retry_policy"]["$ref"], "#/definitions/v1JobRetryPolicy")
        self.assertEqual(body["queue_timeout_seconds"]["maximum"], 3600)
        self.assertEqual(body["idempotency_key"]["maxLength"], 128)
        self.assertIn("location", body)
        self.assertIn("latest_run_id", self.definitions["v1ProvisionedResource"]["properties"])

    def test_resources_retries_and_history_have_published_bounds(self):
        resources = self.definitions["v1JobResources"]["properties"]
        for field, ceiling in (("cpu_millis", 6000), ("memory_mib", 32768), ("ephemeral_storage_mib", 32768)):
            self.assertEqual(resources[field]["maximum"], ceiling)
        retry = self.definitions["v1JobRetryPolicy"]["properties"]
        self.assertEqual(retry["max_attempts"]["maximum"], 3)
        self.assertEqual(retry["allow_spot"]["type"], "boolean")
        get = self.document["paths"]["/control/v1/orgs/{org_id}/jobs/{job_id}/runs"]["get"]
        parameters = {p["name"]: p for p in get["parameters"]}
        # The pinned grpc-gateway generator emits field constraints for JSON
        # bodies but only descriptions for query parameters. Preserve the
        # advertised bounds; backend handlers must enforce them as well.
        self.assertIn("capped at 100", parameters["page_size"]["description"])
        self.assertIn("at most 1024 bytes", parameters["page_token"]["description"])

    def test_runs_results_and_cancellation_are_org_and_job_scoped(self):
        root = "/control/v1/orgs/{org_id}/jobs/{job_id}/runs/{run_id}"
        for suffix, method, response in (("", "get", "v1JobRun"), (":cancel", "post", "v1JobRun"), ("/result", "get", "v1JobRunResult")):
            operation = self.document["paths"][root + suffix][method]
            paths = {p["name"] for p in operation["parameters"] if p["in"] == "path"}
            self.assertEqual(paths, {"org_id", "job_id", "run_id"})
            self.assertEqual(operation["responses"]["200"]["schema"]["$ref"], "#/definitions/" + response)
            self.assertEqual(operation.get("security", self.document["security"]), [{"bearerAuth": []}])
        run = self.definitions["v1JobRun"]["properties"]
        self.assertNotIn("logs_url", run)
        result = self.definitions["v1JobRunResult"]["properties"]
        self.assertIn("download_expires_at", result)
        self.assertIn("logs_expires_at", result)
        self.assertIn("logs_truncated", result)

    def test_sandbox_queue_is_additive_and_has_a_separate_deadline(self):
        statuses = self.definitions["v1CodeSandboxStatus"]["enum"]
        self.assertEqual(statuses[-1], "CODE_SANDBOX_STATUS_QUEUED")
        self.assertEqual(statuses[1], "CODE_SANDBOX_STATUS_STARTING")
        fields = self.definitions["v1CodeSandbox"]["properties"]
        self.assertIn("queue_deadline", fields)
        self.assertIn("expires_at", fields)


if __name__ == "__main__":
    unittest.main()
