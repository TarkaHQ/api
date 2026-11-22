# Platform access from compute (contract preview)

Every Tarka compute workload has a private platform gateway at `http://tarka`.
It is the same for hosted agents, HTTP services (Functions), batch jobs, code
sandboxes and container sessions. Profiles differ only in which capabilities
are enabled for a workload.

The platform authenticates the workload. Code inside the container sends no
credential and never holds one. The gateway address resolves only inside a
workload and is not a public fallback. Anything a caller sends in
`Authorization`, `Proxy-Authorization` or a forwarding header is discarded.

## Routes

| Route | Service |
| --- | --- |
| `GET http://tarka/` | Discovery document for this workload |
| `http://tarka/v1/*` | The OpenAI-compatible inference API described in `openapi/tarka-inference-v1.openapi.json` |
| `http://tarka/database/api/*` | The workload's own database |
| `http://tarka/project/database/api/*` | The default database of the workload's project |
| `GET http://tarka/databases` | Names of the databases this workload may use |
| `http://tarka/databases/{name}/api/*` | A named database in the workload's project |
| `GET http://tarka/storage/{bucket}` | Objects in a bucket of the workload's project |
| `http://tarka/storage/{bucket}/{key}` | One object: `GET`, `HEAD`, `PUT`, `DELETE` |
| `POST http://tarka/storage/{bucket}/{key}:presign` | A short-lived URL for a large download or upload |
| `http://tarka/git/{repository}.git/*` | Git smart HTTP for a repository of the workload's project |
| `http://tarka/mcp`, `http://tarka/api/*` | The MCP endpoint and API routes of the workload's gateway |
| `http://tarka/gateways/{gateway}/mcp`, `http://tarka/gateways/{gateway}/api/*` | The same for one of several granted gateways |
| `http://tarka/compute/functions/{name}/*` | Invoke an HTTP service (Function) of the workload's project |
| `http://tarka/compute/jobs/{name}/runs` | Start a run of a job of the workload's project, and read its status |
| `http://tarka/compute/sessions` | Create, use and delete short-lived container sessions |
| `GET http://tarka/environment` | Every project secret granted to the workload |
| `GET http://tarka/secrets/{name}` | One granted project secret |

`…/api/*` is the database record API: `GET` and `POST`
`/api/collections/{collection}/records`, `GET`, `PATCH` and `DELETE`
`/api/collections/{collection}/records/{record}`,
`GET /api/files/{collection}/{record}/{file}`, `POST /api/batch`,
`GET /api/health`, and `GET` and `POST /api/realtime`.

## Required header

Every route except `/v1` requires the request header `Tarka-Workload: 1`.
A request without it is refused with `403 platform_header_required`. `/v1`
needs no header, so an unmodified OpenAI client works with
`base_url="http://tarka/v1"` and any placeholder key.

Every route refuses a request that carries `Origin`, `Cookie`,
`X-Forwarded-For` or `Forwarded` with `403 forwarded_request_refused`: the
gateway serves code inside the workload, not a browser or a proxy in front of
it.

## Access

`WorkloadAccess` in `proto/tarka/provisioning/v1/container.proto` selects what
a workload may reach. Set it when the workload is created
(`CreateComputeWorkloadRequest.access`) or later with `SetWorkloadAccess`; a
change applies to running workloads without a redeploy. A capability left
unset takes the profile default.

| Capability | Hosted agents, HTTP services, batch jobs | Code sandboxes, container sessions |
| --- | --- | --- |
| `inference` | enabled | disabled |
| `databases` | enabled | disabled |
| `databases.own` | enabled | not available |
| `databases.project_default` | enabled | disabled |
| `storage` | disabled | disabled |
| `git` | disabled | disabled |
| `gateway` | disabled | disabled |
| `compute` | disabled | disabled |
| `environment` | disabled | disabled |
| `identity.act_as_invoking_user` | disabled (HTTP services only) | not available |

