"""Monitoring panel: use-case paths of the interactions and the architecture diagram (no Streamlit, no LLM)."""

import json

from real_basket.mcp_servers import analysis_tools, data_tools, knowledge_tools
from real_basket.ui import monitoring as mon


def _turn(tool: str, payload: dict, status: str = "success") -> list[dict]:
    """Strands messages of one chat turn: tool choice, tool result, final answer."""
    return [
        {"role": "assistant", "content": [{"toolUse": {"toolUseId": "t1", "name": tool, "input": {"level": "x"}}}]},
        {"role": "user", "content": [{"toolResult": {"toolUseId": "t1", "status": status,
                                                     "content": [{"text": json.dumps(payload)}]}}]},
        {"role": "assistant", "content": [{"text": "Die Abweichung beträgt 0,11 PP."}]},
    ]


def _pairs(trace: mon.Trace) -> list[tuple[str, str]]:
    return [(s.source, s.target) for s in trace.steps]


def test_every_mcp_tool_has_a_path_through_the_architecture():
    tools = {fn.__name__ for m in (data_tools, analysis_tools, knowledge_tools) for fn in m.TOOLS}
    assert tools == set(mon.TOOL_PATHS)
    for path in mon.TOOL_PATHS.values():
        assert all(node in mon.NODES for node in path)
    assert all(a in mon.NODES and b in mon.NODES for a, b in mon.ARCH_EDGES)
    assert mon.tool_path("realbasket_get_cpi") == mon.TOOL_PATHS["get_cpi"]


def test_chat_trace_follows_the_tool_calls_of_the_agent():
    trace = mon.chat_trace("Warum?", _turn("investigate_deviation", {"deviation_pp": 0.1061}),
                           answer="Die Abweichung beträgt 0,11 PP.", agent_created=True)
    pairs = _pairs(trace)
    assert pairs[0] == ("user", "ui") and pairs[-1] == ("ui", "user")
    for edge in [("orchestrator", "mcp_client"), ("orchestrator", "llm"), ("mcp_client", "mcp_analysis"),
                 ("mcp_analysis", "core_investigation"), ("core_investigation", "data"), ("ui", "guardrail")]:
        assert edge in pairs
    assert sum(s.action.startswith("LLM-Aufruf") for s in trace.steps) == 2
    assert trace.status == "ok" and trace.kind == "Chat"


def test_chat_trace_flags_tool_errors_unverified_figures_and_agent_errors():
    trace = mon.chat_trace("?", _turn("get_cpi", {"error": "boom"}), answer="9,99 %", unverified=["9,99 %"])
    assert trace.status == "warn"
    assert mon.chat_trace("?", _turn("get_cpi", {}, status="error"), answer="ok").status == "error"
    failed = mon.chat_trace("?", [], error="401 Incorrect API key")
    assert failed.status == "error" and ("ui", "guardrail") not in _pairs(failed)


def test_rag_trace_shows_the_embedding_model_only_when_used():
    assert ("knowledge", "embedding") in _pairs(mon.rag_trace("Kaltmiete", "embedding", 3))
    assert ("knowledge", "embedding") not in _pairs(mon.rag_trace("Kaltmiete", "bm25", 3))
    search = _turn("search_methodology", {"retriever": "embedding", "passages": []})
    assert ("knowledge", "embedding") in _pairs(mon.chat_trace("?", search, answer="ok"))


def test_dot_highlights_the_path_with_numbered_edges():
    overview = mon.to_dot()
    assert overview.startswith("digraph") and overview.rstrip().endswith("}")
    assert all(f'"{n}"' in overview for n in mon.NODES)
    trace = mon.dashboard_trace(False, 10, 10)
    dot = mon.to_dot(trace)
    assert 'label="1"' in dot and "#d9480f" in dot
    assert '"ui" -> "user"' in dot and 'constraint="false"' in dot       # return edge, not in the architecture
    assert len(trace.rows()) == len(trace.steps)
    assert mon.new_chat_trace(True).steps[-1].target == "mcp_client"
