"""Run one real stdio MCP session against the same direct fixture function."""

import asyncio
import json
import sys
from importlib.metadata import version

from mcp import Client, StdioServerParameters

from examples.mcp.server import lookup


async def exercise() -> dict:
    params = StdioServerParameters(command=sys.executable, args=["-m", "examples.mcp.server"])
    async with asyncio.timeout(20), Client(params) as client:
        tools = await client.list_tools()
        tool = next(t for t in tools.tools if t.name == "lookup")
        success = await client.call_tool("lookup", {"key": "answer"})
        invalid = await client.call_tool("lookup", {})
        failed = await client.call_tool("lookup", {"key": "fail"})
        text = "".join(getattr(block, "text", "") for block in success.content)
        if success.is_error or text != lookup("answer"):
            raise AssertionError("remote successful result differs from direct fixture")
        if not invalid.is_error or not failed.is_error:
            raise AssertionError("invalid input or service failure was hidden")
        return {
            "sdk": version("mcp"),
            "protocol": client.protocol_version,
            "transport": "stdio",
            "schema": tool.input_schema,
            "direct": lookup("answer"),
            "remote": text,
            "invalid_input_error": invalid.is_error,
            "service_error": failed.is_error,
            "authorization": "not assessed",
            "cancellation": "not assessed",
        }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(exercise()), indent=2))
