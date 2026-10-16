import hashlib
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
ACTION_REFERENCE = re.compile(r"^\s*uses:\s*([^\s#]+)")
IMMUTABLE_ACTION_REFERENCE = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")
# The reviewed version of agent-review.yml. Before changing this hash, re-check
# every property: pull_request trigger only; contents: read and pull-requests:
# write only; the job skips drafts, forks and bot authors; actions pinned to
# commits; checkout without persisted credentials; the only secrets are the
# model credential; Claude has Read, Grep and Glob only, ignores project
# settings, cannot read outside the checkout or .git, and judges against the
# base branch's AGENTS.md; and no step runs repository code.
REVIEWED_AGENT_REVIEW_SHA256 = (
    "74f69e59f81fefa41da69564e97f439b1317eb8621fe585f6964f1687fb65067"
)


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

    def test_agent_review_is_the_reviewed_version(self):
        path = WORKFLOWS / "agent-review.yml"
        self.assertEqual(
            hashlib.sha256(path.read_bytes()).hexdigest(),
            REVIEWED_AGENT_REVIEW_SHA256,
            "agent-review.yml changed: re-check the properties listed with "
            "REVIEWED_AGENT_REVIEW_SHA256, then update the hash",
        )
        workflow = path.read_text()
        # Fork pull requests never reach the model credential or the review.
        self.assertIn(
            "github.event.pull_request.head.repo.full_name == github.repository",
            workflow,
        )
        self.assertEqual(
            set(re.findall(r"secrets\.([A-Z0-9_]+)", workflow)),
            {"ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"},
        )
        self.assertEqual(
            re.findall(r'--allowedTools "([^"]+)"', workflow), ["Read,Grep,Glob"]
        )
        self.assertIn("--setting-sources user", workflow)
        self.assertIn('"blockReadsOutsideWorkingDirectories":true', workflow)


if __name__ == "__main__":
    unittest.main()
