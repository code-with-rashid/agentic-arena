# Coding harness comparison

This matrix compares documented system shape. It does not rank task quality,
speed, cost, safety, or reliability. Every project below is source-reviewed at
a pinned revision and remains **not locally benchmarked** by Agentic Arena.

## Admission rule

A primary comparison candidate must be open source, own an agent loop, modify a
repository or run development commands, and expose a repeatable CLI, SDK, or
server path. It must also reveal enough about execution, state, and authority to
design an independent experiment. Aider is retained as an adjacent baseline:
it deliberately covers a narrower pair-programming workflow.

## System shape

| Project | Product center | Automation surface | Execution boundary | Durable evidence |
|---|---|---|---|---|
| [DeepSeek Harness](deepseek-harness.md) | Plugin-composed coding application | TypeScript/Python SDK over subprocess JSON-RPC; headless and ACP profiles | Profile-selected local tools and policy; `sdk-minimal` exposes a broad local shell | Append-only session events and generation-versioned JSONL |
| [OpenHands](openhands.md) | Embeddable SDK plus remote Agent Server and application | Python SDK, REST/WebSocket server, TypeScript client | Local workspace or ephemeral Docker/Kubernetes-style workspace | Event-driven conversations with persistence and pause/resume APIs |
| [OpenCode](opencode.md) | Local coding agent with client/server architecture | Headless HTTP/OpenAPI server and in-process SDK | Local process tools; permissions govern action use and external directories | Addressable sessions, messages, status, diffs, forks, abort, revert, and events |
| [Cline](cline.md) | Shared agent core across IDE, CLI, desktop, and SDK | Headless CLI and Node SDK | Local workspace tools governed by approval policy | Durable sessions plus Git-backed workspace checkpoints and restore |
| [goose](goose.md) | Local general agent with coding capabilities | CLI, API/server, recipes, and ACP | Local extensions; sandbox and tool permissions are configuration choices | Sessions plus portable recipe definitions and structured responses |
| [SWE-agent](swe-agent.md) | Research runner for repository problem solving | CLI and Python configuration/API | SWE-ReX deployment abstraction for local/container/remote environments | JSON trajectories with prompts, actions, observations, state, and model statistics |
| [Aider](aider.md) | Terminal pair programmer | CLI and Python scripting | Direct local repository and commands | Chat history and Git commits/diffs; narrower run lifecycle |

## Authority, extension, and delegation

| Project | Approval or policy model | Extension model | Delegation | Main comparison caution |
|---|---|---|---|---|
| DeepSeek Harness | Permission presets and policy plugins; SDK approval round trip is not implemented in the reviewed protocol | Cordis plugins, bundles, MCP, skills | Pluggable subagent providers | Profiles change most of the evaluated system |
| OpenHands | Security analyzer and action-confirmation policy | Tools, skills, hooks, plugins, MCP | SDK supports multi-agent construction | Local and remote workspace configurations are different conditions |
| OpenCode | Ordered `allow`/`ask`/`deny` rules by action and resource | Custom tools, MCP, skills, plugins | Named subagents with their own policies | Permission rules control tools but are not an outer sandbox |
| Cline | Tool auto-approval and interactive approval policies | MCP, plugins, rules, skills, SDK tools | SDK advertises multi-agent teams | IDE and headless hosts must be recorded separately |
| goose | Tool permission controls; upstream recommends outer isolation for risky work | MCP extensions and reusable recipes | Independent subagents; reviewed self-test forbids nested delegation | A recipe can add executable extensions and must be treated as code |
| SWE-agent | Command blocklists, parsers, timeouts, and configurable correction paths | Tool bundles, hooks, templates, deployments | Retry/review loops rather than a general interactive subagent product | Benchmark-oriented defaults should not be generalized to interactive UX |
| Aider | User interaction and Git recovery rather than a general capability policy | Coder/edit formats and configuration | No general subagent layer in the reviewed scope | Smaller scope makes feature-count comparisons misleading |

## Which design is most informative?

- Study **DeepSeek Harness** for explicit plugin lifecycle, durable facts versus
  live signals, and unknown tool outcomes.
- Study **OpenHands** for SDK/application separation, event-driven agent state,
  and remote workspace boundaries.
- Study **OpenCode** for a local server API, causal session operations, and
  ordered per-resource permissions.
- Study **Cline** for one core spanning IDE and headless use, durable abort
  recovery, and workspace rewind semantics.
- Study **goose** for MCP-first capability composition, portable workflows, and
  extension supply-chain questions.
- Study **SWE-agent** for experiment configuration and trajectories that retain
  exact prompts, actions, observations, environment state, and usage.
- Study **Aider** for repository maps, edit-format evaluation, and Git as a
  simple user-visible recovery mechanism.

## Proposed executable comparison

Begin with one small repository repair and one interrupted side-effect task.
Run the same exact model and budgets through each supported headless surface.
Record the resolved harness configuration, outer runtime, permissions, prompts,
tools, network, and retry behavior. Score tests, repository diff, process
cleanup, effect IDs, and secrets exposure outside the harness.

Report two layers:

1. **Task outcome:** independently verified pass, fail, timeout, harness error,
   unsupported, or unknown effect.
2. **System behavior:** model calls, tokens, tool calls, approvals, retries,
   context growth, elapsed time, recovery, and retained artifacts.

One run cannot establish quality. Repeat trials and confidence intervals come
after the runner proves it can preserve these distinctions.
