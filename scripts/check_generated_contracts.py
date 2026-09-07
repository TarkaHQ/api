#!/usr/bin/env python3
"""Fail when checked-in generated OpenAPI differs from protobuf output."""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATED_CONTRACTS = (
    "openapi/tarka-control-v1.swagger.json",
    "openapi/tarka-inference-v2.swagger.json",
)


def main() -> None:
    subprocess.run(
        ["git", "diff", "--exit-code", "--", *GENERATED_CONTRACTS],
        cwd=ROOT,
        check=True,
    )
    print("validated checked-in generated OpenAPI contracts")


if __name__ == "__main__":
    main()
