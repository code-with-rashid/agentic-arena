# Run modes and evidence levels

The three modes answer different questions. Choose the claim first, then the run.

| Mode | Use it to answer | Model access | Publish as benchmark? |
|---|---|---|---|
| `mock` | Is the adapter wired correctly? What framework mechanics remain when responses are fixed? | Deterministic local server | No |
| `codex` | Does the end-to-end path work with real model responses on an existing subscription? | Codex sign-in | No |
| `live` | How do adapters compare against the same native provider and model? | OpenAI-compatible API key | Yes |

## Mock mode

Use mock mode for fast, repeatable development and for measurements that remain valid when the model output is held constant: prompt bytes, retry behavior, pause mechanics, and orchestration calls. A high pass rate proves plumbing, not intelligence.

## Codex mode

Use Codex mode as a functional bridge when you have a ChatGPT/Codex subscription but no provider API key. It exercises real responses, but the translation layer means latency, token accounting, and cost are not comparable with native APIs. See the [Codex bridge guide](../codex-bridge.md).

## Live mode

Use live mode when you can hold the provider, model, tools, task, and scoring constant across adapters. These scorecards may support native latency, usage, cost, and answer-quality claims. Record the model and framework versions and repeat the run so later readers can judge freshness and stability.

Continue with [Methodology](../methodology.md) for the full comparison contract.
