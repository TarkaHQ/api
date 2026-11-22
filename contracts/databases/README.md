# Database data API contracts

`pocketbase-compat-vectors.json` pins how the PocketBase-compatible HTTP
endpoints of a managed database translate to
`tarka.databases.v1.DatabaseService`, which is the canonical data API. Tarka's
HTTP facade and database runtime are both tested against these cases, so a
client using a PocketBase SDK and a client using gRPC observe the same
behavior.

Each case names one RPC and describes the same exchange twice:

| Field | Meaning |
| --- | --- |
| `http_request` | Request a PocketBase client sends, relative to the database's data root. `query` holds single-valued parameters. A body is `json` or a list of `multipart` parts. |
| `grpc_request` | The equivalent request message in protobuf JSON with proto field names. `org_id` and `database_id` are bound by the endpoint and omitted. |
| `engine_request` | Present only when the request the runtime replays internally differs from `http_request`. Typed values travel in one `@jsonPayload` part so they keep their JSON types. |
| `http_response` | Status and `body` (`body_array` for batches, `body_base64` for files, `sse` for event streams) the PocketBase client receives. |
| `grpc_response` / `grpc_stream` | The response message, or the stream messages in order. |
| `grpc_error` | Status code and message of a rejected call, with the `RecordError` status detail. |

`status_mapping` lists the HTTP status for each gRPC code in both directions.
Where several HTTP statuses map to one code, the first entry is used when
translating back.

Multipart text parts follow PocketBase's inference: `true` and `false` become
booleans, numbers without a leading zero or plus sign become numbers, repeated
names become arrays, and everything else stays a string.

## Not preserved

- A query parameter given more than once keeps its last value.
- A `Range` header with several ranges is rejected with `416`; request one
  range per call.
- Uploads are buffered: a request, including all files, may not exceed 32 MiB.
- JSON key order and insignificant whitespace.
