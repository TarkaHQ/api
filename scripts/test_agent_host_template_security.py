#!/usr/bin/env python3
"""Regression tests for the Agent Host Compose trust boundary."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("validate_agent_host_templates.py")
SPEC = importlib.util.spec_from_file_location("agent_host_validator", SCRIPT)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


METADATA = """  id: test
  variables:
    - name: APP_PASSWORD
      secret: true
"""
SAFE = """x-tarka:
  id: test
services:
  app:
    image: example.invalid/app@sha256:{digest}
    environment:
      APP_PASSWORD: ${{APP_PASSWORD}}
    expose: ["8080"]
    volumes:
      - app-data:/data
volumes:
  app-data:
""".format(digest="0" * 64)


class AgentHostTemplateSecurityTests(unittest.TestCase):
    def validate(self, document: str) -> None:
        VALIDATOR.validate_compose_security(document, METADATA, Path("test.yaml"))

    def test_safe_named_volume_and_declared_secret_are_allowed(self) -> None:
        self.validate(SAFE)

    def test_host_bind_mount_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "host bind mounts"):
            self.validate(SAFE.replace("app-data:/data", "/etc:/host"))

    def test_long_form_volume_is_rejected(self) -> None:
        document = SAFE.replace(
            "      - app-data:/data", "      - type: bind\n        source: /etc\n        target: /host"
        )
        with self.assertRaisesRegex(ValueError, "long-form volumes"):
            self.validate(document)

    def test_host_port_publish_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "service key 'ports' is forbidden"):
            self.validate(SAFE.replace('    expose: ["8080"]', '    ports: ["8080:8080"]'))

    def test_privileged_service_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "service key 'privileged' is forbidden"):
            self.validate(SAFE.replace("    environment:", "    privileged: true\n    environment:"))

    def test_undeclared_interpolation_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "undeclared Compose variables"):
            self.validate(SAFE.replace("${APP_PASSWORD}", "${UNDECLARED_TOKEN}"))

    def test_literal_secret_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "sensitive environment variable"):
            self.validate(SAFE.replace("${APP_PASSWORD}", "hard-coded"))

    def test_unknown_top_level_section_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "forbidden top-level keys"):
            self.validate(SAFE + "networks:\n  host-access:\n")

    def test_external_named_volume_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "empty, internal declarations"):
            self.validate(SAFE.replace("  app-data:\n", "  app-data:\n    external: true\n"))

    def test_undeclared_named_volume_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "undeclared named volumes"):
            self.validate(SAFE.replace("app-data:/data", "missing:/data"))

    def test_yaml_merge_key_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "YAML merge keys"):
            self.validate(SAFE.replace("    image:", "    <<: *defaults\n    image:"))

    def test_quoted_forbidden_key_cannot_bypass_validation(self) -> None:
        document = SAFE.replace(
            "    environment:", '    "privileged": true\n    environment:'
        )
        with self.assertRaisesRegex(ValueError, "quoted Compose keys"):
            self.validate(document)


if __name__ == "__main__":
    unittest.main()