Object storage and Hosted Git stay disabled until they are enabled for the
workload, and then reach only the buckets and repositories named in its
grants. Each grant lists `read`, `write` or both. Listing grants does not
enable the capability, and enabling it without a grant reaches nothing.

The same holds for the remaining capabilities: `gateway` reaches only the
gateways it names, `compute` only the Functions it names and, when `jobs` or
`sessions` is set, the project's jobs or new sessions, and `environment` only
the secrets it names. Acting for an invoking user, binding an identity and
full database access need an owner, admin or operator.

`GET http://tarka/` returns the resolved access:

```json
{
  "service": "tarka-platform-gateway",
  "inference_base_url": "http://tarka/v1",
  "workload": {
    "id": "76c4be1f-7061-4c3b-8d39-b32864e5ac32",
    "profile": "http_service",
    "name": "echo",
    "org_id": "0b6a53c2-6a55-4d4b-9d8e-2f6f0f3a6f10",
    "project_id": "c0a1f5de-3f0c-4a52-8a39-5f8f7a0e9d21"
  },
  "access": {
    "inference": {"enabled": true},
    "databases": {"enabled": true, "mode": "rules", "own": true, "project_default": true},
    "storage": {"enabled": true, "grants": [{"bucket": "assets", "actions": ["read", "write"]}]},
    "git": {"enabled": false},
    "gateway": {"enabled": true, "gateways": ["support-tools"]},
    "compute": {"enabled": true, "functions": ["resize"], "jobs": false, "sessions": false},
    "environment": {"enabled": true, "secrets": ["STRIPE_KEY"]}
  }
}
```

While an HTTP service serves a request of a signed-in user and may act for
that user, the document also carries `"invocation": {"user": "<principal
id>", "realm": "<identity scope id>"}`.

## Databases

A workload's own database and its project's default database are created the
first time they are called. Neither needs a name, a schema file or any prior
setup. Deleting a workload leaves its database in the project as an ordinary
named database.

Both start in `implicit` schema mode. Writing a record to a collection that
does not exist creates the collection, and a field is added the first time a
record carries it: a string becomes a text field, a number a number field, a
boolean a bool field, and an object or array a JSON field. A later value of a
different type is refused with `400`. Listing a collection that does not exist
returns an empty list. Only workloads, agents and organization developers
create collections and fields; an application user cannot. Collections created
this way admit agents and refuse application users until a release sets their
rules. Submitting a release or connecting a source repository switches the
database to `managed` mode, where only releases change the schema.

`GetDatabaseManifest` returns the collections defined this way in
`implicit_collections_json`, in the form a manifest declares them. Adding them
unchanged to a release's `collections` adopts them with their data. Deleting
a project's default database or a workload's own database clears that role:
the next call without a name creates a new, empty one, and the deleted
database is restored, if at all, as an ordinary named database.

Each call is authorized as follows.

| Caller | Decision | `@request.auth` in collection rules |
| --- | --- | --- |
| Workload with no bound identity | The workload's `databases` access. `mode: rules` applies collection rules; `mode: full` bypasses them | `kind = "agent"`, `subject` = the workload ID, `realm` = the organization ID |
| Workload bound to an identity (`WorkloadAccess.identity`) | That principal's roles on the database: `read`, `use`, or `administer` for full access | The principal |
| Call that carries a project identity token in `Tarka-On-Behalf-Of` | The existing delegated check: the user's access narrowed by the agent's | The user |

A workload's own database is private to it. Another workload reaches it only
through `http://tarka/databases/{name}` and only when a grant names it.

A database sleeps when idle. The first call after a sleep waits for it to
start. If the start outlasts the request, the gateway answers
`503 database_starting` with `Retry-After`; repeat the request unchanged.

## Object storage

`http://tarka/storage/{bucket}` reaches a bucket in the workload's own
project by its name. A bucket of another project is never reachable, whatever
the grants say. The platform signs every call with a credential limited to
that bucket and to the granted actions; no credential reaches the workload.

