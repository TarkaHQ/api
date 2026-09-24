"""Offline checks for the copyable Control API skill's HTTP helper."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError


SKILL = Path(__file__).resolve().parents[1] / "examples" / "tarka-control-api"
SPEC = importlib.util.spec_from_file_location("skill_request", SKILL / "scripts" / "request.py")
assert SPEC is not None and SPEC.loader is not None
client = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(client)


class SkillRequestTests(unittest.TestCase):
    def invoke(self, args, *, response=b"{}", failure=None, token="example-token", stdin=""):
        opener = Mock()
        opener.open.return_value = io.BytesIO(response)
        opener.open.side_effect = failure
        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            patch.dict(os.environ, {"TARKA_ACCESS_TOKEN": token}),
            patch.object(client, "build_opener", return_value=opener),
            patch.object(sys, "stdin", io.StringIO(stdin)),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            result = client.main(args)
        return result, stdout.getvalue(), stderr.getvalue(), opener

    def test_sends_each_method_with_bearer_auth_query_and_timeout(self):
        for method in ("GET", "POST", "PUT", "PATCH", "DELETE"):
            with self.subTest(method=method):
                result, stdout, stderr, opener = self.invoke(
                    [method.lower(), "/orgs/example/resources?resource_type=agent"],
                    response=b'{"resources": []}',
                )
                self.assertEqual((result, json.loads(stdout), stderr), (0, {"resources": []}, ""))
                request = opener.open.call_args.args[0]
                self.assertEqual(request.get_method(), method)
                self.assertEqual(
                    request.full_url,
                    "https://tarka.rest/control/v1/orgs/example/resources?resource_type=agent",
                )
                self.assertEqual(request.get_header("Authorization"), "Bearer example-token")
                self.assertEqual(request.get_header("Accept"), "application/json")
                self.assertIsNone(request.data)
                opener.open.assert_called_once_with(request, timeout=30)

    def test_inline_file_and_stdin_preserve_json_fields(self):
        body = {"name": "demo", "spec": {"label": "नमस्ते"}, "min_replicas": 0}
        raw = json.dumps(body, ensure_ascii=False)
        with tempfile.TemporaryDirectory() as directory:
            body_file = Path(directory) / "body.json"
            body_file.write_text(raw, encoding="utf-8")
            for source, stdin in ((raw, ""), ("@" + str(body_file), ""), ("-", raw)):
                with self.subTest(source=source):
                    result, _, stderr, opener = self.invoke(
                        ["POST", "/orgs/example/agent-hosts", "--data", source], stdin=stdin
                    )
                    self.assertEqual((result, stderr), (0, ""))
                    request = opener.open.call_args.args[0]
                    self.assertEqual(json.loads(request.data), body)
                    self.assertEqual(request.get_header("Content-type"), "application/json")

    def test_invalid_inputs_fail_without_network_or_echoing_secrets(self):
        cases = [
            (["GET", "/me"], {"token": ""}),
            (["GET", "/me"], {"token": "secret\nvalue"}),
            (["POST", "/orgs", "--data", '{"secret":"private-value",'], {}),
            (["POST", "/orgs", "--data", "[]"], {}),
            (["POST", "/orgs", "--data", '{"value":NaN}'], {}),
            (["POST", "/orgs", "--data", '{"value":Infinity}'], {}),
        ]
        for args, options in cases:
            with self.subTest(args=args):
                result, stdout, stderr, opener = self.invoke(args, **options)
                self.assertEqual((result, stdout), (1, ""))
                self.assertTrue(stderr)
                self.assertNotIn("private-value", stderr)
                self.assertNotIn("secret\nvalue", stderr)
                self.assertNotIn("example-token", stderr)
                opener.open.assert_not_called()

    def test_rejects_paths_outside_the_control_base(self):
        for path in (
            "https://example.invalid/me", "//example.invalid/me", "me",
            "/me#fragment", "/../v1/models", "/%2e%2e/v1/models", "/me\n",
            "/\\example.invalid/me", "/me?filter=raw space",
        ):
            with self.subTest(path=path):
                result, stdout, stderr, opener = self.invoke(["GET", path])
                self.assertEqual((result, stdout), (1, ""))
                self.assertIn("PATH must be", stderr)
                opener.open.assert_not_called()

    def test_missing_body_file_fails_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            result, stdout, stderr, opener = self.invoke(
                ["POST", "/orgs", "--data", "@" + str(Path(directory) / "missing.json")]
            )
        self.assertEqual((result, stdout), (1, ""))
        self.assertIn("Request failed", stderr)
        opener.open.assert_not_called()

    def test_http_errors_preserve_both_api_error_shapes_without_retry(self):
        for status in (400, 401, 403, 404, 409, 429, 503):
            body = b'{"error":"invalid_token"}' if status == 401 else b'{"code":7,"message":"denied"}'
            with self.subTest(status=status):
                error = HTTPError(client.BASE_URL + "/me", status, "failure", {}, io.BytesIO(body))
                result, stdout, stderr, opener = self.invoke(["POST", "/orgs"], failure=error)
                self.assertEqual((result, stdout), (1, ""))
                self.assertIn(f"HTTP {status}: {body.decode()}", stderr)
                opener.open.assert_called_once()

    def test_network_errors_and_timeouts_do_not_retry(self):
        for error in (URLError("offline"), TimeoutError("timed out")):
            with self.subTest(error=error):
                result, stdout, stderr, opener = self.invoke(["POST", "/orgs"], failure=error)
                self.assertEqual((result, stdout), (1, ""))
                self.assertIn("Request failed", stderr)
                opener.open.assert_called_once()

    def test_empty_response_is_successful(self):
        result, stdout, stderr, _ = self.invoke(["DELETE", "/orgs/example/sandboxes/demo"], response=b"")
        self.assertEqual((result, stdout, stderr), (0, "", ""))

    def test_redirects_never_reach_the_target(self):
        received = []

        class RedirectServer(BaseHTTPRequestHandler):
            def do_GET(self):
                received.append(self.path)
                self.send_response(int(self.path.rsplit("/", 1)[-1]))
                self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/leaked")
                self.end_headers()

            def log_message(self, *args):
                pass

        with HTTPServer(("127.0.0.1", 0), RedirectServer) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                for status in (301, 302, 303, 307, 308):
                    stderr = io.StringIO()
                    with (
                        self.subTest(status=status),
                        patch.object(client, "BASE_URL", f"http://127.0.0.1:{server.server_port}/control/v1"),
                        patch.dict(os.environ, {"TARKA_ACCESS_TOKEN": "example-token", "no_proxy": "127.0.0.1"}),
                        redirect_stdout(io.StringIO()),
                        redirect_stderr(stderr),
                    ):
                        self.assertEqual(client.main(["GET", f"/{status}"]), 1)
                        self.assertIn(f"HTTP {status}:", stderr.getvalue())
                self.assertEqual(received, [f"/control/v1/{status}" for status in (301, 302, 303, 307, 308)])
            finally:
                server.shutdown()
                thread.join(timeout=5)

    def test_copied_skill_runs_from_an_unrelated_working_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            installed = shutil.copytree(SKILL, root / "installed" / "tarka-control-api")
            cwd = root / "elsewhere"
            cwd.mkdir()
            script = str(installed / "scripts" / "request.py")
            environment = {key: value for key, value in os.environ.items() if key not in {"TARKA_ACCESS_TOKEN", "PYTHONPATH"}}
            for args, expected in ((["--help"], 0), (["GET", "/me"], 1)):
                process = subprocess.run(
                    [sys.executable, "-I", script, *args], cwd=cwd, env=environment,
                    capture_output=True, text=True, timeout=5,
                )
                self.assertEqual(process.returncode, expected, process.stderr)
                if expected:
                    self.assertIn("set TARKA_ACCESS_TOKEN", process.stderr)
                else:
                    self.assertIn("JSON|@FILE|-", process.stdout)


if __name__ == "__main__":
    unittest.main()
