---
title: Repository scope, attention, and navigation research
date: 2026-09-27
status: decided
tags:
  - strategy
  - repository-design
  - information-architecture
  - open-source
---

# Repository scope, attention, and navigation research

## Question

Should Agentic Arena keep education, framework comparison, and complete coding
harness comparison in one repository, or split them into focused repositories?
Could a broad repository make visitors lose their way or receive less attention?

## Conclusion

Keep the three areas in Agentic Arena. They serve the same developer journey and
share a vocabulary, evidence method, examples, and maintenance process. Present
them as separate routes rather than as one undifferentiated catalog.

The future production harness remains a separate repository. It will be an
independently installed and released product with its own runtime dependencies,
security surface, compatibility promises, and issue lifecycle. Agentic Arena can
document and evaluate it under the same rules as every other harness.

The useful principle is **one entry point, several bounded journeys, and one
shared evidence system**.

See [Decision 004](../decisions/004-one-repository-bounded-journeys.md).

## What repository attention suggests

GitHub stars are an imperfect attention signal. They are affected by project
age, brand, distribution, timing, and whether a repository contains something
immediately runnable. They do not measure quality and cannot prove that scope
caused popularity. The snapshot below was collected from the GitHub repository
API on 2026-09-27 and is used only to test the claim that focused repositories
always receive more attention.

| Pattern | Examples in the snapshot | Observed signal |
|---|---|---|
| Focused education | [AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners), 75.9k; [12 Factor Agents](https://github.com/humanlayer/12-factor-agents), 26.4k | A clear curriculum or memorable set of principles can attract substantial attention. |
| Focused developer product | [Aider](https://github.com/Aider-AI/aider), 49.2k; [LangGraph](https://github.com/langchain-ai/langgraph), 42.4k; [SWE-agent](https://github.com/SWE-agent/SWE-agent), 20.4k | Each repository communicates one recognizable job and provides runnable software. |
| Focused evaluation product | [Promptfoo](https://github.com/promptfoo/promptfoo), 25.5k; [OpenAI Evals](https://github.com/openai/evals), 19.5k | A concrete evaluation workflow gives a technically broad implementation a focused reason to exist. |
| Broad platform or runnable collection | [LangChain](https://github.com/langchain-ai/langchain), 147.2k; [Awesome LLM Apps](https://github.com/Shubhamsaboo/awesome-llm-apps), 140.0k; [OpenHands](https://github.com/OpenHands/OpenHands), 89.3k | Broad coverage can succeed when it sits behind one strong promise and produces immediate utility. |
| Broad directory | [E2B Awesome AI Agents](https://github.com/e2b-dev/awesome-ai-agents), 30.2k; [Awesome Agents](https://github.com/kyrolabs/awesome-agents), 2.8k; [Awesome LLM Agents](https://github.com/kaushikb11/awesome-llm-agents), 1.6k | Breadth by itself produces highly variable attention. An inventory is not automatically a useful product. |

Both focused and broad repositories succeed. The repeated pattern is a sharp
promise, a clear first action, useful or runnable material, predictable
organization, and a recognizable audience. Repository breadth alone does not
explain attention.

## Information-architecture evidence

- [Diátaxis](https://diataxis.fr/map/) treats tutorials, how-to guides,
  explanation, and reference as distinct user needs. It warns that allowing
  those forms to blur creates structural problems and prevents each form from
  doing its job well.
- Nielsen Norman Group recommends
  [progressive disclosure](https://www.nngroup.com/articles/progressive-disclosure/)
  for information-rich experiences: expose the common choices first and reveal
  secondary detail after the user expresses intent.
- Its guidance on
  [primary navigation](https://www.nngroup.com/articles/format-based-navigation/)
  also favors labels that give topic and purpose cues instead of labels based
  only on content format.
- [GitHub README guidance](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes)
  identifies the README as a visitor's usual first encounter and recommends
  explaining why the project is useful, what people can do with it, and how to
  use it.
- Microsoft's account of
  [working with a monorepo](https://devblogs.microsoft.com/ise/working-with-a-monorepo/)
  describes the relevant tradeoff: one repository makes the full system and
  shared standards easier to see, while growth in size and complexity requires
  simple top-level directories, guidance, and discipline.

These sources support separation by user need inside the experience. They do
not imply that every content type needs a separate Git repository.

## Applying the evidence to Agentic Arena

The three areas are consecutive questions from the same audience:

1. **Education:** How do agentic systems work?
2. **Building:** What machinery and contracts would I need to create?
3. **Framework comparison:** Which library or SDK supplies useful building
   blocks?
4. **Coding harness comparison:** Which complete developer environment fits the
   work, authority, and recovery requirements?
5. **Evaluation:** How can I verify any of those claims?

They share the concepts of model access, tools, context, state, authority,
execution, recovery, and evaluation. Splitting the content would duplicate
definitions and evidence rules, fragment cross-links, and make the complete
developer journey harder to see.

The visitor risk is real, but it occurs when all material competes at the same
level. The public site should therefore keep its goal-based entrance and reveal
specialized material after a route is chosen. In particular, the Compare entry
should first ask whether the reader is choosing:

- a framework or SDK used to build an agent application; or
- a complete coding harness that owns prompts, tools, execution, permissions,
  persistence, and interaction.

Evaluation arenas and methodology support both choices. They should appear as
evidence behind those routes rather than as competing product categories.

## Repository boundary test

Keep material in Agentic Arena when it shares the audience, concepts, evidence,
examples, and publishing lifecycle. Consider a separate repository when most of
the following become true:

- it is independently installed or deployed;
- it needs independent versions and releases;
- it has a distinct security or compatibility promise;
- its contributors and issue lifecycle are substantially independent;
- changes rarely need coordinated updates to the shared knowledge and evidence;
- repository size, checkout cost, or CI isolation becomes a material burden.

Under this test, the education and both comparison tracks stay together. The
planned production harness belongs in its own repository.

## Product implication

Agentic Arena should describe itself as a framework-neutral field guide and
evidence lab for understanding, building, and choosing agentic developer
systems. It should not promise an unstructured collection of everything about
agents. Ecosystem breadth remains the destination, while each page and
experiment must answer one bounded developer question.

