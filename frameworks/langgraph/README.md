# `langgraph` adapter

Uses `langgraph.prebuilt.create_react_agent` with `langchain_openai.ChatOpenAI`
pointed at the shared gateway.

- **Deps:** see [requirements.txt](requirements.txt) (pinned).
- **LLM:** `ChatOpenAI(model=config.model, base_url=config.base_url, api_key=config.api_key)`.
- **Tools:** `arena.tools.search` / `calculator` wrapped with `@langchain_core.tools.tool`.
- **Metrics:** token counts summed from each `AIMessage.usage_metadata`; tool calls
  collected from `AIMessage.tool_calls`; final answer is the last non-empty
  `AIMessage.content`.

```bash
python -m pip install -r frameworks/langgraph/requirements.txt
python -m arena run --arena tool_use --framework langgraph --mode mock
```

Notes / caveats:

- `recursion_limit` is set from `config.max_tool_iterations` so a runaway loop fails
  cleanly instead of hanging.
- In mock mode the token numbers reflect how `langchain_openai` serialises the
  request, not real model usage — only `--mode live` numbers are published.
