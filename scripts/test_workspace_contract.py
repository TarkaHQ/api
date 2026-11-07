"""Managed workspace controls expose lifecycle, never native bearer authority."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WorkspaceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads((ROOT / "openapi/tarka-control-v1.swagger.json").read_text())

    def test_application_policy_is_optional_and_customer_identity_is_not_input(self):
        app = self.doc["definitions"]["v1Application"]
        self.assertNotIn("workspace", app.get("required", []))
        policy = self.doc["definitions"]["v1WorkspacePolicy"]["properties"]
        self.assertEqual(set(policy), {"enabled", "agent_id", "gateway_id", "transport", "permissions", "max_workspaces", "idle_timeout_seconds"})
        self.assertNotIn("subject_id", policy)
        self.assertNotIn("CreateWorkspace", str(self.doc["paths"]))

    def test_lifecycle_is_application_scoped_and_requires_concurrency_version(self):
        root = "/control/v1/access/applications/{application_id}/workspaces"
        self.assertEqual(set(self.doc["paths"][root]), {"get"})
        for suffix, method in (("/{id}", "get"), ("/{id}/pause", "post"), ("/{id}/resume", "post"), ("/{id}", "delete")):
            operation = self.doc["paths"][root + suffix][method]
            params = {p["name"]: p for p in operation["parameters"]}
            self.assertEqual({p["name"] for p in params.values() if p["in"] == "path"}, {"application_id", "id"})
            if method == "post":
                definition = self.doc["definitions"][params["body"]["schema"]["$ref"].split("/")[-1]]
                self.assertIn("expected_version", definition["properties"])
                self.assertIn("org_id", definition["properties"])
                self.assertIn("realm_id", definition["properties"])
            else:
                self.assertIn("org_id", params)
                self.assertIn("realm_id", params)
                if method == "delete":
                    self.assertIn("expected_version", params)
            self.assertEqual(operation.get("security", self.doc["security"]), [{"bearerAuth": []}])

    def test_metadata_cannot_expose_runtime_secrets_or_customer_content(self):
        fields = self.doc["definitions"]["v1Workspace"]["properties"]
        self.assertEqual(set(fields), {"id", "org_id", "realm_id", "application_id", "subject_id", "agent_id", "agent_host_id", "status", "version", "created_at", "updated_at", "last_active_at", "status_reason"})


if __name__ == "__main__":
    unittest.main()
