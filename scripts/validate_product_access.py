#!/usr/bin/env python3
"""Validate the canonical product-access policy contract."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "product-access.json"


def main() -> int:
    policy = json.loads(CONTRACT.read_text())
    if policy.get("version") != 1:
        raise SystemExit("product-access contract version must be 1")

    products = policy.get("products")
    if not isinstance(products, list) or not products:
        raise SystemExit("product-access products must be a non-empty list")
    identifiers = [product.get("id") for product in products]
    if any(not isinstance(identifier, str) or not identifier for identifier in identifiers):
        raise SystemExit("every product needs a non-empty string id")
    if len(identifiers) != len(set(identifiers)):
        raise SystemExit("product ids must be unique")

    allowed_groups = {"models", "compute", "data"}
    for product in products:
        if product.get("group") not in allowed_groups:
            raise SystemExit(f"invalid group for {product.get('id')}")
        if not isinstance(product.get("label"), str) or not product["label"].strip():
            raise SystemExit(f"missing label for {product.get('id')}")
        if not isinstance(product.get("description"), str) or not product["description"].strip():
            raise SystemExit(f"missing description for {product.get('id')}")
        if not isinstance(product.get("api_key_scope"), bool):
            raise SystemExit(f"api_key_scope must be boolean for {product.get('id')}")

    model_products = {product["id"] for product in products if product["group"] == "models"}
    if model_products != {"himalaya", "inference", "utilities"}:
        raise SystemExit("the model authorization boundary must contain exactly himalaya, inference, and utilities")
    api_key_products = {product["id"] for product in products if product["api_key_scope"]}
    if api_key_products != model_products | {"sandboxes"}:
        raise SystemExit("API-key scopes must be the three model products plus sandboxes")

    presets = policy.get("presets")
    if not isinstance(presets, list):
        raise SystemExit("product-access presets must be a list")
    preset_ids = [preset.get("id") for preset in presets]
    if len(preset_ids) != len(set(preset_ids)):
        raise SystemExit("preset ids must be unique")
    known = set(identifiers)
    for preset in presets:
        selected = preset.get("products")
        if not isinstance(selected, list) or not selected:
            raise SystemExit(f"preset {preset.get('id')} needs products")
        if len(selected) != len(set(selected)) or not set(selected) <= known:
            raise SystemExit(f"preset {preset.get('id')} has duplicate or unknown products")

    print("validated canonical product-access policy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
