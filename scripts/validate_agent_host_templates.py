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
ALLOWED_TOP_LEVEL_KEYS = {"x-tarka", "services", "volumes"}
DISALLOWED_SERVICE_KEYS = {
    "build",
    "cap_add",
    "cgroup",
    "cgroup_parent",
    "configs",
    "credential_spec",
    "device_cgroup_rules",
    "devices",
    "dns",
    "dns_opt",
    "dns_search",
    "env_file",
    "extends",
    "extra_hosts",
    "external_links",
    "ipc",
    "labels",
    "links",
    "logging",
    "network_mode",
    "networks",
    "pid",
    "ports",
    "privileged",
    "runtime",
    "secrets",
    "security_opt",
    "sysctls",
    "ulimits",
    "userns_mode",
    "uts",
    "volumes_from",
}
SENSITIVE_ENVIRONMENT_NAME = re.compile(
    r"(?:PASSWORD|PASSWD|SECRET|TOKEN|API_?KEY|ACCESS_?KEY|PRIVATE_?KEY)",
    re.IGNORECASE,
)
INTERPOLATION_PATTERN = re.compile(r"\$\{([A-Z][A-Z0-9_]*)[^}]*}")
NAMED_VOLUME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


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


def optional_section(metadata: str, field: str) -> str:
    try:
        return section(metadata, field)
    except ValueError:
        return ""


def nested_scalar(body: str, field: str) -> str:
    match = re.search(rf"^    {re.escape(field)}:\s*[\"']?([^\n\"']+)[\"']?\s*$", body, re.MULTILINE)
    if not match:
        raise ValueError(f"x-tarka.runtime_profile.{field} is missing")
    return match.group(1).strip()


def service_body(document: str) -> str:
    match = re.search(r"^services:\s*$\n(?P<body>.*?)(?=^[a-z][a-z0-9_-]*:\s*$|\Z)", document, re.MULTILINE | re.DOTALL)
    if not match:
        raise ValueError("top-level services is missing")
    return match.group("body")


def service_count(document: str) -> int:
    return len(re.findall(r"^  [a-z0-9](?:[a-z0-9-]*[a-z0-9])?:\s*$", service_body(document), re.MULTILINE))


def declared_variables(metadata: str) -> set[str]:
    return set(
        re.findall(
            r"^\s+- name:\s*([A-Z][A-Z0-9_]*)\s*$",
            metadata,
            re.MULTILINE,
        )
    )


def validate_short_volume(entry: str, source: Path) -> str | None:
    entry = entry.strip().strip("\"'")
    if entry.startswith("/") and ":" not in entry:
        return None
    parts = entry.split(":")
    if len(parts) not in {2, 3}:
        raise ValueError(f"{source.name}: unsupported volume entry {entry!r}")
    volume, target = parts[:2]
    if not NAMED_VOLUME_PATTERN.fullmatch(volume):
        raise ValueError(f"{source.name}: host bind mounts are forbidden: {entry!r}")
    if not target.startswith("/") or ".." in target.split("/"):
        raise ValueError(f"{source.name}: invalid volume target {target!r}")
    if len(parts) == 3 and parts[2] not in {"ro", "rw"}:
        raise ValueError(f"{source.name}: unsupported volume mode {parts[2]!r}")
    return volume


