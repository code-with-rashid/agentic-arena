---
title: "Maintenance Workflow"
type: guide
status: active
updated: 2026-09-18
tags: [agentic-ecosystem]
---

# Maintenance Workflow

## After meaningful work

1. Update the affected project or initiative note, not every index.
2. Attach sources or experiment artifacts and label evidence type.
3. Update the review date only for material actually checked.
4. Add an entry to the research log or create a dated follow-up.
5. Update the delivery plan if scope or sequencing changed; make a decision record for major direction changes.
6. Check relative links using the repository's existing documentation link tests.

## Suggested review cadence

Review active integrations and protocol/security claims every 30 days, reference-only profiles every 90 days, and immediately after dependency/security/architecture changes relevant to a claim. This is a manual maintenance policy, not an installed scheduler or promise of background monitoring.

Before issuing a recommendation, refresh relevant sources even if their cadence has not elapsed. Record unavailable sources as unverified, preserving the last known evidence.

## Obsidian and Git

Open knowledge/ as a vault. Use standard relative Markdown links, YAML properties, search, backlinks, graph view, and templates. Configure the built-in Templates plugin to use templates/ if desired. Shared app settings keep links portable. Personal workspace files, caches, and plugins are ignored.

Use Git review for shared knowledge; avoid simultaneous Git and another sync system writing conflicting versions. No Obsidian installation or account is needed to consume the Markdown.

## Contributor checklist

Each new profile states purpose, domain, sources, review depth, execution status, relevance, limitations, and next step. Each experiment follows [the template](../templates/experiment.md). Recommendations are revisited when evidence changes.

Run from the repository root: `python -m pytest tests/test_doc_links.py -q`. The tests cover relative links, heading anchors, and documentation reachability. External URLs require a deliberate source review.

## Ownership and migration

The project maintainer owns prioritization; the contributor making a claim owns its evidence. Never delete an old decision solely because it changed; mark it superseded and link its replacement. If a canonical page moves, update backlinks in the same change.

