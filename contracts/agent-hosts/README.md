# Agent Host Compose contracts

These files are the public, versioned definitions for Tarka's built-in Agent
Host templates. They use the standard Compose model plus the `x-tarka`
extension for public routes, product tier, variable prompts, persistent volume
sizes, and template-driven onboarding metadata.

| Template | Tier | Services | Upstream starting point |
| --- | --- | ---: | --- |
| OpenClaw | Core | 2 | [Coolify OpenClaw](https://github.com/coollabsio/coolify/blob/main/templates/compose/openclaw.yaml) |
| Hermes Agent | Core | 2 | [Coolify Hermes Agent with Web UI](https://github.com/coollabsio/coolify/blob/main/templates/compose/hermes-agent-with-webui.yaml) |
| n8n | Core | 1 | [Official n8n Docker image](https://github.com/n8n-io/n8n/tree/n8n%402.41.3/docker/images/n8n) |
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

## CPU and memory

The standard managed templates share a two-vCPU maximum across their application
services. Their CPU scheduling requests are lower so idle hosts do not reserve
two full cores:

| Template | CPU request | CPU limit | Memory request | Memory limit |
| --- | ---: | ---: | ---: | ---: |
| Hermes Agent | 625m | 2 vCPU | 2.25 GiB | 7 GiB |
| OpenClaw, including browser | 750m | 2 vCPU | 3 GiB | 8 GiB |
| n8n | 500m | 2 vCPU | 1 GiB | 3 GiB |

These are aggregate application resources. The private platform gateway and
optional Signal bridge have separate, bounded overhead. Onyx remains a larger
multi-service template with its existing resource profile.

The core tier's 10 GiB memory quota is an upper bound, not an allocation of
physical RAM. Processes use physical memory as needed; a memory limit does not
preallocate empty pages. Kubernetes still accounts for each explicit memory
request when scheduling and admitting workloads. Requests are not automatically
reduced while a host is idle, and a process that retains allocations may need
to release them before its actual memory usage falls.

Hermes `0.21.2-tarka.2` and OpenClaw `2026.9.4-tarka.2` reduce CPU only; their
memory requests, memory limits, persistent volumes, and image digests are
unchanged. Existing saved revisions keep their previous CPU resources until
the owner applies the updated template through the normal configuration flow.

## n8n

The n8n template creates the initial owner using `N8N_OWNER_EMAIL` and the
encrypted `N8N_OWNER_PASSWORD` input before opening its public listener. Later
password, email, and MFA changes belong in n8n and survive host restarts. The
initial inputs do not reset an existing owner. The controller supplies the
public editor and webhook URLs from the assigned hostname.

Select **Tarka Inference** as the OpenAI credential in a workflow. This native
credential points at `http://tarka/v1`; its `tarka-local` key is a non-secret
SDK compatibility marker, replaced by the private platform gateway. The
reserved credential ID `tarkaInference` is refreshed on startup; create a
separate credential for other providers. Use Chat Completions and a live Tarka
model such as `qwen3.8-flash-next`. Support for the OpenAI Responses API,
Assistants, or other provider-specific APIs is not implied.

SQLite, workflows, encrypted credentials, and n8n's generated encryption key
persist together on the 10 GiB `n8n-data` volume. The template runs one instance
and prunes execution history after seven days. Back up the whole volume,
including its encryption key. n8n workflow nodes control their own context
and memory; the platform runtime profile does not install automatic workflow
compaction. The default model and utility aliases are available in the managed
runtime environment.

## Custom stacks

Customers may also submit their own Compose file through the Agent Host API.
The runtime supports multi-service stacks, public Git builds, named persistent
volumes, service dependencies, health checks, internal networking, and one or
more HTTP routes. Host mounts, privileged containers, host namespaces, devices,
external networks, and Docker socket access are intentionally rejected.
Custom stacks may opt selected services into the managed Tarka model environment
without pretending the platform can configure an arbitrary application's own
gateway or compaction implementation.