| Request | Action | Answer |
| --- | --- | --- |
| `GET /storage/{bucket}?prefix=&delimiter=/&limit=&continuation=` | read | `{"objects": [{"key", "size", "etag", "last_modified"}], "prefixes": [...], "next_continuation": "..."}` |
| `GET /storage/{bucket}/{key}` | read | The object's bytes, with `Content-Type`, `Content-Length`, `ETag` and `Last-Modified` |
| `HEAD /storage/{bucket}/{key}` | read | The same headers without a body |
| `PUT /storage/{bucket}/{key}` | write | `200` with `{"key", "size", "etag"}` |
| `DELETE /storage/{bucket}/{key}` | write | `204`, also when the key does not exist |
| `POST /storage/{bucket}/{key}:presign` | read for `GET`, write for `PUT` | `{"method", "url", "expires_at"}` |

- `limit` is 1 to 1000 (default 1000). `delimiter` may only be `/`; with it,
  keys below the next `/` are grouped into `prefixes`. While more pages
  follow, the answer has `next_continuation`; pass it back as
  `continuation` to read the next page.
- A key is up to 1024 bytes of UTF-8, written as a path below the bucket. It
  has no empty segment, no `.` or `..` segment, no trailing `/`, no control
  character and no backslash, and `/` inside a segment cannot be escaped.
- `GET` and `HEAD` take `Range`, `If-Match`, `If-None-Match`,
  `If-Modified-Since` and `If-Unmodified-Since`. `PUT` takes `Content-Type`,
  `Content-MD5`, `Content-Encoding`, `Content-Disposition`, `Cache-Control`,
  `If-Match` and `If-None-Match`. Other request headers are dropped.
- `PUT` needs `Content-Length` and takes at most 256 MiB. A download streams
  without a size limit. For a larger upload, or to move bytes without the
  gateway, ask for a presigned URL.
- A presign body is `{"method": "GET" | "PUT", "expires_in": seconds}`.
  `expires_in` is 60 to 900 and defaults to 300. The URL names one object and
  one method, works from anywhere until it expires, and carries no credential
  that can sign another request. It points at the public storage endpoint, so
  using it needs internet egress. A presigned `PUT` needs `Content-Length` and
  takes up to 5 GiB. Every issued URL is recorded in the audit log.

## Git

`http://tarka/git/{repository}.git` is the Git smart HTTP endpoint of a Hosted
Git repository in the workload's own project.

```bash
git clone http://tarka/git/website.git
```

| Request | Action |
| --- | --- |
| `GET /git/{repository}.git/info/refs?service=git-upload-pack` | read |
| `POST /git/{repository}.git/git-upload-pack` | read |
| `GET /git/{repository}.git/info/refs?service=git-receive-pack` | write |
| `POST /git/{repository}.git/git-receive-pack` | write |

A push without `write` is refused before any data reaches the repository.
The platform authenticates to Hosted Git with a credential limited to that one
repository and to the granted actions. The gateway never asks for a password,
so git never prompts.

HTTP services and batch jobs receive `GIT_CONFIG_COUNT`, `GIT_CONFIG_KEY_0` and
`GIT_CONFIG_VALUE_0`, which make git (2.31 or later) send `Tarka-Workload: 1`
to `http://tarka`. Elsewhere, configure it once:

```bash
git config --global http.http://tarka/.extraHeader 'Tarka-Workload: 1'
```

A fetch request body is limited to 32 MiB and a push to 512 MiB. Git LFS and
the dumb HTTP protocol are not served.

## API and MCP gateways

`http://tarka/mcp` is the MCP endpoint (Streamable HTTP) of the workload's
gateway, and `http://tarka/api/{path}` reaches that gateway's API routes. Both
need exactly one granted gateway. With several, address each one by name or ID
at `http://tarka/gateways/{gateway}/mcp` and
`http://tarka/gateways/{gateway}/api/{path}`; a gateway whose name is not a
plain path segment is addressed by its ID. Only gateways of the workload's own
project are reachable.

