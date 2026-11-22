"""Check the managed database control routes, the data service, and its compatibility vectors."""
import re
import unittest
from pathlib import Path

from strict_json import load_json_object

ROOT = Path(__file__).resolve().parents[1]
DATABASE = "/control/v1/orgs/{org_id}/databases/{database_id}"
COLLECTION = DATABASE + "/collections/{collection}/records"
STREAMING = {"DownloadRecordFile", "OpenRealtime"}
UNBOUND = STREAMING | {"SetRealtimeSubscriptions"}


def proto_messages(source: str) -> dict[str, set[str]]:
    """Return the field names of every top-level message."""
    messages: dict[str, set[str]] = {}
    for name, body in re.findall(r"^message (\w+) \{\n(.*?)^\}", source, re.M | re.S):
        fields = re.findall(r"^\s+(?:repeated |optional )?(?:map<[^>]+>|[\w.]+) (\w+) = \d+", body, re.M)
        messages[name] = set(fields)
    return messages


class DatabaseContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = load_json_object(ROOT / "openapi/tarka-control-v1.swagger.json")
        cls.paths = cls.document["paths"]
        cls.definitions = cls.document["definitions"]
        cls.proto = (ROOT / "proto/tarka/databases/v1/databases.proto").read_text(encoding="utf-8")
        cls.rpcs = {
            name: (request, bool(stream))
            for name, request, stream in re.findall(r"rpc (\w+)\((\w+)\) returns \((stream )?[\w.]+\)", cls.proto)
        }
        cls.messages = proto_messages(cls.proto)
        cls.vectors = load_json_object(ROOT / "contracts/databases/pocketbase-compat-vectors.json")

    def operation(self, route: str, method: str) -> dict:
        operation = self.paths[route][method]
        self.assertEqual(operation.get("security", self.document["security"]), [{"bearerAuth": []}])
        return operation

    def test_lifecycle_routes_return_the_database(self):
        for route, method in ((DATABASE, "delete"), (DATABASE + ":restore", "post"), (DATABASE + "/restore-points", "post")):
            operation = self.operation(route, method)
            self.assertEqual(operation["responses"]["200"]["schema"]["$ref"], "#/definitions/v1ManagedDatabase")
            paths = {p["name"] for p in operation["parameters"] if p["in"] == "path"}
            self.assertEqual(paths, {"org_id", "database_id"})
        delete = {p["name"]: p for p in self.operation(DATABASE, "delete")["parameters"]}
        self.assertEqual(delete["expected_version"]["in"], "query")
        restore = self.definitions["ProvisioningServiceRestoreManagedDatabaseBody"]["properties"]
        self.assertEqual(set(restore), {"restore_point_id", "expected_version"})

    def test_history_lists_are_paginated_and_bounded(self):
        for suffix, response in (
            ("/restore-points", "v1ListDatabaseRestorePointsResponse"),
            ("/agents", "v1ListDatabaseAttachmentsResponse"),
            ("/releases", "v1ListDatabaseReleasesResponse"),
        ):
            operation = self.operation(DATABASE + suffix, "get")
            self.assertEqual(operation["responses"]["200"]["schema"]["$ref"], "#/definitions/" + response)
            parameters = {p["name"]: p for p in operation["parameters"]}
            # The pinned generator emits only descriptions for query bounds.
            self.assertIn("capped at 100", parameters["page_size"]["description"])
            self.assertIn("at most 1024 bytes", parameters["page_token"]["description"])
            self.assertIn("next_page_token", self.definitions[response]["properties"])

    def test_resources_expose_lifecycle_state_without_credentials(self):
        database = self.definitions["v1ManagedDatabase"]["properties"]
        for field in ("created_at", "updated_at", "deleted_at", "restorable_until", "backup_requested_at"):
            self.assertEqual(database[field]["format"], "date-time")
        self.assertEqual(database["operation_error"]["type"], "string")
        release = self.definitions["v1DatabaseRelease"]["properties"]
        self.assertEqual(release["error"]["type"], "string")
        self.assertEqual(release["activated_at"]["format"], "date-time")
        point = self.definitions["v1DatabaseRestorePoint"]["properties"]
        self.assertEqual(set(point), {"id", "database_id", "release", "sha256", "size_bytes", "created_at"})
        for name, definition in self.definitions.items():
            if "Database" in name or "Record" in name:
                for field in set(definition.get("properties", {})) - {"page_token", "next_page_token"}:
                    self.assertNotRegex(field, r"token|secret|password|access_key", f"{name}.{field}")

    def test_existing_database_routes_are_preserved(self):
        established = {
            (DATABASE.rsplit("/", 1)[0], "get"), (DATABASE.rsplit("/", 1)[0], "post"),
            (DATABASE, "get"), (DATABASE, "patch"),
            (DATABASE + "/agents/{agent_host_id}", "put"), (DATABASE + "/manifest", "get"),
            (DATABASE + "/releases", "post"), (DATABASE + "/releases/{release_id}:approve", "post"),
            (DATABASE + "/schema:propose", "post"),
        }
        for route, method in established:
            self.assertIn(method, self.paths[route], f"{method.upper()} {route}")

    def test_record_routes_are_scoped_to_one_database(self):
        routes = {
            ("ListRecords", COLLECTION, "get"), ("CreateRecord", COLLECTION, "post"),
            ("GetRecord", COLLECTION + "/{record_id}", "get"), ("UpdateRecord", COLLECTION + "/{record_id}", "patch"),
            ("DeleteRecord", COLLECTION + "/{record_id}", "delete"),
            ("BatchRecords", DATABASE + "/records:batch", "post"), ("GetDatabaseHealth", DATABASE + "/health", "get"),
        }
        for rpc, route, method in routes:
            operation = self.operation(route, method)
            self.assertEqual(operation["operationId"], "DatabaseService_" + rpc)
            paths = {p["name"] for p in operation["parameters"] if p["in"] == "path"}
            self.assertLessEqual({"org_id", "database_id"}, paths)
        bound = {operation["operationId"].split("_", 1)[1] for item in self.paths.values() for operation in item.values()
                 if operation["operationId"].startswith("DatabaseService_")}
        self.assertEqual(bound, set(self.rpcs) - UNBOUND)

    def test_every_data_request_names_its_organization_and_database(self):
        self.assertEqual({name for name, (_, stream) in self.rpcs.items() if stream}, STREAMING)
        for rpc, (request, _) in self.rpcs.items():
            fields = self.messages[request]
            self.assertLessEqual({"org_id", "database_id"}, fields, rpc)
        # A client-streaming RPC would be unusable from the published SDKs.
        self.assertNotRegex(self.proto, r"rpc \w+\(stream ")

    def test_uploads_are_bounded_parts(self):
        file = self.definitions["v1RecordFile"]["properties"]
        self.assertEqual(file["content"]["format"], "byte")
        self.assertEqual(file["field"]["maxLength"], 256)
        self.assertEqual(file["filename"]["maxLength"], 255)
        actions = self.definitions["v1BatchAction"]["enum"]
        self.assertEqual(actions[0], "BATCH_ACTION_UNSPECIFIED")
        self.assertEqual(set(actions[1:]), {"BATCH_ACTION_CREATE", "BATCH_ACTION_UPDATE", "BATCH_ACTION_UPSERT", "BATCH_ACTION_DELETE"})

    def test_vectors_match_the_service(self):
        self.assertEqual(self.vectors["version"], 1)
        self.assertEqual(self.vectors["service"], "tarka.databases.v1.DatabaseService")
        codes = {entry["grpc"] for entry in self.vectors["status_mapping"]}
        names = [case["name"] for case in self.vectors["cases"]]
        self.assertEqual(len(names), len(set(names)))
        for case in self.vectors["cases"]:
            with self.subTest(case=case["name"]):
                request, stream = self.rpcs[case["rpc"]]
                self.assertLessEqual(set(case["grpc_request"]), self.messages[request] - {"org_id", "database_id"})
                self.assertTrue(case["http_request"]["path"].startswith("/api/"))
                self.assertLessEqual(len([k for k in ("json", "multipart") if k in case["http_request"]]), 1)
                outcomes = [k for k in ("grpc_response", "grpc_stream", "grpc_error") if k in case]
                self.assertEqual(len(outcomes), 1)
                self.assertEqual(outcomes[0] == "grpc_stream", stream)
                if "grpc_error" in case:
                    self.assertIn(case["grpc_error"]["code"], codes)
                    self.assertEqual(case["grpc_error"]["record_error"], case["http_response"]["body"])
        self.assertEqual({case["rpc"] for case in self.vectors["cases"]}, set(self.rpcs))


if __name__ == "__main__":
    unittest.main()
