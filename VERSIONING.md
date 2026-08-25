# API versioning and compatibility

Tarka versions its public API at two related levels:

- Protobuf packages include a stability version, currently
  `tarka.provisioning.v1`.
- Repository releases use semantic tags such as `v1.0.0` so consumers can pin
  an immutable source and generated Go module revision.

Within a stable protobuf package, changes must remain wire-compatible and
source-compatible wherever Protocol Buffers permits it. Safe changes are
normally additive: new RPCs, new messages, and new fields with unused numbers.

Do not:

- change an existing field number or wire type;
- reuse a removed field number or name;
- move messages between packages;
- change an RPC's request, response, streaming shape, or fully qualified name;
- remove or reinterpret an enum value;
- remove an established HTTP binding; or
- make a previously optional behavior unconditionally required.

Removed fields and enum values must reserve both their old numbers and names.
An intentionally incompatible contract belongs in a new protobuf package such
as `tarka.provisioning.v2` and requires an explicit migration window.

Buf's `FILE` breaking policy enforces the mechanical portion of this contract.
Reviewers remain responsible for semantic compatibility, including field
meaning, validation, authentication, authorization, and HTTP behavior.

Generated artifacts are released from the same commit as their source. Tags
are immutable and must never be moved or recreated.
