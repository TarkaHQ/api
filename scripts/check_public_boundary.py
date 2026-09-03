#!/usr/bin/env python3
"""Fail if implementation or generated language bindings enter the public repo."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
ALLOWED_ROOT_FILES = {
    ".editorconfig",
    ".gitignore",
    "CONTRIBUTING.md",
    "LICENSE",
    "Makefile",
    "README.md",
    "SECURITY.md",
    "VERSIONING.md",
    "buf.gen.yaml",
    "buf.lock",
    "buf.yaml",
}
ALLOWED_DIRECTORY_SUFFIXES = {
    "contracts": {".json", ".md", ".yaml"},
    "openapi": {".json"},
    "proto": {".proto"},
    "scripts": {".py"},
}
SAFE_PATH_COMPONENT = re.compile(r"^[A-Za-z0-9._-]+$")
REQUIRED_PINNED_IMAGES = {"BUF_IMAGE", "OPENAPI_VALIDATOR_IMAGE"}
MAKE_ASSIGNMENT = re.compile(r"^([A-Z][A-Z0-9_]*)\s*:?=\s*(\S+)\s*$")
SECRET_PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "Brevo credential": re.compile(r"\bx(?:key|smtp)sib-[A-Za-z0-9_-]{20,}\b"),
    "Cloudflare API token": re.compile(r"\bcfat_[A-Za-z0-9_-]{20,}\b"),
    "GitHub token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b"),
    "GitLab token": re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b"),
    "Google API key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "Hugging Face token": re.compile(r"\bhf_[A-Za-z0-9]{20,}\b"),
    "npm token": re.compile(r"\bnpm_[A-Za-z0-9]{20,}\b"),
    "OpenAI-style key": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    "Slack token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    "Tarka live key": re.compile(r"\btk_live_[A-Za-z0-9_-]{20,}\b"),
    "Uptime Kuma API key": re.compile(r"\buk1_[A-Za-z0-9_-]{20,}\b"),
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


def secret_findings(name: str, content: bytes) -> list[str]:
    if b"\0" in content:
        return []
    text = content.decode("utf-8", errors="replace")
    findings: list[str] = []
    for label, pattern in SECRET_PATTERNS.items():
        for match in pattern.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            findings.append(f"possible {label} in {name}:{line}")
    return findings


def contract_path_allowed(name: str) -> bool:
    path = PurePosixPath(name)
    if not path.parts or any(
        part in {"", ".", ".."} or not SAFE_PATH_COMPONENT.fullmatch(part)
        for part in path.parts
    ):
        return False
    if len(path.parts) == 1:
        return name in ALLOWED_ROOT_FILES
    if path.parts[0] == ".github":
        if name == ".github/CODEOWNERS":
            return True
        return path.suffix in {".md", ".yaml", ".yml"}
    return path.suffix in ALLOWED_DIRECTORY_SUFFIXES.get(path.parts[0], set())


def main() -> None:
    violations: list[str] = []
    for mode, name in tracked_entries():
        if mode != "100644":
            violations.append(f"non-regular or executable tracked file: {name}")
            continue
        if not contract_path_allowed(name):
            violations.append(f"file is outside the public contract allowlist: {name}")
            continue
        content = (ROOT / name).read_bytes()
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            violations.append(f"tracked contract file is not UTF-8 text: {name}")
            continue
        if b"\0" in content:
            violations.append(f"tracked contract file contains binary data: {name}")
            continue
        violations.extend(secret_findings(name, content))

    image_assignments: dict[str, str] = {}
    for line in (ROOT / "Makefile").read_text(encoding="utf-8").splitlines():
        match = MAKE_ASSIGNMENT.fullmatch(line)
        if match and match.group(1) in REQUIRED_PINNED_IMAGES:
            image_assignments[match.group(1)] = match.group(2)
    for name in sorted(REQUIRED_PINNED_IMAGES):
        reference = image_assignments.get(name, "")
        if not re.fullmatch(r"[^\s@]+:[^\s@]+@sha256:[0-9a-f]{64}", reference):
            violations.append(f"Docker verification image is not digest-pinned: {name}")
    if violations:
        raise SystemExit("public contract boundary violations:\n- " + "\n- ".join(violations))
    print("validated contract-only public repository boundary")


if __name__ == "__main__":
    main()
