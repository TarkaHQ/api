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
CI enforces this boundary and rejects generated language sources, application
dependency manifests, service/runtime directories, container definitions,
deployment manifests, and repository dependencies.

## Repository layout

| Path | Purpose |
| --- | --- |
| `proto/tarka/provisioning/v1` | Authoritative control-plane protobuf and gRPC definitions |
| `proto/tarka/inference/v2` | Authoritative inference protobuf and gRPC definitions |
| `openapi/tarka-control-v1.swagger.json` | Generated OpenAPI v2 description of the control API's REST transcoding surface |
| `openapi/tarka-inference-v1.openapi.json` | Authored OpenAPI 3.1 contract for the supported OpenAI-compatible inference surface |
| `openapi/tarka-inference-v2.openapi.json` | Authored OpenAPI 3.1 contract for the deprecated `/v2` REST alias |
| `openapi/tarka-inference-v2.swagger.json` | Generated OpenAPI v2 description of protobuf-bound inference methods |
| `buf.yaml` | Buf module, lint, dependency, and compatibility policy |
| `buf.gen.yaml` | Pinned generator for the derived control OpenAPI document |

Never edit either generated Swagger document by hand; they are derived from
protobuf annotations and CI rejects drift. The authored inference OpenAPI
documents define the exact HTTP wire contracts for `/v1` and `/v2`, including
multipart uploads and byte-stream responses that protobuf transcoding alone
cannot describe precisely.

## API families

- The gRPC-first control API manages accounts, organizations, keys, quotas,
  usage, object storage, hosted Git, sandboxes, and desired-state resources. Its REST
  transcoding routes live under `/control/v1`.
- The inference API is a deliberately scoped OpenAI-compatible HTTP API at
  `https://tarka.rest/v1`. It supports models, chat completions, OCR,
  Responses, transcription, translation, speech generation, and consent-backed
  voice cloning through the endpoints in `tarka-inference-v1.openapi.json`.
  OCR is available both through the dedicated `POST /v1/ocr` endpoint and
  through multimodal `POST /v1/chat/completions` requests.
- Every inference operation also has a native gRPC method at
  `grpc.tarka.rest:443`. The REST gateway calls those same authenticated gRPC
  methods, so REST and gRPC share authorization, model routing, metering,
  persistence, and errors.
- `/v2` is a deprecated compatibility alias for `/v1`. It is not a newer API
  generation and advertises its deprecation in HTTP response headers.

The protobuf package remains `tarka.inference.v2` to preserve the already
published gRPC wire contract. Its package number is independent of the
canonical REST version. Native clients should use
`tarka.inference.v2.InferenceService` when gRPC is available.

## Connect to the APIs

The REST endpoint is `tarka.rest:443` and the native gRPC endpoint is
`grpc.tarka.rest:443`, both over TLS. Authentication metadata uses the standard
`authorization: Bearer <token>` key. Control-plane RPCs use a Tarka account
access token. Customer keys beginning with `tk_live_` are accepted by the
Inference API and, when they include the `sandboxes` scope, by SandboxService
RPCs.

Inside a Tarka Agent Host, the same canonical REST API is available at
`http://tarka/v1`. The host injects a short-lived scoped credential; callers
must not copy that credential outside the host.

The control REST gateway is rooted at `https://tarka.rest/control/v1`. It
accepts `Authorization: Bearer <Tarka account access token>` and uses protobuf
field names in JSON. A `tk_live_` inference key is not an account token and is
rejected by ordinary Control API methods. Sandbox methods are the deliberate
exception: they also accept a `tk_live_` key with the `sandboxes` scope.
Requests with unknown JSON fields are rejected. Sandbox mutations accept an
idempotency key either in their request message or through the
`Idempotency-Key` HTTP/gRPC metadata header.

## Control API

The Control API is the automation surface behind customer workspace actions in
the Tarka Console. Its contract is gRPC-first; every REST route below is a
transcoding binding on the same protobuf method. JSON field names are
`snake_case`, timestamps use RFC 3339, and 64-bit integers may be serialized as
JSON strings by protobuf-aware clients.

The API has three credential boundaries:

| Credential | Accepted by | Purpose |
| --- | --- | --- |
| Tarka account access token | Every Control API method | Identity, organizations, credentials, policy, usage, and provisioning |
| `tk_live_` key with `sandboxes` scope | SandboxService methods only | Organization-bound sandbox automation |
| `tk_live_` key with `himalaya`, `inference`, or `utilities` scope | Inference API only | Runtime requests for HimalayaAI, general LLM, or utility model categories |

Account access must be approved, the organization must be active, and the
caller must have an active organization membership. Read operations generally
accept every organization role. Organization metadata and quota changes require
an owner or admin. API-key, compute, storage, and repository mutations require
an owner, admin, or operator. Product entitlements add a second gate for
private-beta model categories, Agent Hosts, Batch Jobs, Sandboxes, Object
Storage, and Hosted Git. A key scope cannot exceed its creator's current product
entitlement, and removing that entitlement blocks existing model keys.

