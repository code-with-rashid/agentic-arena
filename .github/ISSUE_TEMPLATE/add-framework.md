---
name: Add / complete a framework adapter
about: Implement one of the stub adapters, or add a brand-new framework
title: "adapter: <framework> for <arena>"
labels: ["adapter", "good first issue"]
---

## Framework

- Name / package:
- Version to pin:
- Docs link:

## Scope

- [ ] `frameworks/<name>/adapter.py` implements the `Framework` protocol
- [ ] LLM client wired to `config.base_url` / `config.api_key` / `config.model`
- [ ] Shared `arena.tools.search` / `arena.tools.calculator` registered unchanged
- [ ] `AgentResult` populated: `output_text`, `tool_calls`, token counts, `llm_calls`
- [ ] `frameworks/<name>/requirements.txt` pinned
- [ ] `frameworks/<name>/README.md` notes anything non-obvious
- [ ] `python -m arena run --arena tool_use --framework <name> --mode mock` is green
- [ ] Row added to the framework table in `README.md`
- [ ] `docs/frameworks/<name>.md` deep-dive stub filled in
- [ ] (if you have a key) committed a `--mode live` `results/` refresh

## Notes

<!-- Anything the framework makes awkward: streaming, tool-call history, token usage, async, etc. -->
