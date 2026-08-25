# Tarka API

This repository is the source of truth for Tarka's public, gRPC-first API. It
contains the Protocol Buffer definitions that power Tarka services, official
SDKs, the Tarka CLI, and the generated REST gateway.

The API is designed to work like other public schema repositories: clone or pin
this repository, then generate a client in any language supported by Protocol
Buffers and gRPC. The checked-in Go package is the generated low-level binding
used by Tarka's own control plane; it is not a handwritten SDK.

## Repository layout

| Path | Purpose |
| --- | --- |
| `proto/tarka/provisioning/v1` | Authoritative protobuf and gRPC definitions |
| `gen/go` | Reproducibly generated Go messages, clients, servers, and REST gateway |
| `openapi` | Generated OpenAPI v2 description of the REST transcoding surface |
| `buf.yaml` | Buf module, lint, dependency, and compatibility policy |
| `buf.gen.yaml` | Pinned generators used for checked-in artifacts |

Never edit `gen/` or `openapi/` by hand. They are derived from `proto/` and CI
rejects drift.

## Use the Go bindings

Pin a release instead of depending on `main`:

```bash
go get github.com/TarkaHQ/api@v1.0.0
```

Then import the versioned package:

```go
import provisioningv1 "github.com/TarkaHQ/api/gen/go/tarka/provisioning/v1"
```

The service endpoint is `grpc.tarka.rest:443` over TLS. Authentication metadata
uses the standard `authorization: Bearer <token>` key. Control-plane RPCs use a
Tarka account access token. Customer keys beginning with `tk_live_` are accepted
only by product RPCs for which the key has an explicit scope; currently that is
the `SandboxService` with the `sandboxes` scope.

The generated REST gateway is rooted at `https://tarka.rest`. It accepts the
same `Authorization: Bearer <token>` header and uses protobuf field names in
JSON. Requests with unknown JSON fields are rejected. Sandbox mutations accept
an idempotency key either in their request message or through the
`Idempotency-Key` HTTP/gRPC metadata header.

## Generate your own client

Install [Buf](https://buf.build/docs/installation), clone a tagged release, and
use a generation template for your language:

```bash
git clone --branch v1.0.0 --depth 1 https://github.com/TarkaHQ/api.git tarka-api
cd tarka-api
buf lint
buf build
buf generate --template path/to/your/buf.gen.yaml
```

A minimal Python template, for example, is:

```yaml
version: v2
plugins:
  - remote: buf.build/protocolbuffers/python
    out: gen/python
  - remote: buf.build/grpc/python
    out: gen/python
```

Pin remote plugin versions in production generation templates. Buf resolves the
Google API annotations declared in `buf.lock`; standard protobuf well-known
types are supplied by the Protocol Buffers toolchain.

You can also use `protoc` directly. Add `proto/` and the Google API common
protos to its include paths, then compile the files under
`proto/tarka/provisioning/v1` with your language's gRPC plugin.

## Local development

With Buf and Go installed:

```bash
make verify
```

With only Docker installed:

```bash
make verify-docker
```

When changing a contract, regenerate artifacts, review the generated diff, and
include both source and generated changes in the same pull request. See
[`CONTRIBUTING.md`](CONTRIBUTING.md) and [`VERSIONING.md`](VERSIONING.md) before
proposing a change.

## REST/OpenAPI

gRPC is the primary contract. REST routes are generated from
`google.api.http` annotations in the same protobuf definitions, so the REST
surface cannot become an independent source of truth. The generated Swagger
document is available at `openapi/tarka-control-v1.swagger.json`.

## License

Apache License 2.0. See [`LICENSE`](LICENSE).
