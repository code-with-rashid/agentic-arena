"""Every adapter must load, expose `name` + `lib_version`, and either build or raise
a clean NotImplementedError. This keeps stubs honest and catches import-time typos.
"""

import pytest

from arena.config import ArenaConfig
from arena.registry import available_frameworks, load_arena, load_framework

STUBS = {"claude_agent_sdk", "microsoft_af"}


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
