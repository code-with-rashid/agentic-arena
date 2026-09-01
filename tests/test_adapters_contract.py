"""Every adapter must load, expose `name` + `lib_version`, and either build or raise
a clean NotImplementedError. This keeps stubs honest and catches import-time typos.
"""

import json
from dataclasses import replace

import pytest

from arena.config import ArenaConfig
from arena.llm.mockserver import MockScript, MockServer
from arena.registry import available_frameworks, load_arena, load_framework
from arena.types import ArenaSpec, EvalItem

STUBS = {"claude_agent_sdk"}

SENTINEL = "Reply only with the word ORNITHOPTER and nothing else."


def _sentinel_arena(tools):
    """An arena that shares nothing with tool_use, so a hard-coded prompt shows up."""
    return ArenaSpec(
        id="sentinel",
        description="sentinel",
        tools=list(tools),
        system_prompt_intent=f"\n{SENTINEL}\n",
        dataset=[],
        mock_script_path="",
    )


def _buildable_frameworks():
    """Adapters that are neither stubs nor missing their dependency."""
    out = []
    for name in available_frameworks():
        if name in STUBS:
            continue
        try:
            load_framework(name).build(_sentinel_arena(["search"]), ArenaConfig(mode="mock"))
        except Exception:  # noqa: BLE001 - dependency not installed in this env
            continue
        out.append(name)
    return out


BUILDABLE = _buildable_frameworks()


@pytest.mark.parametrize("name", available_frameworks())
def test_adapter_loads_and_declares_metadata(name):
    adapter = load_framework(name)
    assert adapter.name == name
    assert isinstance(adapter.lib_version, str) and adapter.lib_version


@pytest.mark.parametrize("name", sorted(STUBS))
def test_stub_adapters_raise_not_implemented(name):
    adapter = load_framework(name)
    arena = load_arena("tool_use")
    with pytest.raises(NotImplementedError):
        adapter.build(arena, ArenaConfig(mode="mock"))


def _wire_traffic(name, tools):
    """Run one item through an adapter and return what it actually sent."""
    arena = _sentinel_arena(tools)
    arena.dataset = [EvalItem(id="s-01", input="Say the word.", checks=[])]
    with MockServer(MockScript({"default": {"turns": [{"content": "ORNITHOPTER"}]}})) as server:
        config = replace(ArenaConfig(mode="mock"), base_url=server.base_url, api_key="mock-key")
        load_framework(name).build(arena, config).run(arena.dataset[0])
        assert server.requests, f"{name}: adapter sent no request"
        return server.requests[0]


@pytest.mark.parametrize("name", BUILDABLE)
def test_adapter_takes_its_system_prompt_from_the_arena(name):
    """No adapter may hard-code a task instruction.

    A hard-coded prompt means the adapter asks for the wrong thing whenever it is
    run on an arena other than the one its author had in mind — and mock mode
    hides it, because the script replays correct turns regardless of the prompt.
    Asserted against the actual request body, not an adapter attribute.
    """
    sent = json.dumps(_wire_traffic(name, ["search"]).get("messages", []))
    assert SENTINEL in sent, f"{name}: arena prompt never reached the model -> {sent[:400]}"


@pytest.mark.parametrize("name", BUILDABLE)
def test_adapter_advertises_only_the_tools_the_arena_declares(name):
    """Handing an agent an undeclared tool breaks 'same fight for everyone'."""
    body = _wire_traffic(name, ["search"])
    advertised = sorted(t.get("function", {}).get("name", "") for t in body.get("tools", []) or [])
    assert advertised == ["search"], (
        f"{name}: advertised {advertised}, but the arena declares only ['search']"
    )


def test_at_least_one_adapter_was_actually_exercised():
    """Guard against the parametrised contract tests silently collapsing to zero."""
    assert "vanilla" in BUILDABLE, BUILDABLE
