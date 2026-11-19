"""Agent factory: orchestrator agent with MCP tools and a collector sub-agent ("agents as tools" pattern).

Target architecture phase 1: all tools (data, VPI, index calculation, deviation analysis, regional rents, method
notes) come from ONE MCP server `realbasket` (stdio subprocess by default, Streamable HTTP if MCP_URL is set).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import openai
from strands import Agent, tool
from strands.models.openai import OpenAIModel
from strands.tools.mcp import MCPClient

from real_basket.agents.mcp_clients import mcp_client
from real_basket.agents.prompts import COLLECTOR_PROMPT, ORCHESTRATOR_PROMPT
from real_basket.core import llm
from real_basket.core.settings import get_settings


class AzureOpenAIModel(OpenAIModel):
    """Strands OpenAI provider talking to Azure OpenAI (model_id = deployment name).

    Like the base class, a fresh async client is created per request (httpx connections must not be
    shared across asyncio event loops)."""

    @asynccontextmanager
    async def _get_client(self) -> AsyncIterator[Any]:
        async with openai.AsyncAzureOpenAI(**self.client_args) as client:
            yield client


def create_model(temperature: float = 0.2) -> OpenAIModel:
    settings = get_settings()
    cls = AzureOpenAIModel if llm.use_azure(settings) else OpenAIModel
    return cls(
        client_args=llm.client_kwargs(settings),
        model_id=llm.completion_model_id(settings),
        params={"temperature": temperature},
    )


COLLECTOR_TOOLS = ("get_prices",)


def make_collector_tool(server: MCPClient):
    """Collector sub-agent as a tool; it only gets `get_prices` of the (already running) MCP client."""

    @tool
    def collect_category_prices(category: str) -> str:
        """Delegate price collection for one expenditure group of the reference basket ('food',
        'housing_energy', 'mobility', 'health', 'communication') to the specialised Price Collector agent and
        return its summary."""
        tools = [t for t in server.list_tools_sync() if t.tool_name in COLLECTOR_TOOLS]
        collector = Agent(
            name="REALBASKET-COLLECTOR",
            system_prompt=COLLECTOR_PROMPT,
            model=create_model(),
            tools=tools,
            callback_handler=None,
        )
        return str(collector(f"Collect and summarise prices for category '{category}'."))

    return collect_category_prices


def create_orchestrator() -> Agent:
    """Chat agent. The MCP client is managed by the agent: the server starts with the agent and stops when it
    is cleaned up (`agent.cleanup()` or garbage collection)."""
    settings = get_settings()
    server = mcp_client(settings)
    return Agent(
        name=settings.AGENT_NAME,
        system_prompt=ORCHESTRATOR_PROMPT,
        model=create_model(),
        tools=[server, make_collector_tool(server)],
        callback_handler=None,
    )
