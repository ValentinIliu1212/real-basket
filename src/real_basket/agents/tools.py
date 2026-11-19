"""Plain-Python access to the RealBasket tools (scripts, tests, compatibility).

The agents do NOT use this module: they reach all tools via the MCP server `realbasket`
(`real_basket.mcp_servers.server`). The functions below are the same plain functions the server registers,
re-exported here under their current and former names.

All figures are real data parsed deterministically from the reference PDFs (reports/real-data). There is no
synthetic data: if the PDFs are unavailable, every tool returns an `error` instead of numbers.
"""

from __future__ import annotations

from real_basket.mcp_servers.analysis_tools import get_regional_rents, investigate_deviation
from real_basket.mcp_servers.data_tools import calculate_index, data_checks, get_basket, get_cpi, get_prices
from real_basket.mcp_servers.knowledge_tools import list_documents, search_methodology

# former in-process tool names
fetch_prices = get_prices
fetch_official_cpi = get_cpi
calculate_essential_vs_cpi = calculate_index
fetch_regional_rents = get_regional_rents

__all__ = ["calculate_essential_vs_cpi", "calculate_index", "data_checks", "fetch_official_cpi", "fetch_prices",
           "fetch_regional_rents", "get_basket", "get_cpi", "get_prices", "get_regional_rents",
           "investigate_deviation", "list_documents", "search_methodology"]
