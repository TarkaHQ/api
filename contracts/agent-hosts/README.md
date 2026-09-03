# Agent Host Compose contracts

These files are the public, versioned definitions for Tarka's built-in Agent
Host templates. They use the standard Compose model plus the `x-tarka`
extension for public routes, product tier, variable prompts, persistent volume
sizes, and template-driven onboarding metadata.

| Template | Tier | Services | Upstream starting point |
| --- | --- | ---: | --- |
| OpenClaw | Core | 2 | [Coolify OpenClaw](https://github.com/coollabsio/coolify/blob/main/templates/compose/openclaw.yaml) |
| Hermes Agent | Core | 2 | [Coolify Hermes Agent with Web UI](https://github.com/coollabsio/coolify/blob/main/templates/compose/hermes-agent-with-webui.yaml) |
| Onyx | Pro | 9 | [biralo-studio/onyx-docker-compose](https://github.com/biralo-studio/onyx-docker-compose/blob/main/docker-compose.yml) |

Tarka adapts the upstream files for the managed Kubernetes runtime: images are
pinned by immutable multi-platform digest, resource reservations and limits are
explicit, persistent volumes have quotas, public routes are declared, and
secrets are supplied through Agent Host variables. These are therefore not
drop-in replacements for the upstream projects' local-development files.

The Onyx template requires an initial administrator email, a unique
administrator password, and an authentication signing secret. Its backend
first starts on a pod-local listener; Tarka registers, authenticates, and
verifies that administrator before Onyx binds its service port. Only the Onyx
web proxy is published. This prevents an Internet client from claiming the
first-account administrator role on a fresh deployment.

Every running Agent Host also receives a private platform gateway at
`http://tarka`. Agent workloads call the OpenAI-compatible inference API at
`http://tarka/v1` without supplying a customer API key. A host-bound service
identity is held only by that gateway and is rejected by Tarka's public API
surfaces.

Schema version 2 templates declare a managed runtime profile and the messaging
gateways supported by that exact runtime. The profile selects a live Tarka chat
model, caps active context at roughly 80K tokens, enables automatic compaction,
and publishes utility-model modalities. Gateway YAML is non-secret; bot tokens
and other credentials are supplied as separately encrypted variables.

`catalog.json` is the machine-readable release index. Its SHA-256 checksums
cover the exact Compose bytes consumed by the infrastructure repository. CI
rejects mutable image references, metadata/catalog drift, and checksum drift.

## Custom stacks

Customers may also submit their own Compose file through the Agent Host API.
The runtime supports multi-service stacks, public Git builds, named persistent
volumes, service dependencies, health checks, internal networking, and one or
more HTTP routes. Host mounts, privileged containers, host namespaces, devices,
external networks, and Docker socket access are intentionally rejected.
Custom stacks may opt selected services into the managed Tarka model environment
without pretending the platform can configure an arbitrary application's own
gateway or compaction implementation.