### Identity, organizations, and access requests

| Method | REST route | Ability |
| --- | --- | --- |
| `GetCurrentUser` | `GET /control/v1/me` | Return the account identity, product entitlement decisions, and every active organization membership |
| `BootstrapCurrentUser` | `POST /control/v1/me/bootstrap` | Idempotently create the first organization when none exists |
| `CreateOrg` | `POST /control/v1/orgs` | Create an additional organization and owner membership |
| `GetOrg` | `GET /control/v1/orgs/{org_id}` | Read one visible organization |
| `UpdateOrg` | `PATCH /control/v1/orgs/{org_id}` | Change an organization display name |
| `ListOrgMembers` | `GET /control/v1/orgs/{org_id}/members` | List active and inactive memberships |
| `RequestProductAccess` | `POST /control/v1/orgs/{org_id}/product-access-requests` | Submit a private-beta product request |
| `ListProductAccessRequests` | `GET /control/v1/orgs/{org_id}/product-access-requests` | List recent requests, optionally filtered by product |

Organization selection in the web console is browser state, not a server-side
Control API resource. API callers select an organization by putting `org_id` in
the route or request message.

### Models, API keys, limits, usage, and resources

| Method | REST route | Ability |
| --- | --- | --- |
| `ListModels` | `GET /control/v1/models` | List active model aliases with their server-owned `access_product`, optionally filtered by `modality` |
| `CreateApiKey` | `POST /control/v1/orgs/{org_id}/api-keys` | Create a scoped `tk_live_` key; plaintext is returned once |
| `ListApiKeys` | `GET /control/v1/orgs/{org_id}/api-keys` | List redacted key metadata |
| `RevokeApiKey` | `POST /control/v1/orgs/{org_id}/api-keys/{api_key_id}:revoke` | Permanently revoke a key |
| `GetQuotaPolicy` | `GET /control/v1/orgs/{org_id}/quota-policy` | Read effective concurrency, request, token, and model policy |
| `UpdateQuotaPolicy` | `PUT /control/v1/orgs/{org_id}/quota-policy` | Replace the organization quota policy |
| `ListUsageEvents` | `GET /control/v1/orgs/{org_id}/usage/events` | Read newest metered requests; `limit` defaults to 25 and caps at 100 |
| `GetUsageSummary` | `GET /control/v1/orgs/{org_id}/usage/summary` | Aggregate the current UTC calendar month |
| `ListProvisionedResources` | `GET /control/v1/orgs/{org_id}/resources` | List desired-state resources, optionally by `resource_type` |
| `GetProvisionedResource` | `GET /control/v1/orgs/{org_id}/resources/{resource_id}` | Read one desired-state resource and status detail |
| `CreateInferenceService` | `POST /control/v1/orgs/{org_id}/inference-services` | Apply managed inference desired state |
| `CreateAgentHost` | `POST /control/v1/orgs/{org_id}/agent-hosts` | Apply Agent Host desired state after beta approval |
| `CreateJob` | `POST /control/v1/orgs/{org_id}/jobs` | Apply Batch Job desired state after beta approval |

`CreateInferenceService`, `CreateAgentHost`, and `CreateJob` are desired-state
apply operations: reusing an organization, resource type, and name replaces the
stored spec and returns the same resource identity. Generic resource reads do
not imply a generic delete operation. Product-specific lifecycle methods are
published only when their behavior is implemented.

### Object Storage and Hosted Git

| Method | REST route | Ability |
| --- | --- | --- |
| `CreateStorageBucket` | `POST /control/v1/orgs/{org_id}/storage/buckets` | Provision a private, versioned bucket |
| `ListStorageBuckets` | `GET /control/v1/orgs/{org_id}/storage/buckets` | List organization buckets |
| `DeleteStorageBucket` | `DELETE /control/v1/orgs/{org_id}/storage/buckets/{bucket_id}` | Delete an empty bucket |
| `CreateStorageCredential` | `POST /control/v1/orgs/{org_id}/storage/buckets/{bucket_id}/credentials` | Create a bucket-bound S3 access key and one-time secret |
| `ListStorageCredentials` | `GET /control/v1/orgs/{org_id}/storage/buckets/{bucket_id}/credentials` | List redacted S3 credential metadata |
| `RevokeStorageCredential` | `POST /control/v1/orgs/{org_id}/storage/buckets/{bucket_id}/credentials/{credential_id}:revoke` | Permanently revoke an S3 credential |
| `EnsureHostedGitAccess` | `POST /control/v1/me/git-access` | Provision or reconcile the account's Hosted Git identity |
| `CreateGitRepository` | `POST /control/v1/orgs/{org_id}/git-repositories` | Create a private, LFS-enabled repository |
| `ListGitRepositories` | `GET /control/v1/orgs/{org_id}/git-repositories` | List repositories and clone URLs |
| `DeleteGitRepository` | `DELETE /control/v1/orgs/{org_id}/git-repositories/{repository_id}` | Delete a repository and retain its final control-plane state |

