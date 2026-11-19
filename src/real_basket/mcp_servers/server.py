"""MCP server `realbasket`: ONE server process with the tool areas data, knowledge and analysis.

The areas live in separate modules (`data_tools.py`, `knowledge_tools.py`, `analysis_tools.py`), so a later split
into several servers only needs `--areas` (or one entry point per area) - the tool names stay the same.

Start:
    poetry run real-basket-mcp                                            # stdio, all areas
    poetry run real-basket-mcp --transport streamable-http --port 8001    # http://127.0.0.1:8001/mcp
    poetry run real-basket-mcp --areas data,analysis                      # subset (e.g. without the LLM key)
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable

from mcp.server.mcpserver import MCPServer

from real_basket.mcp_servers import analysis_tools, data_tools, knowledge_tools

AREAS = {"data": data_tools, "knowledge": knowledge_tools, "analysis": analysis_tools}

SERVER_INSTRUCTIONS = ("RealBasket: essential living cost index vs. the official German CPI (VPI). All numbers come "
                       "from the deterministic tools (real data parsed from the reference PDFs); never calculate "
                       "rates yourself. Areas:")


def create_server(areas: Iterable[str] = tuple(AREAS)) -> MCPServer:
    """Build the `realbasket` MCP server with the tools, resources and prompts of the given areas."""
    areas = list(dict.fromkeys(areas))
    unknown = sorted(set(areas) - set(AREAS))
    if unknown or not areas:
        raise ValueError(f"unknown or no MCP areas {unknown}, expected some of {sorted(AREAS)}")
    instructions = "\n".join([SERVER_INSTRUCTIONS, *(f"- {AREAS[a].INSTRUCTIONS}" for a in areas)])
    server = MCPServer("realbasket", instructions=instructions)
    for area in areas:
        AREAS[area].register(server)
    return server


mcp = create_server()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="MCP server realbasket")
    parser.add_argument("--transport", choices=("stdio", "streamable-http"), default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--areas", default=",".join(AREAS), help=f"comma separated subset of {','.join(AREAS)}")
    args = parser.parse_args(argv)
    server = create_server(a.strip() for a in args.areas.split(",") if a.strip())
    if args.transport == "stdio":
        server.run("stdio")
    else:
        server.run("streamable-http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
