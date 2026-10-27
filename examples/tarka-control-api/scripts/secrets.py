#!/usr/bin/env python3
"""Upload Agent Host secrets from a local file without echoing secret values."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener
from uuid import UUID

from request import BASE_URL, NoRedirect

KEY = re.compile(r"^[A-Z_][A-Z0-9_]{0,127}$")
LIMIT = 262144


def parse_values(raw: str) -> dict[str, str]:
    """JSON or .env, without shell execution, expansion, or value-bearing errors."""
    if len(raw.encode("utf-8")) > LIMIT:
        raise ValueError("secret file is too large")
    values: dict[str, str] = {}

    def put(key: str, value: str) -> None:
        if not KEY.fullmatch(key) or key in values or not isinstance(value, str):
            raise ValueError("invalid or duplicate secret key")
        if len(value.encode("utf-8")) > 65536:
            raise ValueError("secret value is too large")
        values[key] = value

    if raw.lstrip().startswith("{"):
        def pairs(entries):
            for key, value in entries:
                put(key, value)
            return values
        try:
            result = json.loads(raw, object_pairs_hook=pairs)
            if not isinstance(result, dict):
                raise ValueError()
        except (ValueError, TypeError):
            raise ValueError("invalid JSON secret file") from None
    else:
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].lstrip()
            key, separator, value = line.partition("=")
            if not separator:
                raise ValueError("invalid .env secret file")
            value = value.strip()
            try:
                if value.startswith('"'):
                    value = json.loads(value)
                elif value.startswith("'"):
                    if not value.endswith("'") or len(value) < 2:
                        raise ValueError()
                    value = value[1:-1]
                else:
                    value = value.split(" #", 1)[0].rstrip()
                put(key.strip(), value)
            except (ValueError, TypeError):
                raise ValueError("invalid .env secret file") from None
    if not 1 <= len(values) <= 128:
        raise ValueError("secret file must contain 1 to 128 keys")
    return values


def call(method: str, path: str, token: str, body: dict) -> dict:
    request = Request(BASE_URL + path, data=json.dumps(body).encode("utf-8"), method=method,
                      headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    with build_opener(NoRedirect()).open(request, timeout=30) as response:
        result = json.load(response)
    if not isinstance(result, dict):
        raise ValueError("invalid metadata response")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--org", required=True, help="organization ID")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--bundle", help="handoff ID returned to your agent")
    target.add_argument("--name", help="host name; prepare a new handoff before upload")
    parser.add_argument("--file", required=True, help="local .env/JSON file, or - for stdin")
    args = parser.parse_args(argv)
    try:
        org = str(UUID(args.org))
        token = os.environ.get("TARKA_ACCESS_TOKEN", "").strip()
        if not token or not token.isascii() or any(char.isspace() for char in token):
            raise ValueError("set TARKA_ACCESS_TOKEN in the local environment")
        if args.file == "-":
            raw = sys.stdin.read(LIMIT + 1)
        else:
            with Path(args.file).open(encoding="utf-8") as source:
                raw = source.read(LIMIT + 1)
        values = parse_values(raw)
        base = f"/orgs/{org}/agent-host-secret-bundles"
        bundle = args.bundle
        if not bundle:
            bundle = call("POST", base, token, {"name": args.name})["id"]
        bundle = str(UUID(bundle))
        metadata = call("PUT", base + "/" + bundle, token, {"values": values})
        if metadata.get("status") != "ready":
            raise ValueError("secret upload did not become ready")
        # Print locally validated metadata only, never an arbitrary server body.
        print(json.dumps({"secrets_bundle_id": bundle, "status": "ready", "keys": sorted(values)}))
        return 0
    except HTTPError as error:
        print(f"Secret upload failed (HTTP {error.code}); no values were printed.", file=sys.stderr)
    except (URLError, OSError, ValueError, KeyError, TypeError):
        print("Secret upload failed; check the local file, session and handoff. No values were printed.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
