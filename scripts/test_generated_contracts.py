from __future__ import annotations

import unittest
from subprocess import CalledProcessError
from unittest import mock

from check_generated_contracts import GENERATED_CONTRACTS, ROOT, main


class GeneratedContractTests(unittest.TestCase):
    def test_all_generated_contracts_are_guarded(self) -> None:
        self.assertEqual(
            GENERATED_CONTRACTS,
            (
                "openapi/tarka-control-v1.swagger.json",
                "openapi/tarka-inference-v2.swagger.json",
            ),
        )

    @mock.patch("check_generated_contracts.subprocess.run")
    def test_check_fails_closed_on_generated_drift(self, run: mock.Mock) -> None:
        run.side_effect = CalledProcessError(1, ["git", "diff"])

        with self.assertRaises(CalledProcessError):
            main()

        run.assert_called_once_with(
            ["git", "diff", "--exit-code", "--", *GENERATED_CONTRACTS],
            cwd=ROOT,
            check=True,
        )


if __name__ == "__main__":
    unittest.main()