The workload calls a gateway as an identity of the project, so the gateway's
policy, tool grants and connections apply to it exactly as to any other
caller:

- A workload bound to an identity (`WorkloadAccess.identity.principal_id`)
  calls as that agent or service principal.
- Otherwise a hosted agent, HTTP service or batch job calls as its own agent
  identity. The platform creates that agent principal in the project's
  production identity scope on the first gateway call, names it after the
  workload, and gives it no roles: every call is refused until a role grants
  it the gateway's tools. Suspending or deleting that principal locks the
  workload out; it is never created again.
- A code sandbox or container session must be bound to an identity.
- `Tarka-On-Behalf-Of: <project identity token>` calls as that user, with the
  token's audience set to the gateway, as for any delegated call.
- `Tarka-Act-As: invoking-user` calls as the signed-in user whose request the
  HTTP service is serving; see [Acting for the invoking user](#acting-for-the-invoking-user).

Requests carry `Content-Type`, `Accept`, `Mcp-Session-Id`,
`Mcp-Protocol-Version` and `Last-Event-ID`; other headers are dropped. The
gateway's own answers, including its `{"error": "permission_denied"}` refusals,
pass through unchanged.

## Invoking compute

`http://tarka/compute` reaches other compute of the workload's own project. A
call is billed to the organization and counts against its sandbox and job
quotas exactly like the same call through the control API, made by an owner,
admin or operator who may use the product. Each workload may make 60 compute
calls a minute; beyond that the gateway answers `429 rate_limited` with
`Retry-After`.

| Request | Needs | Answer |
| --- | --- | --- |
| `{method} /compute/functions/{name}/{path}?{query}` | `functions` names the service | The service's status, `Content-Type` and body |
| `POST /compute/jobs/{name}/runs` | `jobs` | `202` with the new run, as `JobRun` |
| `GET /compute/jobs/{name}/runs/{run_id}` | `jobs` | The run, as `JobRun` |
| `POST /compute/sessions` | `sessions` | `201` with the new session, as `CodeSandbox` |
| `GET /compute/sessions/{session_id}` | `sessions` | The session, as `CodeSandbox` |
| `POST /compute/sessions/{session_id}/exec` | `sessions` | The finished command, as `Execution` |
| `DELETE /compute/sessions/{session_id}` | `sessions` | The stopping session, as `CodeSandbox` |

- A Function call takes any method `InvokeHTTPService` takes, `Content-Type`
  and a body of at most 1 MiB, and waits for the service like
  `InvokeHTTPService`. The service receives the path below
  `/compute/functions/{name}` and the query string.
- A job run repeats the job's current definition, as a new revision. It is
  refused with `409 job_run_active` while a run of the job is active.
- A session body is `{"container": {...}, "timeout_seconds": 30-300,
  "resources": {...}, "max_network_bytes": n}`, the fields of
  `CreateCodeSandboxRequest` for a container session. A command body is
  `{"command": ["..."], "stdin": "...", "timeout_seconds": 1-30,
  "idempotency_key": "..."}`. A workload reaches only the sessions it created.
  A new session is in the workload's project and has every capability
  disabled, like any other.
- JSON uses the field names of the protobuf messages.

Workloads that invoke each other form a chain. The platform records each
call's depth: a call from outside Tarka has depth 0, and a Function, job run
or session started by a workload has the depth of its caller plus one. An
invoked service receives `Tarka-Call-Depth` with its depth; code does not need
to forward it. A call that would exceed depth 4 is refused with
`508 call_depth_exceeded`, so a Function that calls itself, or two that call
each other, stop.

## Environment and secrets

Project secrets are managed with `SetProjectSecret`, `ListProjectSecrets` and
`DeleteProjectSecret`. A workload whose `environment` names a secret reads it
at run time; the platform never writes a secret into a container's
configuration, and the control API never returns one.

| Request | Answer |
| --- | --- |
| `GET /environment` | `{"variables": {"NAME": "value", ...}}` with every granted secret that exists |
| `GET /secrets/{name}` | `{"name": "NAME", "value": "...", "version": 3}` |

A secret name is an environment variable name: an uppercase letter or
underscore followed by up to 127 uppercase letters, digits and underscores.
Every read is recorded in the organization's audit log by name, never with
its value. A deleted or replaced secret takes effect on the next read.

## Acting for the invoking user

An HTTP service with `identity.act_as_invoking_user` can act for the signed-in
user of its project whose request it is serving, without handling a token.

1. The user's request reaches the service's public URL with
   `Authorization: Bearer <access token>`, issued by the project's production
   identity scope for the audience `https://{label}.tarka.run`. The platform
   verifies it before invoking the service and answers `401` if it is not
   valid. The service receives neither the token nor `Authorization`.
2. For the duration of that one invocation the platform holds a short-lived
   assertion of the user, bound to the service, the replica and the call.
3. Code that sends `Tarka-Act-As: invoking-user` on a database or gateway
   request acts as that user. Access is the intersection of the user's own
   permissions and the workload's: the workload's access decides which
   databases and gateways are reachable at all, and the user's roles and the
   collection rules decide the rest.

The assertion ends with the invocation: a request sent after the response
was returned, from a request of another caller, or from another workload, is
refused with `403 invoking_user_unavailable`. Without
`act_as_invoking_user` the service never sees a difference: the
`Authorization` header is ignored, as before.

## Errors

Gateway errors use one JSON shape:

```json
{"error": {"type": "permission_error", "code": "capability_disabled", "message": "Database access is not enabled for this workload."}}
```

| HTTP | `code` | Meaning |
| --- | --- | --- |
| `403` | `platform_header_required` | The `Tarka-Workload: 1` header is missing |
| `403` | `forwarded_request_refused` | The request carries a browser or proxy header |
| `403` | `capability_disabled` | The route's capability is not enabled for this workload, the bucket or repository is not granted, or the grant lacks the action |
| `403` | `workload_unbound` | The container is not currently assigned to a workload |
| `404` | `database_not_found` | No database with that name is available to this workload |
| `404` | `bucket_not_found` | No bucket with that name in the workload's project |
| `404` | `object_not_found` | No object at that key |
| `404` | `repository_not_found` | No repository with that name in the workload's project |
| `404` | `gateway_not_found` | No gateway with that name or ID in the workload's project |
| `404` | `function_not_found` | No HTTP service with that name in the workload's project |
| `404` | `job_not_found` | No job with that name in the workload's project |
| `404` | `job_run_not_found` | No run with that ID of that job |
| `404` | `session_not_found` | No session with that ID created by this workload |
| `404` | `secret_not_found` | No secret with that name in the workload's project |
| `400` | `gateway_required` | `/mcp` or `/api/*` was called while several gateways are granted |
| `403` | `identity_required` | A code sandbox or container session called a gateway without a bound identity |
| `403` | `invoking_user_unavailable` | `Tarka-Act-As: invoking-user` was sent outside a live invocation by a signed-in user |
| `409` | `job_run_active` | A run of the job is still active |
| `429` | `rate_limited` | The workload made too many compute calls; retry after `Retry-After` |
| `503` | `function_unavailable` | The service is busy with another call or could not start; retry |
| `508` | `call_depth_exceeded` | The chain of workloads invoking each other is deeper than 4 |
| `411` | `length_required` | An upload through the gateway needs `Content-Length` |
| `412` | `precondition_failed` | A conditional header did not match |
| `413` | `payload_too_large` | The body is over the gateway's limit; use a presigned URL |
| `416` | `range_not_satisfiable` | The requested range lies outside the object |
| `503` | `database_starting` | The database is starting; retry after `Retry-After` |
| `502` | `platform_unavailable` | The platform service could not be reached |

Responses from the inference API, the database record API, gateways and
invoked Functions pass through unchanged. Object bytes and Git protocol
responses pass through as well; storage, Git, compute and secret errors use
the shape above.
