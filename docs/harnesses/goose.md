# goose

goose is an open-source local agent for development and general workflows. It
offers desktop, CLI, server/API, and Agent Client Protocol surfaces. MCP
extensions provide most capabilities, while recipes package repeatable prompts,
settings, extensions, parameters, structured responses, retries, and
subrecipes.

**Evidence status:** source-reviewed on 2026-09-23 at `e678c3b`
(`v1.52.0`). Agentic Arena has not run it locally.

- [Official site](https://block.github.io/goose/)
- [Official repository](https://github.com/aaif-goose/goose)
- [Architecture](https://github.com/aaif-goose/goose/blob/e678c3b64a1dfd3c262a6a2019f158d33d5dcab0/documentation/docs/goose-architecture/goose-architecture.md)
- [Recipe reference](https://github.com/aaif-goose/goose/blob/e678c3b64a1dfd3c262a6a2019f158d33d5dcab0/documentation/docs/guides/recipes/recipe-reference.md)

## Distinguishing design

goose makes standard protocols central: MCP composes tools and resources, while
ACP connects editors and other agents. Recipes provide a portable workflow
artifact with declared inputs and optional structured output. Its current
surface also includes skills and independent subagents; the reviewed self-test
expects nested delegation to be rejected.

Tool permissions and sandbox mode can reduce authority, while upstream security
guidance still recommends a dedicated container or virtual machine for risky or
untrusted work. Extensions and recipe-declared commands remain executable
supply-chain inputs.

## What Agentic Arena should test

Run a pinned recipe through the CLI/API with a fixed extension set. Record every
spawned extension command, resolved permission, MCP identity, retry check, and
subagent. Compare an unrestricted local run with an outer-isolated run. A recipe
should be reviewed like code before it can enter a benchmark fixture.

goose teaches us that a portable workflow needs provenance for every capability
it activates. It also provides a useful model for protocol-first composition
and declarative, parameterized tasks.
