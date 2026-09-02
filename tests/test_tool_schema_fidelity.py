"""Does every framework describe the *same* tool to the model?

`docs/overhead.md` measured what each framework's `tools` block **costs**
(501-701 characters, a 1.4x spread) and read the spread as serialisation. Nothing
had compared what those bytes actually **say**. They were not saying the same
thing.

`arena/tools/__init__.py` declares the canonical spec — `search(query, k=3)`,
with a description on the tool and on both parameters — and `vanilla` sends
exactly that. Every framework adapter re-declares the tool in its own idiom, and
in doing so three of them dropped things:

    what the arena declared        what was reaching the model
    ---------------------------------------------------------------------
    search(query, k=3)             google_adk, smolagents: search(query)
                                     - the `k` parameter simply absent
    query: "What to look up."      langgraph, pydantic_ai, openai_agents,
    k: "How many snippets."          microsoft_af: bare types, no description
    "...Returns up to k snippets"  all six: a shortened tool description

Mock mode cannot see any of this. The mock replays scripted tool calls whatever
the schema said, so every arena stayed green while two frameworks were being
offered a strictly narrower tool and four a less-described one. It is the same
class of unfairness as an unwired iteration budget, and it would have shown up
live as a quality difference attributed to the framework.

It also partly undercuts a published number: `langgraph` measured **leanest** on
the wire at 0.91x, and part of that leanness was missing parameter descriptions
rather than tighter serialisation.

What is gated here is that every adapter offers the tool the arena declared:
the same parameters, the same types, and a description on each. What is **not**
gated is how a framework decorates that — `title`, `additionalProperties`,
`strict`, and OpenAI's strict-mode widening of `required` are framework
properties, reported in docs/tool-schemas.md and not failures.
"""

import contextlib
import tempfile
from dataclasses import replace

import pytest

from arena import tools as arena_tools
from arena.config import ArenaConfig
from arena.llm.mockserver import MockScript, MockServer
from arena.registry import available_frameworks, load_arena, load_framework
from arena.types import EvalItem

STUBS = {"claude_agent_sdk"}
SCRIPT = MockScript({"default": {"turns": [{"content": "330 metres."}]}})

# Every arena, not only `tool_use`. The first audit covered `search` and
# `calculator`; extending it to the pause arenas found a worse divergence, since
# `request_approval`'s canonical description is what *tells the model to stop*.
ARENAS = ("tool_use", "human_in_the_loop", "durable_state")
ITEMS = {
    "tool_use": "How tall is the Eiffel Tower?",
    "human_in_the_loop": "Book a room for 6 people on tuesday.",
    "durable_state": "How tall is the Eiffel Tower?",
}


def _canonical(arena):
    return {
        spec["function"]["name"]: spec["function"] for spec in arena_tools.specs_for(arena.tools)
    }


def _buildable(arena):
    out = []
    for name in available_frameworks():
        if name in STUBS:
            continue
        try:
            config = replace(ArenaConfig(mode="mock"), base_url="http://127.0.0.1:1", api_key="k")
            load_framework(name).build(arena, config)
        except Exception:  # noqa: BLE001 - not installed, or does not run this arena
            continue
        out.append(name)
    return out


ARENA = load_arena("tool_use")
CANONICAL = _canonical(ARENA)
BUILDABLE = _buildable(ARENA)

# (arena id, framework) for every pairing that can actually be built here.
CASES = [(a, f) for a in ARENAS for f in _buildable(load_arena(a))]
_CACHE: dict[tuple[str, str], dict] = {}


def _normalise(text):
    """Collapse whitespace. A framework may reflow a description; it may not cut it.

    ADK appends its own `Args:` block, LangChain leaves the docstring alone, and a
    long description has to wrap somewhere in the source. None of that changes
    what the model is told, so none of it should fail a test — while dropping a
    sentence does.
    """
    return " ".join(str(text or "").split())


def _wire_schemas(arena_id, name):
    """The `tools` block this adapter actually puts on the wire, keyed by name."""
    key = (arena_id, name)
    if key in _CACHE:
        return _CACHE[key]
    arena = load_arena(arena_id)
    with MockServer(SCRIPT, arena_tools=list(arena.tools)) as server:
        config = replace(
            ArenaConfig(mode="mock"),
            base_url=server.base_url,
            api_key="mock-key",
            max_tool_iterations=3,
            checkpoint_dir=tempfile.mkdtemp(prefix="arena-schema-"),
        )
        item = EvalItem(id="s-01", input=ITEMS[arena_id], checks=[])
        with contextlib.suppress(Exception):  # a pause is a normal outcome here
            load_framework(name).build(arena, config).run(item)
        out = {}
        for spec in (server.requests[0].get("tools") if server.requests else []) or []:
            fn = spec.get("function", spec)
            if fn.get("name"):
                out[fn["name"]] = fn
    _CACHE[key] = out
    return out


def _declared(name, arena_id="tool_use"):
    """Only the arena's own tools. Control tools are exempt (methodology §3)."""
    canonical = _canonical(load_arena(arena_id))
    return {n: s for n, s in _wire_schemas(arena_id, name).items() if n in canonical}