S3 credentials are separate from Tarka API keys. `access_key_id` and
`secret_access_key` are returned together only at credential creation; later
list operations return redacted metadata. Hosted Git data-plane authentication
uses an SSH key or a Forgejo personal access token, not a `tk_live_` key.

### Code Sandboxes

| Method | REST route | Ability |
| --- | --- | --- |
| `ListSandboxTemplates` | `GET /control/v1/orgs/{org_id}/sandbox-templates` | List built-in and organization templates |
| `CreateSandboxTemplate` | `POST /control/v1/orgs/{org_id}/sandbox-templates` | Build a dependency-pinned Python or Node.js template |
| `GetSandboxTemplate` | `GET /control/v1/orgs/{org_id}/sandbox-templates/{template_id}` | Read template build state |
| `DeleteSandboxTemplate` | `DELETE /control/v1/orgs/{org_id}/sandbox-templates/{template_id}` | Retire an unused custom template |
| `ListSandboxes` | `GET /control/v1/orgs/{org_id}/sandboxes` | List non-deleted sandboxes |
| `CreateSandbox` | `POST /control/v1/orgs/{org_id}/sandboxes` | Start a sandbox from a ready template |
| `GetSandbox` | `GET /control/v1/orgs/{org_id}/sandboxes/{sandbox_id}` | Read sandbox lifecycle state |
| `DeleteSandbox` | `DELETE /control/v1/orgs/{org_id}/sandboxes/{sandbox_id}` | Idempotently stop and delete a sandbox |
| `Execute` | `POST /control/v1/orgs/{org_id}/sandboxes/{sandbox_id}:execute` | Execute one source-code payload |
| `GetExecution` | `GET /control/v1/orgs/{org_id}/sandboxes/{sandbox_id}/executions/{execution_id}` | Read execution state and retained output |

Sandbox template creation, sandbox creation, and execution accept
`idempotency_key`; the same key and request body return the original resource
for 24 hours. Reusing a key with different content is rejected. Execution
stdout and stderr are retained for 15 minutes.

### Errors

REST authentication middleware returns a compact JSON body such as
`{"error":"invalid_token"}`. Errors emitted after protobuf dispatch use the
standard gRPC-Gateway status object. Stable error codes are documented in
protobuf comments and implementation documentation; clients should branch on
HTTP/gRPC status and the machine-readable message, not on prose.

| HTTP | gRPC | Typical meaning |
| --- | --- | --- |
| `400` | `INVALID_ARGUMENT` | Invalid field, unknown scope, or validation limit |
| `401` | `UNAUTHENTICATED` | Missing, expired, malformed, or unknown bearer token |
| `403` | `PERMISSION_DENIED` | Account, membership, role, entitlement, scope, or organization mismatch |
| `404` | `NOT_FOUND` | Visible resource does not exist |
| `409` | `ALREADY_EXISTS`, `FAILED_PRECONDITION`, or `ABORTED` | Name conflict or lifecycle precondition |
| `429` | `RESOURCE_EXHAUSTED` | Quota, rate, or cluster-capacity limit |
| `503` | `UNAVAILABLE` | Required control dependency is unavailable |

The complete field-level contract is in
[`proto/tarka/provisioning/v1`](proto/tarka/provisioning/v1), and the generated
REST description is
[`openapi/tarka-control-v1.swagger.json`](openapi/tarka-control-v1.swagger.json).

Existing OpenAI clients can call inference by changing only their base URL and
key:

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://tarka.rest/v1",
    api_key="tk_live_...",
)

completion = client.chat.completions.create(
    model="himalaya-q8",
    messages=[{"role": "user", "content": "Reply with READY."}],
)
```

The Responses API uses the same client and base URL:

```python
response = client.responses.create(
    model="himalaya-q8",
    input="Reply with READY.",
)
print(response.output_text)
```

For OCR through the same OpenAI-compatible method, select an OCR model and send
an inline image as a standard multimodal content part:

```python
completion = client.chat.completions.create(
    model="glm-ocr-nepali",
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "Extract all text from this image."},
            {
                "type": "image_url",
                "image_url": {"url": "data:image/png;base64,..."},
            },
        ],
    }],
)
```

OCR images must be inline base64 values or base64 data URLs. Remote image URLs
are rejected. OCR requests require a customer key with the `utilities` scope,
including requests sent through `/chat/completions`.

Tarka implements the subset documented in
`openapi/tarka-inference-v1.openapi.json`; OpenAI endpoints absent from that
document are not part of Tarka's stable public contract.

## Generate your own client

Install [Buf](https://buf.build/docs/installation), clone a tagged release, and
use a generation template for your language:

```bash
git clone --branch v1.3.0 --depth 1 https://github.com/TarkaHQ/api.git tarka-api
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
`proto/tarka/provisioning/v1` and `proto/tarka/inference/v2` with your
language's gRPC plugin.

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
