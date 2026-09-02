#!/usr/bin/env python3
"""Validate the dependency-free public Agent Host template catalog."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts" / "agent-hosts"
CATALOG = CONTRACTS / "catalog.json"
IMAGE_PATTERN = re.compile(r"^\s+image:\s*[\"']?([^\s\"']+)", re.MULTILINE)
DIGEST_PATTERN = re.compile(r"^[^@$\s]+@sha256:[0-9a-f]{64}$")


def scalar(metadata: str, field: str) -> str:
    match = re.search(rf"^  {re.escape(field)}:\s*[\"']?([^\n\"']+)[\"']?\s*$", metadata, re.MULTILINE)
    if not match:
        raise ValueError(f"x-tarka.{field} is missing")
    return match.group(1).strip()


def section(metadata: str, field: str) -> str:
    match = re.search(
        rf"^  {re.escape(field)}:\s*$\n(?P<body>.*?)(?=^  [a-z][a-z0-9_]*:\s*(?:[^|>].*)?$|\Z)",
        metadata,
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        raise ValueError(f"x-tarka.{field} is missing")
    return match.group("body")


def nested_scalar(body: str, field: str) -> str:
    match = re.search(rf"^    {re.escape(field)}:\s*[\"']?([^\n\"']+)[\"']?\s*$", body, re.MULTILINE)
    if not match:
        raise ValueError(f"x-tarka.runtime_profile.{field} is missing")
    return match.group(1).strip()


def service_count(document: str) -> int:
    match = re.search(r"^services:\s*$\n(?P<body>.*?)(?=^[a-z][a-z0-9_-]*:\s*$|\Z)", document, re.MULTILINE | re.DOTALL)
    if not match:
        raise ValueError("top-level services is missing")
    return len(re.findall(r"^  [a-z0-9](?:[a-z0-9-]*[a-z0-9])?:\s*$", match.group("body"), re.MULTILINE))


def main() -> None:
    catalog = json.loads(CATALOG.read_text())
    if catalog.get("schema_version") != 2:
        raise ValueError("catalog schema_version must be 2")
    entries = catalog.get("templates")
    if not isinstance(entries, list) or not entries:
        raise ValueError("catalog templates must be a non-empty list")

    files = sorted(CONTRACTS.glob("*.compose.yaml"))
    listed_files = sorted(entry.get("file") for entry in entries)
    if listed_files != [path.name for path in files]:
        raise ValueError("catalog files do not match the published Compose files")
    ids: set[str] = set()
    for entry in entries:
        path = CONTRACTS / entry["file"]
        raw = path.read_bytes()
        document = raw.decode()
        metadata_match = re.search(r"^x-tarka:\s*$\n(?P<body>.*?)(?=^[a-z][a-z0-9_-]*:\s*$)", document, re.MULTILINE | re.DOTALL)
        if not metadata_match:
            raise ValueError(f"{path.name}: x-tarka metadata is missing")
        metadata = metadata_match.group("body")
        actual = {
            "id": scalar(metadata, "id"),
            "version": scalar(metadata, "version"),
            "tier": scalar(metadata, "tier"),
            "service_count": service_count(document),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
        for field, value in actual.items():
            if entry.get(field) != value:
                raise ValueError(f"{path.name}: catalog {field} does not match {value!r}")
        if actual["id"] in ids:
            raise ValueError(f"duplicate template id {actual['id']}")
        ids.add(actual["id"])
        runtime = section(metadata, "runtime_profile")
        if nested_scalar(runtime, "managed_model") != "true":
            raise ValueError(f"{path.name}: managed_model must be true")
        if nested_scalar(runtime, "default_model_alias") != "qwen3.8-flash-next":
            raise ValueError(f"{path.name}: default model must be qwen3.8-flash-next")
        context_limit = int(nested_scalar(runtime, "context_token_limit"))
        compaction_limit = int(nested_scalar(runtime, "compaction_threshold_tokens"))
        if context_limit != 81920 or not 50000 <= compaction_limit < context_limit:
            raise ValueError(f"{path.name}: managed context policy is invalid")
        gateway_block = section(metadata, "gateways")
        gateway_ids = re.findall(r"^    - id:\s*([a-z][a-z0-9_-]*)\s*$", gateway_block, re.MULTILINE)
        if len(gateway_ids) != len(set(gateway_ids)) or not gateway_ids:
            raise ValueError(f"{path.name}: gateway ids must be non-empty and unique")
        setup_modes = re.findall(r"^      setup_mode:\s*([a-z_]+)\s*$", gateway_block, re.MULTILINE)
        if len(setup_modes) != len(gateway_ids) or any(mode not in {"predeploy", "postdeploy_pairing"} for mode in setup_modes):
            raise ValueError(f"{path.name}: every gateway needs a valid setup_mode")
        images = IMAGE_PATTERN.findall(document)
        if len(images) != actual["service_count"]:
            raise ValueError(f"{path.name}: every service must define exactly one image")
        for image in images:
            if not DIGEST_PATTERN.fullmatch(image):
                raise ValueError(f"{path.name}: mutable or invalid image reference {image!r}")

    print(f"validated {len(entries)} Agent Host templates")


if __name__ == "__main__":
    main()
