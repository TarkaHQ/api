#!/usr/bin/env python3
"""Validate the repository's public OpenAPI contract invariants."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTROL_PATH = ROOT / "openapi" / "tarka-control-v1.swagger.json"
INFERENCE_PATH = ROOT / "openapi" / "tarka-inference-v1.openapi.json"
INFERENCE_V2_PATH = ROOT / "openapi" / "tarka-inference-v2.swagger.json"
INFERENCE_V2_OPENAPI_PATH = ROOT / "openapi" / "tarka-inference-v2.openapi.json"
HTTP_METHODS = {
    "get",
    "put",
    "post",
    "delete",
    "options",
    "head",
    "patch",
    "trace",
}
PUBLIC_API_HOST = "tarka.rest"
PUBLIC_API_ORIGIN = f"https://{PUBLIC_API_HOST}"


def load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        document = json.load(handle)
    if not isinstance(document, dict):
        raise ValueError(f"{path}: document root must be an object")
    return document


def resolve_pointer(document: dict[str, Any], reference: str, source: Path) -> None:
    if not reference.startswith("#/"):
        raise ValueError(f"{source}: only local references are allowed: {reference}")
    value: Any = document
    for raw_part in reference[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if not isinstance(value, dict) or part not in value:
            raise ValueError(f"{source}: unresolved reference: {reference}")
        value = value[part]


def walk_references(value: Any, document: dict[str, Any], source: Path) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "$ref":
                if not isinstance(child, str):
                    raise ValueError(f"{source}: $ref must be a string")
                resolve_pointer(document, child, source)
            else:
                walk_references(child, document, source)
    elif isinstance(value, list):
        for child in value:
            walk_references(child, document, source)


def operation_ids(document: dict[str, Any], source: Path) -> set[str]:
    identifiers: set[str] = set()
    for route, path_item in document.get("paths", {}).items():
        if not isinstance(route, str) or not route.startswith("/"):
            raise ValueError(f"{source}: invalid route: {route!r}")
        if not isinstance(path_item, dict):
            raise ValueError(f"{source}: path item for {route} must be an object")
        for method, operation in path_item.items():
            if method.lower() not in HTTP_METHODS:
                continue
            if not isinstance(operation, dict):
                raise ValueError(f"{source}: {method.upper()} {route} must be an object")
            identifier = operation.get("operationId")
            if not isinstance(identifier, str) or not identifier:
                raise ValueError(f"{source}: {method.upper()} {route} has no operationId")
            if identifier in identifiers:
                raise ValueError(f"{source}: duplicate operationId: {identifier}")
            identifiers.add(identifier)
    return identifiers


def has_bearer_requirement(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(
            isinstance(requirement, dict)
            and set(requirement) == {"bearerAuth"}
            and requirement["bearerAuth"] == []
            for requirement in value
        )
    )


def validate_bearer_definition(document: dict[str, Any], source: Path) -> None:
    """Require credentials to use the standard Authorization bearer header."""

    if document.get("swagger") == "2.0":
        definition = document.get("securityDefinitions", {}).get("bearerAuth")
        expected = {
            "type": "apiKey",
            "in": "header",
            "name": "Authorization",
        }
        if not isinstance(definition, dict) or any(
            definition.get(key) != value for key, value in expected.items()
        ):
            raise ValueError(
                f"{source}: bearerAuth must use the Authorization header"
            )
        return

    definition = (
        document.get("components", {})
        .get("securitySchemes", {})
        .get("bearerAuth")
    )
    if not isinstance(definition, dict) or {
        "type": definition.get("type"),
        "scheme": definition.get("scheme"),
    } != {"type": "http", "scheme": "bearer"}:
        raise ValueError(f"{source}: bearerAuth must be an HTTP bearer scheme")


def validate_authenticated_tls_surface(
    document: dict[str, Any], source: Path
) -> None:
    if not has_bearer_requirement(document.get("security")):
        raise ValueError(f"{source}: global bearerAuth requirement is required")
    validate_bearer_definition(document, source)

    if document.get("swagger") == "2.0":
        if document.get("schemes") != ["https"]:
            raise ValueError(f"{source}: Swagger surface must use HTTPS only")
        if document.get("host") != PUBLIC_API_HOST:
            raise ValueError(
                f"{source}: Swagger host must be {PUBLIC_API_HOST}"
            )
    else:
        servers = document.get("servers")
        if (
            not isinstance(servers, list)
            or len(servers) != 1
            or not isinstance(servers[0], dict)
            or servers[0].get("url") != PUBLIC_API_ORIGIN
        ):
            raise ValueError(
                f"{source}: server must be exactly {PUBLIC_API_ORIGIN}"
            )

    for route, path_item in document.get("paths", {}).items():
        for method, operation in path_item.items():
            if method.lower() not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            if "security" in operation and not has_bearer_requirement(
                operation["security"]
            ):
                raise ValueError(
                    f"{source}: {method.upper()} {route} weakens bearer authentication"
                )


def validate_control(document: dict[str, Any]) -> None:
    if document.get("swagger") != "2.0":
        raise ValueError(f"{CONTROL_PATH}: expected Swagger 2.0")
    routes = document.get("paths")
    if not isinstance(routes, dict) or not routes:
        raise ValueError(f"{CONTROL_PATH}: no routes")
    unexpected = sorted(route for route in routes if not route.startswith("/control/v1/"))
    if unexpected:
        raise ValueError(
            f"{CONTROL_PATH}: inference routes must not be generated from the control API: "
            + ", ".join(unexpected)
        )


def validate_inference(document: dict[str, Any]) -> None:
    if document.get("openapi") != "3.1.0":
        raise ValueError(f"{INFERENCE_PATH}: expected OpenAPI 3.1.0")
    expected = {
        "/v1/models": {"get"},
        "/v1/models/{model}": {"get"},
        "/v1/chat/completions": {"post"},
        "/v1/responses": {"post"},
        "/v1/responses/{response_id}": {"get", "delete"},
        "/v1/responses/{response_id}/cancel": {"post"},
        "/v1/ocr": {"post"},
        "/v1/audio/transcriptions": {"post"},
        "/v1/audio/translations": {"post"},
        "/v1/audio/speech": {"post"},
        "/v1/audio/voice-clones": {"post"},
        "/v1/audio/voice-clones/{voice_id}": {"get", "delete"},
    }
    routes = document.get("paths")
    if not isinstance(routes, dict):
        raise ValueError(f"{INFERENCE_PATH}: paths must be an object")
    actual = {
        route: {
            method.lower()
            for method in path_item
            if method.lower()
            in {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
        }
        for route, path_item in routes.items()
    }
    if actual != expected:
        raise ValueError(
            f"{INFERENCE_PATH}: stable endpoint set changed; expected {expected}, got {actual}"
        )
    schemes = document.get("components", {}).get("securitySchemes", {})
    if "bearerAuth" not in schemes:
        raise ValueError(f"{INFERENCE_PATH}: bearerAuth security scheme is required")
    for route in ("/v1/audio/transcriptions", "/v1/audio/translations", "/v1/audio/voice-clones"):
        content = routes[route]["post"]["requestBody"]["content"]
        if "multipart/form-data" not in content:
            raise ValueError(f"{INFERENCE_PATH}: {route} must be multipart")
    speech_content = routes["/v1/audio/speech"]["post"]["responses"]["200"]["content"]
    if not any(value.get("schema", {}).get("format") == "binary" for value in speech_content.values()):
        raise ValueError(f"{INFERENCE_PATH}: speech response must be binary")


def validate_inference_v2(document: dict[str, Any]) -> None:
    if document.get("swagger") != "2.0":
        raise ValueError(f"{INFERENCE_V2_PATH}: expected Swagger 2.0")
    expected_v1 = {
        "/v1/models": {"get"},
        "/v1/models/{model}": {"get"},
        "/v1/chat/completions": {"post"},
        "/v1/responses": {"post"},
        "/v1/responses/{response_id}": {"get", "delete"},
        "/v1/responses/{response_id}/cancel": {"post"},
        "/v1/ocr": {"post"},
        "/v1/audio/transcriptions": {"post"},
        "/v1/audio/translations": {"post"},
        "/v1/audio/speech": {"post"},
        "/v1/audio/voice-clones": {"post"},
        "/v1/audio/voice-clones/{voice_id}": {"get", "delete"},
    }
    expected_v2 = {
        "/v2/models": {"get"},
        "/v2/models/{model}": {"get"},
        "/v2/chat/completions": {"post"},
        "/v2/responses": {"post"},
        "/v2/responses/{response_id}": {"get", "delete"},
        "/v2/responses/{response_id}/cancel": {"post"},
        "/v2/ocr": {"post"},
        "/v2/audio/transcriptions": {"post"},
        "/v2/audio/translations": {"post"},
        "/v2/audio/speech": {"post"},
        "/v2/audio/voice-clones": {"post"},
        "/v2/audio/voice-clones/{voice_id}": {"get", "delete"},
    }
    expected = expected_v1 | expected_v2
    routes = document.get("paths")
    if not isinstance(routes, dict):
        raise ValueError(f"{INFERENCE_V2_PATH}: paths must be an object")
    actual = {
        route: {
            method.lower()
            for method in path_item
            if method.lower()
            in {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
        }
        for route, path_item in routes.items()
    }
    if actual != expected:
        raise ValueError(
            f"{INFERENCE_V2_PATH}: endpoint set changed; expected {expected}, got {actual}"
        )
    schemes = document.get("securityDefinitions", {})
    bearer = schemes.get("bearerAuth", {})
    if bearer.get("name") != "Authorization" or bearer.get("in") != "header":
        raise ValueError(f"{INFERENCE_V2_PATH}: bearerAuth security definition is required")
    definitions = document.get("definitions", {})
    required = {
        "v2ChatCompletionRequest",
        "v2OpenAIRequest",
        "v2OpenAIResponse",
        "v2OCRRequest",
        "v2AudioTranscriptionRequest",
        "v2AudioTranslationRequest",
        "v2SpeechRequest",
        "v2VoiceCloneRequest",
    }
    missing = sorted(required - definitions.keys())
    if missing:
        raise ValueError(f"{INFERENCE_V2_PATH}: missing request definitions: {missing}")


def validate_inference_v2_openapi(document: dict[str, Any]) -> None:
    if document.get("openapi") != "3.1.0":
        raise ValueError(f"{INFERENCE_V2_OPENAPI_PATH}: expected OpenAPI 3.1.0")
    expected = {
        "/v2/models": {"get"},
        "/v2/models/{model}": {"get"},
        "/v2/chat/completions": {"post"},
        "/v2/responses": {"post"},
        "/v2/responses/{response_id}": {"get", "delete"},
        "/v2/responses/{response_id}/cancel": {"post"},
        "/v2/ocr": {"post"},
        "/v2/audio/transcriptions": {"post"},
        "/v2/audio/translations": {"post"},
        "/v2/audio/speech": {"post"},
        "/v2/audio/voice-clones": {"post"},
        "/v2/audio/voice-clones/{voice_id}": {"get", "delete"},
    }
    routes = document.get("paths", {})
    actual = {
        route: {
            method
            for method in item
            if method in {"get", "put", "post", "delete", "patch"}
        }
        for route, item in routes.items()
    }
    if actual != expected:
        raise ValueError(f"{INFERENCE_V2_OPENAPI_PATH}: endpoint set mismatch")
    schemes = document.get("components", {}).get("securitySchemes", {})
    if schemes.get("bearerAuth", {}).get("scheme") != "bearer":
        raise ValueError(f"{INFERENCE_V2_OPENAPI_PATH}: bearerAuth is required")
    for route in ("/v2/audio/transcriptions", "/v2/audio/translations", "/v2/audio/voice-clones"):
        content = routes[route]["post"]["requestBody"]["content"]
        if "multipart/form-data" not in content:
            raise ValueError(f"{INFERENCE_V2_OPENAPI_PATH}: {route} must be multipart")
    speech_content = routes["/v2/audio/speech"]["post"]["responses"]["200"]["content"]
    if not any(value.get("schema", {}).get("format") == "binary" for value in speech_content.values()):
        raise ValueError(f"{INFERENCE_V2_OPENAPI_PATH}: speech response must be binary")


def main() -> None:
    control = load(CONTROL_PATH)
    inference = load(INFERENCE_PATH)
    inference_v2 = load(INFERENCE_V2_PATH)
    inference_v2_openapi = load(INFERENCE_V2_OPENAPI_PATH)
    validate_control(control)
    validate_inference(inference)
    validate_inference_v2(inference_v2)
    validate_inference_v2_openapi(inference_v2_openapi)
    for source, document in (
        (CONTROL_PATH, control),
        (INFERENCE_PATH, inference),
        (INFERENCE_V2_PATH, inference_v2),
        (INFERENCE_V2_OPENAPI_PATH, inference_v2_openapi),
    ):
        validate_authenticated_tls_surface(document, source)
        operation_ids(document, source)
        walk_references(document, document, source)
    print("validated control and v1/v2 inference OpenAPI contracts")


if __name__ == "__main__":
    main()
