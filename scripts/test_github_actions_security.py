from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
ACTION_REFERENCE = re.compile(r"^\s*uses:\s*([^\s#]+)")
IMMUTABLE_ACTION_REFERENCE = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")


class GitHubActionsSecurityTests(unittest.TestCase):
    def test_external_actions_are_pinned_to_full_commit_shas(self):
        references = []
        for path in sorted(WORKFLOWS.glob("*.yml")):
            for line in path.read_text().splitlines():
                match = ACTION_REFERENCE.match(line)
                if not match:
                    continue
                reference = match.group(1)
                if reference.startswith("./") or reference.startswith("docker://"):
                    continue
                references.append((path.name, reference))

        self.assertTrue(references, "at least one external Action must be checked")
        for workflow, reference in references:
            self.assertRegex(
                reference,
                IMMUTABLE_ACTION_REFERENCE,
                f"{workflow} uses mutable Action reference {reference}",
            )

    def test_untrusted_pull_request_target_is_not_enabled(self):
        for path in sorted(WORKFLOWS.glob("*.yml")):
            self.assertNotRegex(
                path.read_text(),
                r"(?m)^\s*pull_request_target\s*:",
                path.name,
            )

    def test_codeql_has_only_required_write_permission(self):
        workflow = (WORKFLOWS / "codeql.yml").read_text()
        self.assertIn("  contents: read\n", workflow)
        self.assertIn("  security-events: write\n", workflow)
        self.assertEqual(workflow.count(": write\n"), 1)
        self.assertIn("          queries: security-extended\n", workflow)


if __name__ == "__main__":
    unittest.main()
