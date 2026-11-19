"""Agent factory: the chat agent REALBASKET-ORCHESTRATOR with the tools of the MCP server `realbasket`.

Target architecture phase 1: all tools (data, VPI, index calculation, deviation analysis, regional rents, method
notes) come from ONE MCP server `realbasket` (stdio subprocess by default, Streamable HTTP if MCP_URL is set).

Decision (review 11/2026): the former collector sub-agent (`collect_category_prices`, "agents as tools") was
removed. It added a second LLM call per category and let an LLM compute "change in percent", although the
deterministic `get_prices` tool returns those numbers itself (`summary`). A price-collector agent is planned
again only with live sources (phase 2, A2A), where it has real work to do.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import openai
from strands import Agent
from strands.models.openai import OpenAIModel

from real_basket.agents.mcp_clients import mcp_client
from real_basket.agents.prompts import ORCHESTRATOR_PROMPT
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


def create_orchestrator() -> Agent:
    """Chat agent. The MCP client is managed by the agent: the server starts with the agent and stops when it
    is cleaned up (`agent.cleanup()` or garbage collection). Raises `llm.LLMConfigError` if the provider
    settings are incomplete (fail fast instead of a 401 in the middle of a chat)."""
    settings = get_settings()
    llm.require_configured(settings)
    return Agent(
        name=settings.AGENT_NAME,
        system_prompt=ORCHESTRATOR_PROMPT,
        model=create_model(),
        tools=[mcp_client(settings)],
        callback_handler=None,
    )
