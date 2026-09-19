# Execution boundaries and operations

A working model loop needs a separate execution contract: what may run, under
whose authority, with which resources, and how effects are observed. A tool
denial is application policy. An operating-system restriction is a different
layer with a different observer.

| Boundary | Useful for | Costs and gaps |
|---|---|---|
| Ordinary process | Trusted local functions and crash separation | Same user often retains filesystem/network authority |
| Container | Filesystem/network namespaces and resource constraints | Shared kernel, daemon trust, configuration and mounts matter |
| VM | Separate guest kernel and stronger workload separation | Startup, image lifecycle, resources and operational complexity |
| Remote service | Central policy, credential brokering and audit | Availability, identity, transport and remote effect reconciliation |

Use [AST](https://github.com/kajogo777/the-agent-sandbox-taxonomy)'s filesystem,
network, process, isolation, authentication/authorization, audit/logging and
escape-prevention vocabulary as **descriptive tags** for evidence. Do not inherit
a taxonomy rating or claim certification. Source reviewed 2026-09-19; our
[research note](../../knowledge/projects/agent-sandbox-taxonomy.md) records review depth.

## Opt-in local recipe

Prerequisites: Docker CLI, a running **local Linux container engine with cgroup
v2**, permission to use it, and a local Python 3.13 image. Linux engines and
Docker Desktop Linux containers are the intended targets. Windows containers,
cgroup v1 and unavailable engines are unsupported. This does not install or
reconfigure a runtime. Access to a Docker daemon is itself privileged host
authority; the workload never receives its socket, host mounts or privileged mode.

```bash
# Explicit network fetch, once; inspect the publisher/digest before reuse.
docker pull python:3.13-slim
python -m examples.isolation.recipe --image python:3.13-slim
# Reproduce later using the recorded repository digest instead of the mutable tag.
```

The recipe resolves the image to its immutable local ID before creating anything.
It starts one named, non-root container, disables network interfaces except
loopback, drops capabilities, sets no-new-privileges, uses a read-only root,
and grants a 1 MiB temporary filesystem. It configures 128 MiB memory, 0.5 CPU
and 32 processes. A 30-second client deadline bounds the probe; cleanup removes
only its uniquely named container and verifies absence.

The probe checks effective UID/capabilities, no-new-privileges, cgroup values,
read-only filesystem behavior and a small permitted temporary write/delete.
It inspects network interfaces without probing external services. Resource
settings are **observed configuration**, not adversarial exhaustion tests.
No credentials, host bind mounts, paid resources or production data are used.

The JSON artifact records engine version, image ID/digests, flags, source hashes,
observations and teardown. The Linux CI job runs this recipe; local execution
requires the above engine. Passing is not proof against escape or kernel flaws.
[Docker run](https://docs.docker.com/engine/containers/run/) and
[resource constraints](https://docs.docker.com/engine/containers/resource_constraints/)
were reviewed 2026-09-19; effective configuration is checked at runtime.

## Policy, credentials and auditing

A policy decision should bind identity, operation, exact arguments and policy
revision. Enforce it where effects happen; a prompt is not an enforcement point.
Deliver scoped short-lived credentials only to the component that requires them.
Keep secrets out of prompts, tool results and traces, and test rotation/revocation
separately. Deny when authorization cannot be evaluated; preserve the reason so
the harness can request help or continue permitted work.

The [boundary-response arena](../arenas/boundary_response.md) tests **simulated
tool decisions** through three adapters. This container recipe tests a limited
set of actual runtime properties. Neither substitutes for the other.

## From job to service

| Concern | Short job | Long-running service |
|---|---|---|
| Concurrency | Bound workers and total provider budget | Queue admission, per-tenant quotas, backpressure and fair scheduling |
| Recovery | Durable task ID, sink idempotency, restart checkpoint | Leases, fencing, reconciliation and duplicate-delivery handling |
| Health | Exit status plus useful-work result | Separate readiness, liveness, queue age and dependency health |
| Cleanup | Finally block, deadline and orphan sweep | Lease expiry, janitor, retention and ownership labels |
| Budget | Per-attempt, task and experiment ceilings | Tenant/service ceilings across retries and parallel workers |
| Incident | Preserve redacted provenance and effect evidence | Correlate task, policy, identity, provider and sink records |

The [reliability lesson](reliability.md) exposes the crash window; the
[evaluation workbench](evaluation.md) separates claims from effects. For an
incident, first establish whether evidence is complete, then locate the failed
boundary, replay only synthetic inputs, and verify recovery against the independent
sink. Distributed queues, production credentials and incident response automation
remain design topics, not implemented services.

