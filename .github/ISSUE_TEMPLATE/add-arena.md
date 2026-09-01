---
name: Add an arena
about: Propose or implement a new reference task
title: "arena: <name>"
labels: ["arena"]
---

## What it exercises

<!-- e.g. multi-agent handoffs, retrieval, structured output, human-in-the-loop, durable state -->

## Spec

- [ ] `arenas/<name>/arena.toml` — id, description, `tools`, `system_prompt_intent`
- [ ] `arenas/<name>/dataset.jsonl` — >= 15 items with mechanical `checks`
- [ ] `arenas/<name>/mock_script.json` — canned turns so it runs offline
- [ ] New check types (if any) added to `arena/scorer.py` + tested
- [ ] `README.md` arenas table + `ROADMAP.md` updated
- [ ] At least the `vanilla` adapter passes it in mock mode

## Scoring approach

<!-- How does an item pass? Keep checks mechanical. If it needs an LLM judge, say so
     explicitly and label the arena accordingly. -->
