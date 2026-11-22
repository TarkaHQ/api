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

`…/api/*` is the database record API: `GET` and `POST`
`/api/collections/{collection}/records`, `GET`, `PATCH` and `DELETE`
`/api/collections/{collection}/records/{record}`,
`GET /api/files/{collection}/{record}/{file}`, `POST /api/batch`,
`GET /api/health`, and `GET` and `POST /api/realtime`.

Object storage, Hosted Git, the API and MCP gateway, and invoking other compute
are not part of this contract yet.

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
    "databases": {"enabled": true, "mode": "rules", "own": true, "project_default": true}
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

## Errors

Gateway errors use one JSON shape:

```json
{"error": {"type": "permission_error", "code": "capability_disabled", "message": "Database access is not enabled for this workload."}}
```

| HTTP | `code` | Meaning |
| --- | --- | --- |
| `403` | `platform_header_required` | The `Tarka-Workload: 1` header is missing |
| `403` | `forwarded_request_refused` | The request carries a browser or proxy header |
| `403` | `capability_disabled` | The route's capability is not enabled for this workload |
| `403` | `workload_unbound` | The container is not currently assigned to a workload |
| `404` | `database_not_found` | No database with that name is available to this workload |
| `503` | `database_starting` | The database is starting; retry after `Retry-After` |
| `502` | `platform_unavailable` | The platform service could not be reached |

Responses from the inference API and the database record API pass through
unchanged.
