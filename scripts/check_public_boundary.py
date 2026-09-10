#!/usr/bin/env python3
"""Fail if implementation or generated language bindings enter the public repo."""

from __future__ import annotations

import re
import subprocess
from collections.abc import Iterator
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
APPROVED_REMOTE_PLUGIN = "buf.build/grpc-ecosystem/openapiv2:v2.30.0"
APPROVED_REMOTE_PLUGIN_REVISION = "1"
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
OBJECT_ID_PATTERN = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
MAX_HISTORY_OBJECTS = 100_000
MAX_HISTORY_BLOB_BYTES = 32 * 1024 * 1024
MAX_HISTORY_TOTAL_BLOB_BYTES = 512 * 1024 * 1024


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
    text = content.decode("utf-8", errors="replace")
    findings: list[str] = []
    for label, pattern in SECRET_PATTERNS.items():
        for match in pattern.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            findings.append(f"possible {label} in {name}:{line}")
    return findings


def reachable_object_ids(root: Path) -> list[str]:
    process = subprocess.Popen(
        ["git", "rev-list", "--objects", "--all", "--no-object-names"],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdout is not None and process.stderr is not None
    object_ids: list[str] = []
    seen: set[str] = set()
    try:
        for raw_line in process.stdout:
            object_id = raw_line.rstrip("\n")
            if not OBJECT_ID_PATTERN.fullmatch(object_id):
                raise ValueError("git returned invalid reachable-object metadata")
            if object_id in seen:
                continue
            if len(object_ids) >= MAX_HISTORY_OBJECTS:
                raise ValueError("reachable Git object count exceeds scanner limit")
            seen.add(object_id)
            object_ids.append(object_id)
        stderr = process.stderr.read()
        return_code = process.wait()
        if return_code != 0:
            raise subprocess.CalledProcessError(
                return_code,
                process.args,
                stderr=stderr,
            )
        return object_ids
    except BaseException:
        if process.poll() is None:
            process.kill()
        process.wait()
        raise
    finally:
        process.stdout.close()
        process.stderr.close()


def historical_blob_inventory(
    root: Path, object_ids: list[str]
) -> list[tuple[str, int]]:
    if not object_ids:
        return []
    type_output = subprocess.check_output(
        [
            "git",
            "cat-file",
            "--batch-check=%(objectname) %(objecttype) %(objectsize)",
        ],
        cwd=root,
        input="\n".join(object_ids) + "\n",
        text=True,
    )
    lines = type_output.splitlines()
    if len(lines) != len(object_ids):
        raise ValueError("git object inventory is incomplete")

    blobs: list[tuple[str, int]] = []
    total_blob_bytes = 0
    for expected_object_id, line in zip(object_ids, lines):
        fields = line.split(" ")
        if len(fields) != 3 or fields[0] != expected_object_id:
            raise ValueError("git returned invalid object inventory metadata")
        object_id, object_type, raw_size = fields
        if object_type not in {"blob", "commit", "tag", "tree"}:
            raise ValueError(f"git returned invalid object type for {object_id}")
        try:
            size = int(raw_size)
        except ValueError as error:
            raise ValueError(
                f"git returned invalid object size for {object_id}"
            ) from error
        if size < 0:
            raise ValueError(f"git returned invalid object size for {object_id}")
        if object_type != "blob":
            continue
        if size > MAX_HISTORY_BLOB_BYTES:
            raise ValueError(f"historical blob exceeds scanner limit: {object_id}")
        total_blob_bytes += size
        if total_blob_bytes > MAX_HISTORY_TOTAL_BLOB_BYTES:
            raise ValueError("historical blob bytes exceed scanner limit")
        blobs.append((object_id, size))
    return blobs


def historical_blobs(root: Path) -> Iterator[tuple[str, bytes]]:
    inventory = historical_blob_inventory(root, reachable_object_ids(root))
    if not inventory:
        return
    process = subprocess.Popen(
        ["git", "cat-file", "--batch"],
        cwd=root,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert (
        process.stdin is not None
        and process.stdout is not None
        and process.stderr is not None
    )
    try:
        for object_id, expected_size in inventory:
            process.stdin.write(f"{object_id}\n".encode("ascii"))
            process.stdin.flush()
            header = process.stdout.readline().decode("ascii").rstrip("\n")
            if header != f"{object_id} blob {expected_size}":
                raise ValueError(f"unable to read historical blob {object_id}")
            content = process.stdout.read(expected_size)
            if len(content) != expected_size or process.stdout.read(1) != b"\n":
                raise ValueError(f"truncated historical blob {object_id}")
            yield object_id, content
        process.stdin.close()
        stderr = process.stderr.read()
        return_code = process.wait()
        if return_code != 0:
            raise subprocess.CalledProcessError(
                return_code,
                process.args,
                stderr=stderr,
            )
    except BaseException:
        if process.poll() is None:
            process.kill()
        process.wait()
        raise
    finally:
        if not process.stdin.closed:
            process.stdin.close()
        process.stdout.close()
        process.stderr.close()


def history_secret_findings(root: Path = ROOT) -> list[str]:
    shallow = subprocess.check_output(
        ["git", "rev-parse", "--is-shallow-repository"],
        cwd=root,
        text=True,
    ).strip()
    if shallow != "false":
        return ["git history is shallow; historical secrets cannot be verified"]

    findings: list[str] = []
    for object_id, content in historical_blobs(root):
        findings.extend(
            secret_findings(f"historical blob {object_id}", content)
        )
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


def remote_plugin_findings(content: str) -> list[str]:
    findings: list[str] = []
    plugin_entries = re.findall(r"^  -\s+\S.*$", content, re.MULTILINE)
    matches = list(
        re.finditer(r"^  - remote:\s*(\S+)\s*$", content, re.MULTILINE)
    )
    for index, match in enumerate(matches):
        reference = match.group(1)
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        block = content[match.end() : end]
        revisions = re.findall(r"^    revision:\s*(\S+)\s*$", block, re.MULTILINE)
        if reference != APPROVED_REMOTE_PLUGIN:
            findings.append(f"unapproved remote generator: {reference}")
        if revisions != [APPROVED_REMOTE_PLUGIN_REVISION]:
            findings.append(f"remote generator is not revision-pinned: {reference}")
    if len(plugin_entries) != len(matches):
        findings.append("only canonical remote protobuf generators are allowed")
    if not matches:
        findings.append("no approved remote protobuf generator configured")
    return findings


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

    violations.extend(history_secret_findings())

    image_assignments: dict[str, str] = {}
    for line in (ROOT / "Makefile").read_text(encoding="utf-8").splitlines():
        match = MAKE_ASSIGNMENT.fullmatch(line)
        if match and match.group(1) in REQUIRED_PINNED_IMAGES:
            image_assignments[match.group(1)] = match.group(2)
    for name in sorted(REQUIRED_PINNED_IMAGES):
        reference = image_assignments.get(name, "")
        if not re.fullmatch(r"[^\s@]+:[^\s@]+@sha256:[0-9a-f]{64}", reference):
            violations.append(f"Docker verification image is not digest-pinned: {name}")
    violations.extend(
        remote_plugin_findings((ROOT / "buf.gen.yaml").read_text(encoding="utf-8"))
    )
    if violations:
        raise SystemExit("public contract boundary violations:\n- " + "\n- ".join(violations))
    print("validated contract-only public repository boundary")


if __name__ == "__main__":
    main()
