---
title: "Open-source Coding Harness Landscape"
type: research
status: complete
updated: 2026-09-23
tags: [agentic-ecosystem, coding-harness, evaluation]
---

# Open-source coding harness landscape

Question: which projects make DeepSeek Harness meaningfully comparable, and which differences should influence a future independent harness?

## Admission decision

The primary cohort must be open source, own an agent loop, change repositories or execute development commands, provide a repeatable CLI/SDK/server surface, and document enough execution, state, and authority behavior for an independent test. This admits DeepSeek Harness, OpenHands, OpenCode, Cline, goose, and SWE-agent. Aider is an adjacent lean editing baseline.

## Why these are comparable without being identical

- DeepSeek Harness is the explicit plugin-composition case.
- OpenHands is the SDK plus remote workspace/service case.
- OpenCode is the local client/server and ordered-permission case.
- Cline is the shared IDE/headless core and checkpoint case.
- goose is the MCP/ACP and portable-recipe case.
- SWE-agent is the research runner and trajectory case.
- Aider tests how far a smaller Git-native editing system can go.

The variation is useful because developers choose product boundaries before they choose individual features. Results must be grouped by task and operating model, not collapsed into a universal score.

## Source revisions

| Project | Reviewed revision | Release context | License |
|---|---|---|---|
| DeepSeek Harness | `46a7f68b0922371ce7144b668b90e377d8e799f4` | `0.1.7-rc.1` | MIT |
| OpenHands SDK | `5b36cacccc2bbe6f8fbce9e1d3ff4b0a3dcddadb` | `v1.49.5` | MIT |
| OpenCode | `7cb044ee892fa8116610ba31a82922c656eaf86c` | `v1.18.32` | MIT |
| Cline | `9c0e4aaee09f6593eb8d06ec4a35bf19b7dc33f1` | current monorepo | Apache-2.0 |
| goose | `e678c3b64a1dfd3c262a6a2019f158d33d5dcab0` | `v1.52.0` | Apache-2.0 |
| SWE-agent | `3ea751c087f32b16e039a2233dd6eefecef325d5` | `v1.1.0` | MIT |
| Aider | `5dc9490bb35f9729ef2c95d00a19ccd30c26339c` | `v0.86.0` | Apache-2.0 |

## Cross-project lessons

1. **Separate kernel, runtime, and client.** OpenHands and Cline show two ways to reuse one loop across application surfaces; OpenCode shows the value of a stable local server contract.
2. **Persist causal lifecycle, not only chat.** DeepSeek's event journal, OpenCode's session operations, Cline's checkpoints, and SWE-agent's trajectories cover different parts of recovery. Our design needs submission IDs, terminal outcomes, event history, and workspace/effect reconciliation together.
3. **Authority has layers.** Tool permission rules do not replace an outer sandbox. Extension, recipe, plugin, skill, and child-agent provenance also changes authority.
4. **Portable configuration is executable.** DeepSeek patches, goose recipes, OpenCode agents, Cline plugins, and SWE-agent configs can activate tools or code. Their resolved forms belong in run artifacts.
5. **Evidence should outlive the UI.** SWE-agent's exact queries and environment state are a useful floor; independent diffs, effects, and cleanup observations still remain necessary.
6. **Smaller is a legitimate architecture.** Aider shows that repository maps, edit protocols, and Git recovery can solve a focused problem with less lifecycle machinery.

## Exclusions for this pass

Continue and other IDE-first assistants remain discovery candidates. Roo Code's current upstream repository is archived, so it is not a primary active candidate. Closed-source or subscription-only harnesses can later be evaluated behaviorally, but cannot receive the same source-review depth. Frameworks such as AutoGen stay in the framework/orchestration track.

## Next implementation order

1. Define the neutral whole-harness run record and independent observer.
2. Implement the small repository fixture and interruption/effect fixture.
3. Start with SWE-agent for artifact completeness and one local harness for interactive lifecycle coverage.
4. Add SDK/server adapters for DeepSeek Harness, OpenHands, OpenCode, Cline, and goose.
5. Add Aider only to applicable editing tasks and mark unsupported lifecycle dimensions.
6. Run repeated native-model trials only after contract tests prove equivalent inputs, budgets, and outcome classification.

Related: [public comparison](../../docs/harnesses/comparison.md), [separate-track decision](../decisions/003-separate-harness-track.md), [research backlog](backlog.md).
