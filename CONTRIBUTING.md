# Contributing

Thank you for helping improve the Tarka API. Public contract changes have a
larger compatibility cost than ordinary implementation changes, so please open
an issue before proposing a new service, a new versioned package, or any change
that could affect existing clients.

## Development workflow

1. Branch from `main`.
2. Edit authoritative files under `proto/` or the inference contract under
   `openapi/tarka-inference-v1.openapi.json`.
3. Run `make verify` (or `make verify-docker`).
4. Review the generated control OpenAPI diff and any authored inference
   OpenAPI changes for unintended behavior.
5. Describe compatibility, authentication, authorization, REST, and rollout
   effects in the pull request.

Pull requests must pass protobuf formatting, lint, generation-drift, OpenAPI
validation, and Buf breaking-change checks. New public messages, fields, enum
values, services, RPCs, paths, and schemas should explain their semantics rather
than merely restate their names.

## Contract rules

Follow [`VERSIONING.md`](VERSIONING.md). In particular, never renumber or reuse
fields. Reserve the number and name of anything removed. Prefer additive
changes to the current stable package, and introduce a new versioned package
for deliberately incompatible designs.

The generated control Swagger document must be produced by the pinned plugin in
`buf.gen.yaml` and must not be edited manually. Do not commit generated client
or server code in any language.

## Security

Do not report vulnerabilities in a public issue. Follow [`SECURITY.md`](SECURITY.md).
