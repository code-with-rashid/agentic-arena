# Functional tests using a Codex subscription

The `codex` mode exercises real model responses through an experimental local
Chat Completions translation layer. It uses the supported `codex exec` command
and its saved ChatGPT sign-in. It does not extract tokens, create an OpenAI API
key, or reuse browser cookies.

## Run an arena

Install the Codex CLI and sign in using `codex login`. Verify `codex login status`
reports ChatGPT authentication, then run:

```bash
python -m arena run --arena tool_use --framework vanilla --mode codex --item tu-01
python -m arena run --arena tool_use --framework vanilla --framework langgraph --mode codex
python -m arena summary --mode codex --print
```

Install each framework's dependencies before selecting it. `ARENA_CODEX_MODEL`
selects the Codex model (default `gpt-6-astra`) independently of the API-oriented
`ARENA_MODEL`. Each request has
a 180-second client timeout by default, configurable with
`ARENA_REQUEST_TIMEOUT_S`. The subprocess times out before the client.

The harness starts and stops a localhost bridge for each run with a fresh local
key. Its raw traces are marked `mode: codex`; scorecards live in
`runs/codex-scorecards/<arena>/`, and the summary is `runs/codex-summary.md`.
Nothing is published to `results/`.

## Standalone OpenAI-shaped endpoint

For another local client, start the bridge from PowerShell:

```powershell
$env:ARENA_BRIDGE_KEY = 'choose-a-local-password'
python -m arena.llm.codex_bridge --model gpt-6-astra --port 8765
```

Point the client at `http://127.0.0.1:8765/v1`, use the same local password as
its API key, and request exactly the model selected above. This password only
protects the local server. Codex authenticates separately through its saved
login. Stop the server with Ctrl+C. Use the integrated `--mode codex` command
for arena runs so reports retain the correct provenance.

## What this tests

Adapters receive real, unscripted assistant text and tool requests. The adapter
executes the shared tools, sends their results back, and handles validation,
orchestration, approvals and resume. The bridge never executes requested tools
itself and never receives expected answers or scorer checks.

Each HTTP request starts an ephemeral Codex invocation in an empty temporary
directory, with user configuration, shell tools, plugins, apps and several other
tools disabled. The whole supplied conversation is encoded in a prompt. Codex
returns a structured envelope, which becomes a Chat Completions response.

## Limits of the evidence

- This is **functional testing, not a native OpenAI API benchmark**. Codex adds
  instructions, a JSON envelope and process overhead. Model tool calls are
  translated from that envelope rather than native Chat Completions calls.
- Temperature is accepted for adapter compatibility but not applied. The bridge
  fixes Codex reasoning effort to `low`; subscription model availability and
  usage limits still apply.
- Reported tokens are the CLI's observed usage, including Codex context and the
  transport envelope. They cannot establish native framework prompt overhead.
  API pricing is not applicable; a zero cost estimate does not mean free usage.
- Only non-streaming text Chat Completions and function tools are supported.
  Unsupported options such as `stop` and native `response_format` are rejected,
  rather than silently advertised as working. This excludes adapters needing
  those options. Only one request runs at a time; concurrent requests get 429.
- Run one Codex bridge process at a time on a host. The request lock belongs to
  one bridge process, so two separate arena commands can still compete for the
  same Codex account and produce transient failed turns. Sequential retries are
  safe because raw runs are timestamped and kept separately.
- Scripted resilience faults remain mock tests. A real model answering the
  resilience prompts does not prove recovery from the mock's injected faults.
- Use a real API endpoint later to verify native protocol behavior, controlled
  sampling, provider errors, token accounting and publishable comparisons.

References: [Codex authentication](https://learn.chatgpt.com/docs/auth) and
[non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode).
