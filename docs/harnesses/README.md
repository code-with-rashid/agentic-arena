# Compare complete coding harnesses

A framework supplies building blocks. A coding harness owns the working
experience around a model: prompts, tools, execution, permissions, persistence,
and often delegation. Those extra choices are part of the product, so a harness
cannot be inserted into the framework overhead table without changing the thing
being measured.

Use this track when your question is **"Which complete environment helps an
agent finish development work safely and recoverably?"** Use the
[framework comparison](../compare/index.md) when your question concerns the
orchestration library inside an otherwise shared setup.

## Choose the comparison you need

There is no useful single ranking. The projects optimize for different jobs:

| If you need to decide about… | Compare first |
|---|---|
| A reusable application and remote runtime | [OpenHands](openhands.md), [DeepSeek Harness](deepseek-harness.md), [OpenCode](opencode.md), [Cline](cline.md) |
| A local, extensible developer agent | [OpenCode](opencode.md), [Cline](cline.md), [goose](goose.md) |
| Repeatable research or benchmark runs | [SWE-agent](swe-agent.md), then the other harnesses through the shared experiment contract |
| A lean terminal editing baseline | [Aider](aider.md) |
| Architecture and evidence differences across all of them | [Comparison matrix](comparison.md) |

## Current profiles

| Harness | Review state | What you can conclude |
|---|---|---|
| [DeepSeek Harness](deepseek-harness.md) | Source-reviewed at `46a7f68` (`0.1.7-rc.1`); not locally benchmarked | Architecture, integration boundary, current limitations, and transferable design lessons |
| [OpenHands](openhands.md) | Source-reviewed at `5b36cac` (`v1.49.5`); not locally benchmarked | SDK/server split, event-driven conversations, remote workspaces, and security hooks |
| [OpenCode](opencode.md) | Source-reviewed at `7cb044e` (`v1.18.32` release context); not locally benchmarked | Headless server/SDK surface, sessions, ordered permissions, and subagents |
| [Cline](cline.md) | Source-reviewed at `9c0e4aa`; not locally benchmarked | Shared IDE/CLI/SDK core, checkpoints, approvals, and headless operation |
| [goose](goose.md) | Source-reviewed at `e678c3b` (`v1.52.0`); not locally benchmarked | MCP-first extensions, portable recipes, ACP, permissions, and subagents |
| [SWE-agent](swe-agent.md) | Source-reviewed at `3ea751c`; not locally benchmarked | Configurable research runner, isolated deployments, and rich trajectory artifacts |
| [Aider](aider.md) | Adjacent baseline reviewed at `5dc9490`; not locally benchmarked | Git-native editing, repository maps, edit formats, and lower orchestration complexity |

An entry here is not an endorsement. Review state is part of the result.

## What a fair harness comparison holds fixed

Whole-harness evaluation needs a different contract from adapter evaluation:

| Control | Record it because |
|---|---|
| Task repository and starting revision | The available code and tests define the work |
| Model route and exact version | Model capability can dominate the result |
| Runtime image and network policy | A harness can only use what its environment exposes |
| Granted files, commands, secrets, and approvals | More authority can make a task easier and riskier |
| Wall-clock, token, model-call, and tool-call budgets | Unbounded retries conceal cost and failure |
| Harness version, profile, prompts, tools, and patches | These are the system under comparison |
| Independent final-state checks | A confident transcript is not proof of a correct change |
| Trace and artifact capture | Failures need evidence beyond the final answer |

Run each condition repeatedly and report exclusions, harness errors, timeouts,
task failures, and passes separately. Compare default and hardened profiles as
different configurations. Do not normalize away harness-owned prompts or tools;
they are part of what a developer is choosing.

## Admission path

1. Pin a source revision and review its license, architecture, execution model,
   permission boundary, persistence, and public integration surface.
2. Create a disposable fixture repository with objective checks and no valuable
   credentials or files.
3. Drive the harness through its supported automation interface. Capture the
   exact profile and configuration.
4. Score the resulting repository and external effects independently from the
   harness transcript.
5. Publish artifacts and limitations before making a comparative claim.

Source review establishes comparison vocabulary. Behavioral conclusions still
require the same bounded execution path for every admitted harness.
