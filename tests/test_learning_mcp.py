import asyncio
from importlib.metadata import version

import pytest

pytest.importorskip("mcp", reason="optional lesson: install examples/mcp/requirements.txt")
if version("mcp") != "2.2.0":
    pytest.skip("lesson verified against mcp==2.2.0", allow_module_level=True)

from examples.mcp.recipe import exercise  # noqa: E402


def test_real_stdio_preserves_success_and_failure():
    report = asyncio.run(exercise())
    assert report["direct"] == report["remote"] == "395"
    assert report["invalid_input_error"] and report["service_error"]
    assert "key" in report["schema"]["required"]
