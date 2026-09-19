---
title: "Evidence Rules"
type: guide
status: active
updated: 2026-09-18
tags: [agentic-ecosystem]
---

# Evidence Rules

## Claim categories

| Category | Required evidence | Allowed wording |
|---|---|---|
| Source claim | Primary URL, date, review depth; revision when available | The project documents… |
| Source inspection | File and immutable revision, relevant mechanism | The inspected code does… |
| Measured | Command, versions/config, dataset/scorer identity, artifact, repetitions | Under these conditions we observed… |
| Inference | Linked premises plus uncertainty | We infer… |
| Proposal | Decision/initiative and explicit not-implemented status | We propose… |
| Unknown | Missing evidence and next verification step | Not assessed… |

A reviewed README is not an audited implementation. A probe fingerprint is not security certification. A framework trace is not independent proof of fixture effects.

## Experiment provenance

Record repository commit, dirty-tree status, harness/adapter versions, model and gateway identity (no keys), protocol mode, dataset/scorer hashes, environment/image identity, policy configuration, seeds where supported, repeat count, command, date, and artifact location. Record failures and exclusions with denominators.

Claims about defaults and configured maximums must be separate. Pin source URLs before importing code or reproducing numeric claims. Verify license and attribution at that revision before reuse.

## Canonical ownership

- Code/tests: implemented behavior and invariants.
- results/ and published findings: measured claims within their stated scope.
- GitHub issues: implementation work and completion state.
- Vault: research, synthesis, decisions, source references, and links to evidence.

Conflict handling: retain the conflicting claims, point to their evidence, and mark unresolved until checked. Do not silently promote a stale narrative above a reproducible result. See [maintenance](maintenance.md).

