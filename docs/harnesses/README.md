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

## Current profiles

| Harness | Review state | What you can conclude |
|---|---|---|
| [DeepSeek Harness](deepseek-harness.md) | Source-reviewed at `46a7f68` (`0.1.7-rc.1`); not locally benchmarked | Architecture, integration boundary, current limitations, and transferable design lessons |

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

This first profile establishes the method. More harnesses should enter only
after the same source review and bounded execution path exist.
