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

`…/api/*` is the database record API: `GET` and `POST`
`/api/collections/{collection}/records`, `GET`, `PATCH` and `DELETE`
`/api/collections/{collection}/records/{record}`,
`GET /api/files/{collection}/{record}/{file}`, `POST /api/batch`,
`GET /api/health`, and `GET` and `POST /api/realtime`.

The API and MCP gateway and invoking other compute are not part of this
contract yet.

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

Object storage and Hosted Git stay disabled until they are enabled for the
workload, and then reach only the buckets and repositories named in its
grants. Each grant lists `read`, `write` or both. Listing grants does not
enable the capability, and enabling it without a grant reaches nothing.

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
    "git": {"enabled": false}
  }
}
```

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
| `411` | `length_required` | An upload through the gateway needs `Content-Length` |
| `412` | `precondition_failed` | A conditional header did not match |
| `413` | `payload_too_large` | The body is over the gateway's limit; use a presigned URL |
| `416` | `range_not_satisfiable` | The requested range lies outside the object |
| `503` | `database_starting` | The database is starting; retry after `Retry-After` |
| `502` | `platform_unavailable` | The platform service could not be reached |

Responses from the inference API and the database record API pass through
unchanged. Object bytes and Git protocol responses pass through as well;
storage and Git errors use the shape above.
