"""Local synthetic tool server. Never prints non-protocol data on stdout."""

from mcp.server import MCPServer

server = MCPServer("arena-fixture")


def lookup(key: str) -> str:
    """Look up a synthetic fact; 'fail' deliberately raises a service error."""
    if key == "fail":
        raise ValueError("fixture unavailable")
    if key != "answer":
        raise ValueError("unknown fixture key")
    return "395"


server.tool()(lookup)


if __name__ == "__main__":
    server.run(transport="stdio")
