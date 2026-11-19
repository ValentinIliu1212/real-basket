"""Contract tests of the MCP server `realbasket` (one server, areas data / knowledge / analysis)."""

import asyncio
import json
from pathlib import Path

import pytest

from real_basket.core.settings import get_settings
from real_basket.mcp_servers.server import create_server, main
from real_basket.mcp_servers.server import mcp as server

REAL_DOCS = Path(__file__).resolve().parents[1] / "reports" / "real-data"
needs_docs = pytest.mark.skipif(not REAL_DOCS.is_dir(), reason="reference PDFs not available")

DATA_TOOLS = {"get_basket", "get_prices", "get_cpi", "calculate_index", "data_checks"}
KNOWLEDGE_TOOLS = {"search_methodology", "list_documents"}
ANALYSIS_TOOLS = {"investigate_deviation", "get_regional_rents"}


def run(coro):
    return asyncio.run(coro)


def tool_schemas(srv) -> dict:
    return {t.name: t.input_schema for t in run(srv.list_tools())}


def call(name: str, args: dict | None = None, srv=server) -> dict:
    result = run(srv.call_tool(name, args or {}))
    assert not result.is_error, result
    return json.loads(result.content[0].text)


@pytest.fixture
def no_docs(tmp_path, monkeypatch):
    monkeypatch.setenv("KNOWLEDGE_DIR", str(tmp_path / "none"))
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "store"))
    monkeypatch.setenv("KNOWLEDGE_RETRIEVER", "bm25")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# --- tool contracts ---------------------------------------------------------------------------------
def test_one_server_with_all_areas():
    assert server.name == "realbasket"
    assert set(tool_schemas(server)) == DATA_TOOLS | KNOWLEDGE_TOOLS | ANALYSIS_TOOLS
    for area in ("data:", "knowledge:", "analysis:"):
        assert area in server.instructions


def test_data_tool_contract():
    schemas = tool_schemas(server)
    assert schemas["get_prices"]["required"] == ["category"]
    assert set(schemas["get_prices"]["properties"]) == {"category", "months"}
    assert set(schemas["calculate_index"]["properties"]) == {"weights", "months"}
    assert not schemas["calculate_index"].get("required")


def test_analysis_tool_contract():
    schemas = tool_schemas(server)
    assert set(schemas["investigate_deviation"]["properties"]) == {"level", "category", "region_type", "months"}
    assert set(schemas["get_regional_rents"]["properties"]) == {"region_type"}
    assert not schemas["investigate_deviation"].get("required")


def test_knowledge_contract():
    schemas = tool_schemas(server)
    assert schemas["search_methodology"]["required"] == ["query"]
    assert [t.uri_template for t in run(server.list_resource_templates())] == ["doc://{file}/seite/{page}"]
    assert [p.name for p in run(server.list_prompts())] == ["hinweis_zitieren"]


def test_data_resources_listed():
    assert {str(r.uri) for r in run(server.list_resources())} == {"basket://weights", "basket://checks"}


def test_area_subset_for_a_later_split():
    sub = create_server(["data", "analysis"])
    assert set(tool_schemas(sub)) == DATA_TOOLS | ANALYSIS_TOOLS
    assert "knowledge:" not in sub.instructions
    with pytest.raises(ValueError):
        create_server(["report"])
    with pytest.raises(SystemExit):
        main(["--transport", "ftp"])


# --- no fallback: errors instead of numbers ---------------------------------------------------------
def test_tools_return_error_without_pdfs(no_docs):
    for name, args in [("get_basket", {}), ("get_prices", {"category": "food"}), ("get_cpi", {}),
                       ("calculate_index", {}), ("data_checks", {}), ("investigate_deviation", {}),
                       ("get_regional_rents", {})]:
        res = call(name, args)
        assert "error" in res and "Echte Daten nicht verfügbar" in res["error"], name


def test_knowledge_search_without_pdfs_returns_no_passages(no_docs):
    res = call("search_methodology", {"query": "Miete"})
    assert res["passages"] == []


# --- real data --------------------------------------------------------------------------------------
@needs_docs
def test_calculate_index_via_mcp_matches_reference():
    res = call("calculate_index")
    assert res["period"] == "2026-10-01"
    assert res["essential_yoy_pct"] == pytest.approx(2.93, abs=0.01)
    assert res["cpi_yoy_pct"] == pytest.approx(2.83, abs=0.01)
    assert res["documents"] and res["checks_passed"].split("/")[0] == res["checks_passed"].split("/")[1]


@needs_docs
def test_get_prices_rejects_unknown_category_and_cites_sources():
    assert "error" in call("get_prices", {"category": "luxury"})
    res = call("get_prices", {"category": "food", "months": 3})
    assert res["prices"] and all(p["source"] for p in res["prices"])


@needs_docs
def test_analysis_tools_via_mcp():
    res = call("investigate_deviation", {"level": "category"})
    assert sum(c["gap_pp"] for c in res["categories"]) == pytest.approx(res["deviation_pp"], abs=0.05)
    rents = call("get_regional_rents", {"region_type": "all"})
    assert len(rents["cities"]) == 15 and len(rents["states"]) == 16
    assert "error" in call("get_regional_rents", {"region_type": "kreis"})


@needs_docs
def test_data_checks_and_weights_resource():
    res = call("data_checks")
    assert res["all_ok"] and len(res["checks"]) == 11
    contents = list(run(server.read_resource("basket://weights")))
    assert sum(json.loads(contents[0].content).values()) == pytest.approx(1.0)


@needs_docs
def test_document_page_resource():
    first = sorted(REAL_DOCS.glob("*.pdf"))[0].name
    contents = list(run(server.read_resource(f"doc://{first}/seite/1")))
    assert contents[0].content.strip()


# --- end to end over stdio (subprocess), as used by the chat agent ----------------------------------
@needs_docs
def test_stdio_transport_with_strands_client():
    from real_basket.agents.mcp_clients import mcp_client

    with mcp_client() as client:
        names = {t.tool_name for t in client.list_tools_sync()}
        assert names == DATA_TOOLS | KNOWLEDGE_TOOLS | ANALYSIS_TOOLS
        result = client.call_tool_sync("t1", "calculate_index", {})
        assert result["status"] == "success"
        assert "deviation_pp" in json.dumps(result["content"])
