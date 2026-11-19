"""MCP client of the agents: connects to the MCP server `realbasket` (stdio subprocess or Streamable HTTP)."""

from __future__ import annotations

import os
import sys

from mcp.client.stdio import StdioServerParameters, stdio_client
from strands.tools.mcp import MCPClient

from real_basket.core.settings import PROJECT_ROOT, Settings, get_settings
from real_basket.mcp_servers import SERVER_MODULE


def stdio_parameters() -> StdioServerParameters:
    """Start `python -m real_basket.mcp_servers.server` with the interpreter of this process."""
    env = dict(os.environ)
    src = str(PROJECT_ROOT / "src")
    env["PYTHONPATH"] = os.pathsep.join(p for p in (src, env.get("PYTHONPATH", "")) if p)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return StdioServerParameters(command=sys.executable, args=["-m", SERVER_MODULE], env=env, cwd=str(PROJECT_ROOT))


def mcp_client(settings: Settings | None = None) -> MCPClient:
    """MCP client for the server `realbasket`. Passed to a Strands `Agent(tools=[...])`, the agent starts and
    stops the connection itself. MCP_URL set -> Streamable HTTP, otherwise a local stdio subprocess."""
    settings = settings or get_settings()
    url = settings.MCP_URL.strip()
    if url:
        return MCPClient(url=url, startup_timeout=settings.MCP_STARTUP_TIMEOUT)
    params = stdio_parameters()
    return MCPClient(lambda: stdio_client(params), startup_timeout=settings.MCP_STARTUP_TIMEOUT)
