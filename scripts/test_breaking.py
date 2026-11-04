"""The namespace migration must not hide wire or RPC incompatibilities."""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from check_breaking import FILE, LEGACY_FILE, LEGACY_PACKAGE, PACKAGE, migrate_baseline


@unittest.skipUnless(shutil.which("buf"), "Buf is required for compatibility checks")
class InferenceMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.baseline = {"file": [{
            "name": LEGACY_FILE,
            "package": LEGACY_PACKAGE,
            "syntax": "proto3",
            "messageType": [{"name": "Request", "field": [{
                "name": "model", "number": 1, "label": "LABEL_OPTIONAL", "type": "TYPE_STRING",
            }]}],
            "service": [{"name": "InferenceService", "method": [{
                "name": "Stream", "inputType": f".{LEGACY_PACKAGE}.Request",
                "outputType": f".{LEGACY_PACKAGE}.Request", "serverStreaming": True,
            }]}],
        }]}
        migrate_baseline(self.baseline)
        self.current = copy.deepcopy(self.baseline)

    def check(self) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as directory:
            baseline = Path(directory) / "baseline.json"
            current = Path(directory) / "current.json"
            baseline.write_text(json.dumps(self.baseline))
            current.write_text(json.dumps(self.current))
            return subprocess.run(
                ["buf", "breaking", str(current), "--against", str(baseline),
                 "--config", 'version: v2\nbreaking:\n  use: [FILE]\n'],
                capture_output=True, text=True,
            )

    def test_namespace_only_migration_passes(self) -> None:
        file = self.baseline["file"][0]
        self.assertEqual(file["name"], FILE)
        self.assertEqual(file["package"], PACKAGE)
        self.assertEqual(file["service"][0]["method"][0]["inputType"], f".{PACKAGE}.Request")
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_field_type_change_is_rejected(self) -> None:
        self.current["file"][0]["messageType"][0]["field"][0]["type"] = "TYPE_BYTES"
        result = self.check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('"model"', result.stdout)

    def test_streaming_change_is_rejected(self) -> None:
        self.current["file"][0]["service"][0]["method"][0]["serverStreaming"] = False
        result = self.check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('"Stream"', result.stdout)

    def test_rpc_removal_is_rejected(self) -> None:
        self.current["file"][0]["service"][0]["method"] = []
        result = self.check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('"Stream"', result.stdout)

    def test_v1_baseline_is_unchanged(self) -> None:
        before = copy.deepcopy(self.baseline)
        migrate_baseline(self.baseline)
        self.assertEqual(self.baseline, before)


if __name__ == "__main__":
    unittest.main()
