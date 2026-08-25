# Tarka API

This repository is the source of truth for Tarka's public API surface. It
contains the Protocol Buffer definitions that power Tarka's gRPC control API
and the OpenAPI contracts for its HTTP compatibility surfaces.

The API is designed to work like other public schema repositories: clone or pin
this repository, then generate a client in any language supported by Protocol
Buffers and gRPC. This repository intentionally contains no generated language
bindings and no Tarka implementation code.

## Public contract boundary

Only externally observable API contracts belong here. Service handlers,
business rules, authentication and authorization implementation, persistence,
controllers, gateway hooks, runtime code, container definitions, and deployment
manifests remain in Tarka's private infrastructure repository. Generated
bindings used by Tarka are produced inside that private build.

## Repository layout

| Path | Purpose |
| --- | --- |
| `proto/tarka/provisioning/v1` | Authoritative protobuf and gRPC definitions |
| `openapi/tarka-control-v1.swagger.json` | Generated OpenAPI v2 description of the control API's REST transcoding surface |
| `openapi/tarka-inference-v1.openapi.json` | Authored OpenAPI 3.1 contract for the supported OpenAI-compatible inference surface |
| `buf.yaml` | Buf module, lint, dependency, and compatibility policy |
| `buf.gen.yaml` | Pinned generator for the derived control OpenAPI document |

Never edit `openapi/tarka-control-v1.swagger.json` by hand; it is derived from
the protobuf annotations and CI rejects drift. The inference OpenAPI document
is authoritative for the separate `/v1` compatibility surface.

## API families

- The gRPC-first control API manages accounts, organizations, keys, quotas,
  usage, hosted Git, sandboxes, and desired-state resources. Its REST
  transcoding routes live under `/control/v1`.
- The inference API is a deliberately scoped OpenAI-compatible HTTP API at
  `https://tarka.rest/v1`. Its currently guaranteed endpoints are
  `GET /v1/models` and `POST /v1/chat/completions`, including SSE streaming.

The inference surface is REST-native for compatibility with existing OpenAI
clients; it is not represented as a Tarka gRPC service. Tarka's official SDKs
will compose generated gRPC control clients with the inference compatibility
client behind one supported interface.

## Connect to the APIs

The service endpoint is `grpc.tarka.rest:443` over TLS. Authentication metadata
uses the standard `authorization: Bearer <token>` key. Control-plane RPCs use a
Tarka account access token. Customer keys beginning with `tk_live_` are accepted
only by product RPCs for which the key has an explicit scope; currently that is
the `SandboxService` with the `sandboxes` scope.

The control REST gateway is rooted at `https://tarka.rest`. It accepts the
same `Authorization: Bearer <token>` header and uses protobuf field names in
JSON. Requests with unknown JSON fields are rejected. Sandbox mutations accept
an idempotency key either in their request message or through the
`Idempotency-Key` HTTP/gRPC metadata header.

Existing OpenAI clients can call inference by changing only their base URL and
key:

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://tarka.rest/v1",
    api_key="tk_live_...",
)

completion = client.chat.completions.create(
    model="scalabs/himalaya-q8",
    messages=[{"role": "user", "content": "Reply with READY."}],
)
```

Tarka implements the subset documented in
`openapi/tarka-inference-v1.openapi.json`; OpenAI endpoints absent from that
document are not part of Tarka's stable public contract.

## Generate your own client

Install [Buf](https://buf.build/docs/installation), clone a tagged release, and
use a generation template for your language:

```bash
git clone --branch v1.1.0 --depth 1 https://github.com/TarkaHQ/api.git tarka-api
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

With Buf installed:

```bash
make verify
```

With only Docker installed:

```bash
make verify-docker
```

When changing the protobuf contract, regenerate the control OpenAPI document
and include it in the same pull request. Validate authored inference OpenAPI
changes as part of the same review. See
[`CONTRIBUTING.md`](CONTRIBUTING.md) and [`VERSIONING.md`](VERSIONING.md) before
proposing a change.

## REST/OpenAPI

gRPC is the primary control-plane contract. Control REST routes are generated from
`google.api.http` annotations in the same protobuf definitions, so the REST
control surface cannot become an independent source of truth. The separate
OpenAI-compatible inference surface is described by an authored OpenAPI 3.1
document because its wire format is HTTP/JSON and SSE rather than protobuf.

## License

Apache License 2.0. See [`LICENSE`](LICENSE).
