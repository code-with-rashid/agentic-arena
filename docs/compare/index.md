# Choose what you are comparing

Agentic Arena compares two different kinds of developer choice. Pick the system
boundary first; the relevant evidence and methodology follow from it.

<div class="comparison-gateway">
  <a class="comparison-choice" href="../frameworks/">
    <span class="comparison-choice__label">Building blocks</span>
    <h2>Choose a framework or SDK</h2>
    <p>You are building an agent application and need orchestration, tools, state, approvals, or delegation primitives.</p>
    <strong>Compare frameworks →</strong>
  </a>
  <a class="comparison-choice comparison-choice--harness" href="../harnesses/">
    <span class="comparison-choice__label">Complete developer system</span>
    <h2>Choose a coding agent or harness</h2>
    <p>You need an environment that already owns prompts, tools, execution, permissions, persistence, and user interaction.</p>
    <strong>Compare coding harnesses →</strong>
  </a>
</div>

## The distinction in sixty seconds

| | Framework or SDK | Coding agent or harness |
|---|---|---|
| **What you receive** | Primitives used inside an application you design | A working developer experience around a model |
| **Usually owns** | Orchestration, tool registration, state APIs, handoffs, tracing | Prompts, context selection, tools, execution, permissions, sessions, UI, recovery |
| **You still choose** | Product UX, execution environment, policy, storage, most operational behavior | Model, workspace, authority, configuration, and operating environment |
| **Examples here** | LangGraph, Pydantic AI, OpenAI Agents SDK, Google ADK | OpenHands, OpenCode, Cline, goose, SWE-agent, Aider |
| **Fair comparison** | Hold model, tools, tasks, datasets, and scorer fixed | Hold task repository, model, runtime, authority, budgets, and final-state checks fixed |

Do not put both kinds of system in one score table. A complete harness owns many
variables that the framework experiment deliberately holds fixed.

## Start with the decision, then inspect the evidence

<div class="arena-card-grid arena-card-grid--compact">
  <a class="arena-card" href="../decision-guide/"><h3>Apply your constraints</h3><p>Turn deployment, control, recovery, and dependency requirements into a shortlist.</p></a>
  <a class="arena-card" href="../findings/"><h3>Read measured findings</h3><p>See what Agentic Arena has actually observed and the command that regenerates it.</p></a>
  <a class="arena-card" href="../labs/evidence-workspace/"><h3>Check whether claims compare</h3><p>Build two evidence records and expose mismatched modes, models, datasets, or scorers.</p></a>
  <a class="arena-card" href="../methodology/"><h3>Audit the method</h3><p>Inspect controls, unsupported states, scoring, and the boundary of every claim.</p></a>
</div>

## Framework questions

| Your question | Open |
|---|---|
| Does a framework support a capability? | [Feature matrix](../feature-matrix.md) |
| How much machinery does it add to the same task? | [Framework overhead](../overhead.md) |
| How does it behave when a provider fails? | [Transport failures](../transport.md) |
| What does delegation cost? | [Multi-agent comparison](../multi-agent.md) |
| How are tool contracts represented? | [Tool schemas](../tool-schemas.md) |

## Coding-harness questions

| Your question | Open |
|---|---|
| Which complete systems belong in the comparison? | [Coding-harness overview](../harnesses/README.md) |
| How do their system boundaries differ? | [Coding-harness matrix](../harnesses/comparison.md) |
| What evidence exists for a specific harness? | Open its profile and read the evidence banner first |
| How will Agentic Arena run them fairly? | [Harness admission and experiment contract](../harnesses/README.md#what-a-fair-harness-comparison-holds-fixed) |

## Evidence behind both routes

[Evaluation arenas](../arenas/README.md) define the workload and scorer. The
[fairness controls](../fairness-controls.md) state what must remain fixed. The
[profile evidence guide](../reference/profile-evidence.md) explains source
reviews, diagnostics, mock tests, native-live runs, freshness, and independent
reproduction.