def validate_compose_security(document: str, metadata: str, source: Path) -> None:
    top_level_keys = re.findall(
        r"^([A-Za-z][A-Za-z0-9_-]*):(?:\s.*)?$", document, re.MULTILINE
    )
    duplicates = sorted(
        key for key in set(top_level_keys) if top_level_keys.count(key) > 1
    )
    if duplicates:
        raise ValueError(f"{source.name}: duplicate top-level keys: {duplicates}")
    unexpected = sorted(set(top_level_keys) - ALLOWED_TOP_LEVEL_KEYS)
    if unexpected:
        raise ValueError(f"{source.name}: forbidden top-level keys: {unexpected}")

    services = service_body(document)
    if re.search(r"^\s*<<:\s*", services, re.MULTILINE):
        raise ValueError(f"{source.name}: YAML merge keys are forbidden")
    if re.search(r"^\s*[\"'][A-Za-z][A-Za-z0-9_-]*[\"']\s*:", services, re.MULTILINE):
        raise ValueError(f"{source.name}: quoted Compose keys are forbidden")

    for line in services.splitlines():
        key_match = re.match(r"^\s*(?:-\s+)?([a-z][a-z0-9_-]*):", line)
        if key_match and key_match.group(1) in DISALLOWED_SERVICE_KEYS:
            raise ValueError(
                f"{source.name}: service key {key_match.group(1)!r} is forbidden"
            )

        environment_match = re.match(
            r"^\s+([A-Z][A-Z0-9_]*):\s*(.*?)\s*$", line
        )
        if (
            environment_match
            and SENSITIVE_ENVIRONMENT_NAME.search(environment_match.group(1))
            and not re.fullmatch(
                r"\$\{[A-Z][A-Z0-9_]*}", environment_match.group(2)
            )
        ):
            raise ValueError(
                f"{source.name}: sensitive environment variable "
                f"{environment_match.group(1)!r} must use a declared variable"
            )

    declared = declared_variables(metadata)
    referenced = set(INTERPOLATION_PATTERN.findall(services))
    undeclared = sorted(referenced - declared)
    if undeclared:
        raise ValueError(
            f"{source.name}: undeclared Compose variables referenced: {undeclared}"
        )

    lines = services.splitlines()
    volume_indent: int | None = None
    referenced_volumes: set[str] = set()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if volume_indent is not None and indent <= volume_indent:
            volume_indent = None
        if re.fullmatch(r"volumes:\s*", stripped):
            volume_indent = indent
            continue
        if volume_indent is not None and stripped.startswith("- "):
            entry = stripped[2:].strip()
            if re.match(r"(?:type|source|target):", entry):
                raise ValueError(
                    f"{source.name}: long-form volumes are forbidden"
                )
            volume = validate_short_volume(entry, source)
            if volume:
                referenced_volumes.add(volume)

    volume_section = re.search(
        r"^volumes:\s*$\n(?P<body>.*)\Z", document, re.MULTILINE | re.DOTALL
    )
    declared_volumes: set[str] = set()
    if volume_section:
        for line in volume_section.group("body").splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            match = re.fullmatch(r"  ([A-Za-z0-9][A-Za-z0-9_.-]*):\s*", line)
            if not match:
                raise ValueError(
                    f"{source.name}: named volumes must be empty, internal declarations"
                )
            declared_volumes.add(match.group(1))
    undeclared_volumes = sorted(referenced_volumes - declared_volumes)
    if undeclared_volumes:
        raise ValueError(
            f"{source.name}: undeclared named volumes: {undeclared_volumes}"
        )


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
        validate_compose_security(document, metadata, path)
        runtime = section(metadata, "runtime_profile")
        if nested_scalar(runtime, "managed_model") != "true":
            raise ValueError(f"{path.name}: managed_model must be true")
        if nested_scalar(runtime, "default_model_alias") != "qwen3.8-flash-next":
            raise ValueError(f"{path.name}: default model must be qwen3.8-flash-next")
        context_limit = int(nested_scalar(runtime, "context_token_limit"))
        compaction_limit = int(nested_scalar(runtime, "compaction_threshold_tokens"))
        if context_limit != 81920 or not 50000 <= compaction_limit < context_limit:
            raise ValueError(f"{path.name}: managed context policy is invalid")
        gateway_block = optional_section(metadata, "gateways")
        gateway_ids = re.findall(r"^    - id:\s*([a-z][a-z0-9_-]*)\s*$", gateway_block, re.MULTILINE)
        if len(gateway_ids) != len(set(gateway_ids)):
            raise ValueError(f"{path.name}: gateway ids must be unique")
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
