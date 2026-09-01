# `vanilla` — dependency-free baseline

A hand-rolled ReAct-style loop in ~90 lines using only the Python standard library
(`arena.llm.client` is stdlib `urllib`). No framework.

This adapter exists as the **control**: every other adapter's lines-of-code,
token overhead, and latency overhead are measured relative to "just write the loop."

- **Deps:** none.
- **LLM:** `arena.llm.client.ChatClient` against `config.base_url`.
- **Tools:** calls `arena.tools.dispatch` directly.
- **Loop:** up to `config.max_tool_iterations` tool rounds, then answers.

Run it:

```bash
python -m arena run --arena tool_use --framework vanilla --mode mock
```
