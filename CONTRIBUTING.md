# Contributing

Thank you for helping improve the Tarka API. Public contract changes have a
larger compatibility cost than ordinary implementation changes, so please open
an issue before proposing a new service, a new versioned package, or any change
that could affect existing clients.

## Development workflow

1. Branch from `main`.
2. Edit only authoritative files under `proto/`.
3. Run `make verify` (or `make verify-docker`).
4. Review changes under `gen/` and `openapi/` for unintended behavior.
5. Describe compatibility, authentication, authorization, REST, and rollout
   effects in the pull request.

Pull requests must pass formatting, lint, generation-drift, Go compilation, and
Buf breaking-change checks. New public messages, fields, enum values, services,
and RPCs should have comments that explain their semantics rather than merely
restate their names.

## Contract rules

Follow [`VERSIONING.md`](VERSIONING.md). In particular, never renumber or reuse
fields. Reserve the number and name of anything removed. Prefer additive
changes to the current stable package, and introduce a new versioned package
for deliberately incompatible designs.

Generated files must be produced by the pinned plugins in `buf.gen.yaml` and
must not be edited manually.

## Security

Do not report vulnerabilities in a public issue. Follow [`SECURITY.md`](SECURITY.md).
