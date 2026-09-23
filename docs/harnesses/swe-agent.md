# SWE-agent

SWE-agent is a research-oriented coding harness that takes repository problems
and attempts fixes with a selected language model. Configuration controls the
agent, prompts, tools, repository, deployment, and retry/review strategy.

**Evidence status:** source-reviewed on 2026-09-23 at `3ea751c`; latest tagged
release checked as `v1.1.0`. Agentic Arena has not run it locally.

- [Official repository](https://github.com/SWE-agent/SWE-agent)
- [Environment configuration](https://swe-agent.com/latest/reference/env_config/)
- [Agent API](https://swe-agent.com/latest/reference/agent/)
- [Trajectory format](https://swe-agent.com/latest/usage/trajectories/)

## Distinguishing design

The environment is built over a SWE-ReX deployment abstraction and a pinned
repository configuration. The agent loop is strongly configurable through
templates, tool bundles, parsing and correction behavior, hooks, limits, and
retry/review loops.

Its main strength for this comparison is evidence. A trajectory records each
model response, interpreted thought/action, observation, environment state, the
exact query shown to the model, history, model statistics, and replay
configuration. That makes experiment reconstruction a first-class concern.

## What Agentic Arena should test

Use SWE-agent as the initial research-runner baseline on a small pinned issue.
Verify that the trajectory and final patch agree with independent process and
filesystem observations. Exercise command rejection, malformed actions,
timeout, deployment loss, and repeated attempts. Report benchmark defaults
separately from any configuration adapted for interactive use.

SWE-agent teaches us to make the complete resolved experiment serializable and
to retain the exact model query at every step. It also shows why benchmark
infrastructure and day-to-day developer UX are different product questions.