@pytest.mark.parametrize(("arena_id", "name"), CASES, ids=lambda v: str(v))
def test_the_arenas_own_description_reaches_the_model_intact(arena_id, name):
    """Every framework had shortened `request_approval`, and it is the one that matters.

    The arena describes it as *"Ask a human to approve a consequential action
    before you take it. **Call this and stop; you will be told the decision.**"*
    All six frameworks sent *"Ask a human to approve a consequential action
    before taking it."* — dropping the sentence that tells the model to pause,
    on the arena built to measure whether it pauses. Only `vanilla`, which sends
    the canonical spec directly, kept it.

    Mock mode cannot see this either: the script decides when the pause happens,
    so `human_in_the_loop` was 12/12 for six adapters while five of them were
    being told materially less than the sixth.

    Containment after whitespace-normalising, not equality: ADK appends its own
    `Args:` block and a long description has to wrap somewhere in the source.
    Reflowing is fine; cutting a sentence is not.
    """
    canonical = _canonical(load_arena(arena_id))
    for tool_name, wire in _declared(name, arena_id).items():
        wanted = _normalise(canonical[tool_name]["description"])
        got = _normalise(wire.get("description"))
        assert wanted in got, (
            f"{name} on {arena_id}: `{tool_name}`'s description was cut.\n"
            f"  arena: {wanted}\n"
            f"  wire : {got}"
        )


@pytest.mark.parametrize("name", BUILDABLE)
def test_every_parameter_the_arena_declared_reaches_the_model(name):
    """A framework offered a narrower tool is being handed a different task.

    `google_adk` and `smolagents` both declared `search(query)` where the arena
    declares `search(query, k=3)`, so the model could not ask for a different
    number of snippets. Mock mode could not see it: scripted calls are replayed
    whatever the schema said.
    """
    for tool_name, wire in _declared(name).items():
        wanted = set(CANONICAL[tool_name]["parameters"]["properties"])
        got = set((wire.get("parameters") or {}).get("properties") or {})
        assert wanted <= got, (
            f"{name}'s `{tool_name}` is missing parameter(s) {sorted(wanted - got)} — "
            f"the arena declared {sorted(wanted)}, the model was offered {sorted(got)}"
        )


@pytest.mark.parametrize("name", BUILDABLE)
def test_every_parameter_keeps_the_type_the_arena_gave_it(name):
    """A widened or narrowed type is a different tool, however similar it reads."""
    for tool_name, wire in _declared(name).items():
        canonical = CANONICAL[tool_name]["parameters"]["properties"]
        got = (wire.get("parameters") or {}).get("properties") or {}
        for param, spec in canonical.items():
            if param not in got:
                continue  # covered by the test above
            assert got[param].get("type") == spec["type"], (
                f"{name}'s `{tool_name}.{param}` is {got[param].get('type')!r}, "
                f"the arena declared {spec['type']!r}"
            )


@pytest.mark.parametrize("name", BUILDABLE)
def test_every_parameter_the_arena_described_is_described_on_the_wire(name):
    """The description is the tool, as far as the model is concerned.

    Four frameworks sent bare types where the arena had described every argument,
    because none of them reads a parameter description from the docstring —
    LangChain wants `Annotated`, the pydantic-family ones want `Field`, and ADK
    and smolagents want a Google-style `Args:` block.

    Text, not wording: what is asserted is that *something* describes each
    parameter, since a framework may legitimately reformat it. `google_adk` folds
    the `Args:` block into the tool description rather than emitting
    per-parameter `description` keys, which is why the tool description counts as
    a place the text can live.
    """
    for tool_name, wire in _declared(name).items():
        canonical = CANONICAL[tool_name]["parameters"]["properties"]
        params = (wire.get("parameters") or {}).get("properties") or {}
        blurb = str(wire.get("description") or "")
        for param, spec in canonical.items():
            if param not in params:
                continue
            described = params[param].get("description") or (param in blurb and blurb)
            assert described, (
                f"{name}'s `{tool_name}.{param}` reaches the model as a bare type. "
                f"The arena describes it as {spec['description']!r}, and a model "
                f"choosing arguments cannot see what this adapter dropped"
            )


@pytest.mark.parametrize("name", BUILDABLE)
def test_the_tool_itself_is_described(name):
    """No adapter may ship a tool with no description at all."""
    for tool_name, wire in _declared(name).items():
        assert str(wire.get("description") or "").strip(), (
            f"{name}'s `{tool_name}` has no description"
        )


def test_the_baseline_still_sends_the_canonical_spec_unmodified():
    """Pinned, because `vanilla` is what "the arena declared" means in practice.

    It is the only adapter that uses `arena.tools.specs_for` directly instead of
    re-declaring the tools in a framework idiom. If it drifted, every comparison
    above would be against a moved reference.
    """
    if "vanilla" not in BUILDABLE:
        pytest.skip("baseline not buildable here")
    wire = _declared("vanilla")
    assert set(wire) == set(CANONICAL), sorted(wire)
    for tool_name, spec in CANONICAL.items():
        assert wire[tool_name]["parameters"] == spec["parameters"], tool_name
        assert wire[tool_name]["description"] == spec["description"], tool_name
