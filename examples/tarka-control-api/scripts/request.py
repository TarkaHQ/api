#!/usr/bin/env python3
"""Small, dependency-free JSON client for the public Tarka Control API."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


BASE_URL = "https://tarka.rest/control/v1"


class NoRedirect(HTTPRedirectHandler):
    """Never forward a bearer token to a redirect target."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_url(path: str) -> str:
    parts = urlsplit(path)
    if (
        not path.startswith("/")
        or path.startswith("//")
        or parts.scheme
        or parts.netloc
        or parts.fragment
        or "\\" in path
        or any(ord(char) <= 32 or ord(char) == 127 for char in path)
        or any(part in {".", ".."} for part in unquote(parts.path).split("/"))
    ):
        raise ValueError("PATH must be a route such as /me, relative to /control/v1")
    return BASE_URL + path


def request_body(source: str | None) -> bytes | None:
    if source is None:
        return None
    if source == "-":
        raw = sys.stdin.read()
    elif source.startswith("@"):
        raw = Path(source[1:]).read_text(encoding="utf-8")
    else:
        raw = source
    try:
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError("expected an object")
        return json.dumps(value, allow_nan=False).encode("utf-8")
    except ValueError as error:
        # Do not echo a potentially secret-bearing body in a validation error.
        raise ValueError("--data must contain a valid JSON object") from error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("method", type=str.upper, choices=("GET", "POST", "PUT", "PATCH", "DELETE"))
    parser.add_argument("path", help="route relative to /control/v1, e.g. /me")
    parser.add_argument("--data", metavar="JSON|@FILE|-", help="JSON object, file, or stdin")
    args = parser.parse_args(argv)

    try:
        token = os.environ.get("TARKA_ACCESS_TOKEN", "").strip()
        if not token:
            raise ValueError("set TARKA_ACCESS_TOKEN in your environment")
        if not token.isascii() or any(char.isspace() for char in token):
            raise ValueError("TARKA_ACCESS_TOKEN must be a single bearer token")
        url = request_url(args.path)
        body = request_body(args.data)
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = Request(url, data=body, headers=headers, method=args.method)
        with build_opener(NoRedirect()).open(request, timeout=30) as response:
            output = response.read().decode("utf-8")
        sys.stdout.write(output)
        if output and not output.endswith("\n"):
            sys.stdout.write("\n")
        return 0
    except HTTPError as error:
        with error:
            detail = error.read().decode("utf-8", errors="replace")
        print(f"HTTP {error.code}: {detail or error.reason}", file=sys.stderr)
    except (URLError, OSError, ValueError) as error:
        print(f"Request failed: {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
