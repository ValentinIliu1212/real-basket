"""Agent factory: orchestrator agent that uses a collector sub-agent ("agents as tools" pattern)."""

from __future__ import annotations

from strands import Agent, tool
from strands.models.openai import OpenAIModel

from real_basket.agents.prompts import COLLECTOR_PROMPT, ORCHESTRATOR_PROMPT
from real_basket.agents.tools import (
    calculate_essential_vs_cpi,
    fetch_official_cpi,
    fetch_prices,
    fetch_regional_rents,
)
from real_basket.core.settings import get_settings


def create_model() -> OpenAIModel:
    settings = get_settings()
    return OpenAIModel(
        client_args={"api_key": settings.OPENAI_API_KEY},
        model_id=settings.OPENAI_MODEL_ID,
        params={"temperature": 0.2},
    )


@tool
def collect_category_prices(category: str) -> str:
    """Delegate price collection for one category ('food', 'rent', 'energy', 'mobility')
    to the specialised Price Collector agent and return its summary."""
    collector = Agent(
        name="REALBASKET-COLLECTOR",
        system_prompt=COLLECTOR_PROMPT,
        model=create_model(),
        tools=[fetch_prices],
        callback_handler=None,
    )
    return str(collector(f"Collect and summarise prices for category '{category}'."))


def create_orchestrator() -> Agent:
    settings = get_settings()
    return Agent(
        name=settings.AGENT_NAME,
        system_prompt=ORCHESTRATOR_PROMPT,
        model=create_model(),
        tools=[collect_category_prices, fetch_official_cpi, calculate_essential_vs_cpi, fetch_regional_rents],
        callback_handler=None,
    )
