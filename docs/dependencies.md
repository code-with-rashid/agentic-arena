# Dependencies, pins, and deprecations

## The policy

- **The harness (`arena/`) has zero runtime dependencies.** Standard library only,
  including the mock LLM server, the JSON-schema checker, and the HTTP client. A
  PR that adds a runtime dependency to `arena/` needs a very good reason, because
  the harness is what every framework is measured *through* — its own footprint
  should not be part of the comparison.
- **`dev` is `ruff` + `pytest`.** Deliberately no frameworks: a plain test job must
  stay fast and installable everywhere. The consequence is that the wire-level
  contract tests can only see `vanilla` there, which is why they also run in the
  `comparison` CI job — see [methodology.md](methodology.md) §4.
- **`ruff` is pinned exactly; `pytest` is floored.** `ruff format --check .` is a
  CI gate, and both the formatter's output and the rules behind
  `select = [E, F, I, UP, B, SIM]` change across releases — a range lets a
  contributor's local `ruff format` disagree with CI and produce a diff nobody
  asked for. `pytest` has no such gate: the tests pass or they don't.
- **Every adapter pins exactly.** A scorecard records the library version it was
  produced with, so a bump invalidates that scorecard until it is re-run. Ranges
  are used only for adapters that are not yet verified (`crewai`).

## Current pins

| adapter | pins |
|---|---|
| `vanilla` | none — stdlib |
| `langgraph` | `langgraph==1.2.11`, `langchain-core==1.6.1`, `langchain-openai==1.6.0` |
| `pydantic_ai` | `pydantic-ai-slim[openai]==2.37.0` |
| `openai_agents` | `openai-agents==0.22.0` |
| `microsoft_af` | `agent-framework-core==1.16.0`, `agent-framework-openai==1.14.1` |
| `crewai` | `crewai>=0.130,<1.0` — a range, because the adapter is not yet verified |
| `claude_agent_sdk` | unpinned — deliberate stub |

Two adapters deliberately install the *narrow* package rather than the
meta-package: `pydantic-ai-slim[openai]` instead of `pydantic-ai`, and
`agent-framework-core` + `-openai` instead of `agent-framework`. The
meta-packages pull provider SDKs (azure, boto3, redis, qdrant, ollama, ...) that
no arena uses. This matters for install time and for honestly describing what a
framework costs to adopt for this task.

## Automation

`.github/dependabot.yml` opens one grouped PR per adapter, monthly. The cadence is
deliberately slow: the point is to make drift visible on a predictable schedule,
not to keep `main` on latest. A bump PR is reviewed by running the contract tests
and the mock sweep, and by checking the `comparison` job's overhead table — a jump
there means the library changed how it serialises tool schemas, which is itself a
finding worth recording in [overhead.md](overhead.md).

## What CI does and does not exercise

A green CI run on a bump PR is not the same as "this bump is verified". The gap
worth knowing about:

| action | used in | exercised by CI? |
|---|---|---|
| `actions/checkout` | every workflow | yes |
| `actions/setup-python` | every workflow | yes |
| `actions/upload-artifact` | `full-run.yml` only | **no** — that workflow is `workflow_dispatch` and needs `OPENAI_API_KEY` |

So an `upload-artifact` bump lands untested and first runs when someone triggers
a live run. It is a low-risk action, but if a `full-run` fails at the upload step
right after a bump, that is the first place to look.

`actions/checkout@v7` carries a breaking change — it blocks checking out fork PRs
under `pull_request_target` and `workflow_run`. This repo's workflows trigger on
`push`, `pull_request` and `workflow_dispatch` only, so it does not apply. Worth
re-checking if a workflow ever adopts one of those triggers.

## Deprecation register

Known upstream deprecations that affect an adapter, with the decision made about
each. An entry stays here until the adapter no longer triggers it.

### `langgraph.prebuilt.create_react_agent`

```
LangGraphDeprecatedSinceV10: create_react_agent has been moved to
`langchain.agents`. Please update your import to
`from langchain.agents import create_agent`.
Deprecated in LangGraph V1.0 to be removed in V2.0.
```

- **Where:** `frameworks/langgraph/adapter.py`
- **Status:** *not migrated, deliberately.*
- **Why not:** the replacement lives in the `langchain` package, which the adapter
  does not currently install — it depends on `langchain-core` only. `langchain`
  is also on a separate version track (1.3.x stable) from the pinned
  `langchain-core` (1.6.1), so adopting it means resolving a new top-level
  dependency against existing exact pins. LangGraph 2.0 is not released, and
  `create_react_agent` works correctly on the pinned 1.2.11 — all five arenas are
  green and the adapter passes every wire-level contract test.
- **Trigger to revisit:** LangGraph 2.0 reaching a release candidate, or a
  Dependabot bump that brings `langchain` in as a transitive dependency anyway.
- **Migration sketch:** add `langchain==<compatible>` to
  `frameworks/langgraph/requirements.txt`, swap the import to
  `from langchain.agents import create_agent`, and re-check the overhead table —
  a different agent constructor may serialise tool schemas differently, which
  would move LangGraph's position in [overhead.md](overhead.md).

Recording the decision is the point. An unexplained deprecation warning in CI
output is noise that everyone learns to scroll past; a dated entry with a trigger
is something the next person can act on.
