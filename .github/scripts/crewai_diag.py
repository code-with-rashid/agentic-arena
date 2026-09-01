"""Is CrewAI using native function calling, or its text ReAct fallback?"""

import json
import sys
from dataclasses import replace

from arena.config import ArenaConfig
from arena.llm.mockserver import MockServer
from arena.registry import load_arena, load_framework

arena = load_arena("tool_use")
item = arena.dataset[0]

with MockServer(arena.mock_script_path) as server:
    config = replace(ArenaConfig(mode="mock"), base_url=server.base_url, api_key="mock-key")
    runner = load_framework("crewai").build(arena, config)

    llm = runner.llm
    print("model string      :", getattr(llm, "model", "?"))
    print(
        "tool objects      :",
        [(type(t).__name__, getattr(t, "name", "?")) for t in runner._probe_tools]
        if hasattr(runner, "_probe_tools")
        else "n/a",
    )
    for probe in ("supports_function_calling", "is_litellm_model"):
        fn = getattr(llm, probe, None)
        if callable(fn):
            try:
                print(f"{probe:<18}:", fn())
            except Exception as exc:  # noqa: BLE001
                print(f"{probe:<18}: raised {exc}")

    try:
        runner.run(item)
    except Exception as exc:  # noqa: BLE001
        print("run raised:", type(exc).__name__, exc)

    print("requests seen     :", len(server.requests))
    for n, r in enumerate(server.requests):
        print(f"--- request {n} messages ---")
        for m in r.get("messages", []):
            c = str(m.get("content"))
            if m.get("role") == "user" and "Observation" in c:
                print("  [OBSERVATION TAIL]", c[-900:].replace(chr(10), " | "))
            else:
                print(f"  [{m.get('role')}] {c[:200]}")
    if server.requests:
        req = server.requests[0]
        print("advertised tools  :", [t["function"]["name"] for t in req.get("tools", []) or []])
        print("stop param        :", req.get("stop"))
        print("first msg (300c)  :", json.dumps(req.get("messages", [])[:1])[:300])
    sys.stdout.flush()
