#!/usr/bin/env python3
"""Fail if implementation or generated language bindings enter the public repo."""

from __future__ import annotations

import subprocess
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_ROOTS = {
    "cmd",
    "deploy",
    "deployment",
    "gen",
    "infrastructure",
    "internal",
    "k8s",
    "runtime",
    "services",
}
FORBIDDEN_NAMES = {
    "Dockerfile",
    "docker-compose.yml",
    "go.mod",
    "go.sum",
    "package-lock.json",
    "package.json",
    "pyproject.toml",
    "requirements.txt",
}
IMPLEMENTATION_SUFFIXES = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".go",
    ".java",
    ".js",
    ".kt",
    ".php",
    ".rb",
    ".rs",
    ".swift",
    ".ts",
}


def tracked_entries() -> list[tuple[str, str]]:
    output = subprocess.check_output(
        ["git", "ls-files", "--stage", "-z"], cwd=ROOT
    ).decode()
    entries: list[tuple[str, str]] = []
    for record in output.rstrip("\0").split("\0"):
        metadata, name = record.split("\t", 1)
        mode = metadata.split(" ", 1)[0]
        entries.append((mode, name))
    return entries


def main() -> None:
    violations: list[str] = []
    for mode, name in tracked_entries():
        path = PurePosixPath(name)
        if mode == "160000":
            violations.append(f"repository dependency is not a contract file: {name}")
        if path.parts[0] in FORBIDDEN_ROOTS:
            violations.append(f"forbidden implementation/generated directory: {name}")
        if path.name in FORBIDDEN_NAMES:
            violations.append(f"forbidden implementation dependency file: {name}")
        if path.suffix in IMPLEMENTATION_SUFFIXES:
            violations.append(f"forbidden generated/implementation source: {name}")
    if violations:
        raise SystemExit("public contract boundary violations:\n- " + "\n- ".join(violations))
    print("validated contract-only public repository boundary")


if __name__ == "__main__":
    main()
