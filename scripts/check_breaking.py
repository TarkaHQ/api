#!/usr/bin/env python3
"""Run Buf compatibility checks with the approved inference namespace migration."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LEGACY_PACKAGE = "tarka.inference.v2"
PACKAGE = "tarka.inference.v1"
LEGACY_FILE = "tarka/inference/v2/inference.proto"
FILE = "tarka/inference/v1/inference.proto"


def migrate_baseline(image: dict[str, Any]) -> None:
    """Normalize only the approved file/package and language namespace changes.

    Field numbers, types, RPC signatures, streaming flags and HTTP options stay
    intact, so Buf still checks the entire previous inference contract.
    Once main contains v1, this is a no-op.
    """
    files = image.get("file", [])
    if any(file.get("package") == PACKAGE for file in files):
        return
    legacy = next((file for file in files if file.get("name") == LEGACY_FILE), None)
    if legacy is None or legacy.get("package") != LEGACY_PACKAGE:
        return
    legacy["name"] = FILE
    legacy["package"] = PACKAGE
    options = legacy.get("options", {})
    renames = {
        "javaPackage": ("com.tarka.inference.v2", "com.tarka.inference.v1"),
        "csharpNamespace": ("Tarka.Inference.V2", "Tarka.Inference.V1"),
        "goPackage": (
            "github.com/TarkaHQ/api/gen/go/tarka/inference/v2;inferencev2",
            "github.com/TarkaHQ/api/gen/go/tarka/inference/v1;inferencev1",
        ),
    }
    for key, (old, new) in renames.items():
        if options.get(key) == old:
            options[key] = new

    def references(value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                references(item)
        elif isinstance(value, dict):
            for key, item in value.items():
                if key in {"typeName", "inputType", "outputType", "extendee"} and isinstance(item, str):
                    prefix = f".{LEGACY_PACKAGE}."
                    if item.startswith(prefix):
                        value[key] = f".{PACKAGE}." + item[len(prefix):]
                elif key == "dependency" and isinstance(item, list):
                    value[key] = [FILE if name == LEGACY_FILE else name for name in item]
                else:
                    references(item)

    references(image)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--against", default=".git#branch=main")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="tarka-breaking-") as directory:
        baseline = Path(directory) / "baseline.json"
        subprocess.run(
            ["buf", "build", args.against, "--output", str(baseline)], cwd=ROOT, check=True
        )
        image = json.loads(baseline.read_text())
        migrate_baseline(image)
        baseline.write_text(json.dumps(image))
        subprocess.run(["buf", "breaking", "--against", str(baseline)], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
