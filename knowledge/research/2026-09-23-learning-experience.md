---
title: Learning experience and information architecture research
date: 2026-09-23
status: implemented
tags:
  - documentation
  - ux
  - learning
  - information-architecture
---

# Learning experience and information architecture research

## Problem observed

The public site exposed more than forty navigation choices in one continuous
sidebar. Educational concepts, build instructions, troubleshooting, benchmark
findings, framework profiles, arena definitions, and project details competed
at the same level. The home page repeated that inventory. A visitor had to
understand the repository before the repository could teach them.

The repository also used two incompatible organizing ideas at once:

- task journeys such as Learn, Build, Choose, and Debug;
- content objects such as frameworks, arenas, findings, and methodology.

Both are useful, but mixing them in one flat navigation increases the number of
choices and makes the boundary between education and product comparison unclear.

## Research signals

The redesign combines four established approaches:

1. **Separate kinds of documentation.** [Diátaxis](https://diataxis.fr/) separates
   learning-oriented tutorials, goal-oriented how-to guides, information-oriented
   reference, and understanding-oriented explanation. We adapted this idea to
   four user-visible spaces: Learn, Build, Compare, and Reference. Compare is a
   project-specific evidence space because evaluation is a first-class product
   here rather than ordinary reference material.
2. **Reveal complexity after intent.** Nielsen Norman Group's
   [progressive disclosure guidance](https://www.nngroup.com/articles/progressive-disclosure/)
   recommends showing the most important options first and making the path to
   secondary choices obvious. The new home page asks for one goal and recommends
   one next step before exposing the full site.
3. **Organize around user needs.** GitHub's
   [content design principles](https://docs.github.com/en/contributing/writing-for-github-docs/content-design-principles)
   prioritize user goals, high-value scenarios, clarity, and “just enough” docs.
   Its [content model](https://docs.github.com/en/contributing/style-guide-and-content-model/about-the-content-model)
   uses consistent page types so returning readers can form a stable mental
   model. We use stable top-level rooms and section landing pages as maps.
4. **Keep orientation visible.** Material for MkDocs supports
   [top-level tabs, section navigation, and breadcrumb paths](https://squidfunk.github.io/mkdocs-material/setup/setting-up-navigation/).
   Those features now communicate the active room while keeping local choices in
   the sidebar.

The `truspec` project supplied the visual reference: one strong promise, a small
set of calls to action, spacious cards, and details deferred to dedicated pages.
Agentic Arena keeps its existing MkDocs toolchain but adopts the same restraint.

## Implemented structure

```text
Home
├── Learn       concepts and ordered curriculum
├── Build       executable lessons, task guides, troubleshooting
├── Compare     findings, decisions, dimensions, frameworks, arenas
├── Reference   run modes, methodology, controls, commands
└── Project     roadmap and maintenance material
```

The separation rule is semantic:

- **Learn** answers “how does this work?” without requiring a product choice.
- **Build** answers “how do I make or fix it?” with concrete action.
- **Compare** answers “what does the evidence say about my options?”
- **Reference** answers “what exactly is this command, mode, or contract?”

Pages may link across rooms, but they have one primary home. Learning pages can
use measured examples without turning into framework rankings. Comparison pages
can link to concepts without reteaching them.

## Interaction choices

- The homepage goal picker reduces the initial decision to four human questions.
- The learning path orders seven modules and states an outcome for each.
- Module completion is optional and stored in browser-local storage. It creates
  continuity without accounts, tracking, or repository state.
- Evidence levels appear near comparison entry points so readers know what a run
  can prove before seeing numbers.
- Search remains global for visitors who already know what they need.
- The experience works without JavaScript; interaction enhances static links and
  content rather than hiding essential information.

## Maintenance rules

1. Give every new public page one primary room.
2. Add a page to global navigation only when it is a stable destination.
3. Put advanced detail behind an explicit link or expandable section.
4. Start pages with the reader's question and the useful conclusion.
5. Label claims as measured, functional, claimed upstream, or unverified.
6. Keep personal research depth in the Obsidian vault; publish the distilled path.
7. Review navigation by user task, not by repository directory.

## Success checks

- A first-time visitor can choose Learn, Build, Compare, or Reference from the
  first screen without reading repository history.
- Framework names do not appear inside the ordered education navigation.
- A reader can identify what mock, Codex, and live modes prove before running one.
- Mobile and desktop navigation retain the same room structure.
- The site builds with strict link and navigation validation.
