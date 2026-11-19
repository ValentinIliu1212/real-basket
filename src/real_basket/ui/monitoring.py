"""Monitoring: use-case paths of every interaction through the RealBasket architecture (no Streamlit import).

Every interaction of the dashboard (page load / weight change, method-note search, PDF reports, chat question,
new chat) is recorded as a `Trace`: an ordered list of `Step`s between the components of the architecture diagram
of the README. `to_dot()` draws that architecture as Graphviz DOT and highlights the path of one trace with
numbered edges; the dashboard renders it with `st.graphviz_chart` (rendered in the browser, no Graphviz install).

Chat traces are derived from the Strands messages of the turn (every assistant message = one LLM call,
`toolUse` / `toolResult` blocks = MCP tool calls), so they show what the agent really did, not a fixed script.
"""

from __future__ import annotations

import itertools
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from real_basket.agents.guardrail import answer_figures


@dataclass(frozen=True)
class Node:
    id: str
    label: str
    group: str


GROUPS = {
    "ui": ("Oberfläche", "#e7f5ff"),
    "agent": ("Agent (agents/)", "#fff4e6"),
    "mcp": ("MCP-Server „realbasket“ (mcp_servers/)", "#ebfbee"),
    "core": ("Deterministischer Kern – kein LLM", "#f3f0ff"),
    "llm": ("LLM-Provider (OpenAI / Azure OpenAI)", "#fff0f6"),
    "files": ("Dateien", "#f8f9fa"),
}

NODES: dict[str, Node] = {n.id: n for n in [
    Node("user", "👤 Nutzer", ""),
    Node("ui", "Streamlit-UI / CLI\nui/app.py · cli.py", "ui"),
    Node("orchestrator", "Orchestrator-Agent\nREALBASKET-ORCHESTRATOR", "agent"),
    Node("mcp_client", "MCPClient\nstdio / Streamable HTTP", "agent"),
    Node("guardrail", "Zahlen-Guardrail\nagents/guardrail.py", "agent"),
    Node("mcp_data", "data\nget_basket · get_prices · get_cpi\ncalculate_index · data_checks", "mcp"),
    Node("mcp_analysis", "analysis\ninvestigate_deviation\nget_regional_rents", "mcp"),
    Node("mcp_knowledge", "knowledge\nsearch_methodology\nlist_documents", "mcp"),
    Node("core_index", "core/index.py\nIndex + VPI-Vergleich", "core"),
    Node("core_investigation", "core/investigation.py\nEinflussfaktoren · Mieten", "core"),
    Node("data", "data/\nreal_data.py · basket.py", "core"),
    Node("knowledge", "knowledge/\nRAG: BM25 / Embeddings", "core"),
    Node("reports", "reports/pdf_report.py", "core"),
    Node("llm", "Chat-Modell", "llm"),
    Node("embedding", "Embedding-Modell", "llm"),
    Node("pdfs", "Referenz-PDFs\nreports/real-data", "files"),
    Node("index_file", "RAG-Index\ndata_store/knowledge", "files"),
]}

# static architecture (same as the README diagram)
ARCH_EDGES: list[tuple[str, str]] = [
    ("user", "ui"), ("ui", "orchestrator"), ("ui", "guardrail"), ("orchestrator", "llm"),
    ("orchestrator", "mcp_client"), ("mcp_client", "mcp_data"), ("mcp_client", "mcp_analysis"),
    ("mcp_client", "mcp_knowledge"), ("mcp_data", "core_index"), ("mcp_data", "data"),
    ("mcp_analysis", "core_investigation"), ("mcp_knowledge", "knowledge"), ("core_index", "data"),
    ("core_investigation", "data"), ("ui", "core_index"), ("ui", "core_investigation"), ("ui", "data"),
    ("ui", "knowledge"), ("ui", "reports"), ("reports", "core_index"), ("reports", "data"), ("data", "pdfs"),
    ("knowledge", "pdfs"), ("knowledge", "index_file"), ("knowledge", "embedding"),
]

# MCP tool -> path behind the MCP client (area module, then core / data modules)
TOOL_PATHS: dict[str, list[str]] = {
    "get_basket": ["mcp_data", "data"],
    "get_prices": ["mcp_data", "data"],
    "get_cpi": ["mcp_data", "data"],
    "calculate_index": ["mcp_data", "core_index", "data"],
    "data_checks": ["mcp_data", "data"],
    "investigate_deviation": ["mcp_analysis", "core_investigation", "data"],
    "get_regional_rents": ["mcp_analysis", "core_investigation", "data"],
    "search_methodology": ["mcp_knowledge", "knowledge", "index_file"],
    "list_documents": ["mcp_knowledge", "knowledge", "index_file"],
}
HOP_ACTION = {
    "data": "load_basket() – echte Daten (im Serverprozess gecacht)",
    "core_index": "Index berechnen (essential_index, compare_with_cpi)",
    "core_investigation": "Abweichung / Mieten analysieren",
    "knowledge": "KnowledgeBase (Suche / Status)",
    "index_file": "Index lesen (bei geänderten PDFs neu aufbauen)",
}

STATUS_ICON = {"ok": "✅", "warn": "⚠️", "error": "❌"}
_SEVERITY = {"ok": 0, "warn": 1, "error": 2}
_EDGE_COLOR = {"ok": "#d9480f", "warn": "#f08c00", "error": "#e03131"}
_counter = itertools.count(1)


@dataclass
class Step:
    source: str
    target: str
    action: str
    detail: str = ""
    status: str = "ok"


@dataclass
class Trace:
    kind: str
    title: str
    steps: list[Step]
    duration_s: float | None = None
    note: str = ""
    started: datetime = field(default_factory=datetime.now)
    id: int = field(default_factory=lambda: next(_counter))

    @property
    def status(self) -> str:
        return max((s.status for s in self.steps), key=_SEVERITY.__getitem__, default="ok")

    @property
    def label(self) -> str:
        took = f" · {self.duration_s:.2f} s" if self.duration_s is not None else ""
        return f"{STATUS_ICON[self.status]} {self.started:%H:%M:%S} · {self.kind}: {self.title}{took}"

    def rows(self) -> list[dict]:
        """Steps as table rows (German column names)."""
        return [{"#": i, "Von": _first_line(s.source), "Nach": _first_line(s.target), "Aktion": s.action,
                 "Details": s.detail, "Status": STATUS_ICON[s.status]} for i, s in enumerate(self.steps, 1)]


def _first_line(node_id: str) -> str:
    node = NODES.get(node_id)
    return node.label.split("\n")[0] if node else node_id


def _short(text: Any, limit: int = 90) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


# --- Trace builders -------------------------------------------------------------------------------
def dashboard_trace(weights_changed: bool, checks_ok: int, checks: int, duration_s: float | None = None) -> Trace:
    """Header, charts and drivers of the dashboard: direct calls of core/ and data/ (no LLM, no MCP)."""
    return Trace("Dashboard", "Gewichte geändert" if weights_changed else "Dashboard geladen", [
        Step("user", "ui", "Gewichte ändern" if weights_changed else "Dashboard öffnen"),
        Step("ui", "data", "load_basket()", "gecacht (st.cache_resource)"),
        Step("data", "pdfs", "Tabellen deterministisch lesen", f"{checks_ok} von {checks} Prüfungen bestanden",
             "ok" if checks_ok == checks else "warn"),
        Step("ui", "core_index", "essential_index + compare_with_cpi", "Index und VPI-Vergleich"),
        Step("ui", "core_investigation", "deviation_breakdown", "Einflussfaktoren je Kategorie"),
        Step("ui", "user", "Kennzahlen + Diagramme anzeigen"),
    ], duration_s, "Kein LLM und kein MCP: das Dashboard ruft core/ und data/ direkt auf (gleiche Zahlen).")


def rag_trace(query: str, retriever: str, hits: int, duration_s: float | None = None, error: str = "") -> Trace:
    """Method-note search of the RAG tab."""
    steps = [Step("user", "ui", "Suche Methodenhinweise", _short(query)),
             Step("ui", "knowledge", "KnowledgeBase.search()", f"Suchverfahren: {retriever or '?'}",
                  "error" if error else "ok")]
    if not error:
        steps.append(Step("knowledge", "index_file", "Index lesen", "Textstellen + Vektoren"))
        if retriever == "embedding":
            steps.append(Step("knowledge", "embedding", "Suchanfrage einbetten", "mit BM25 fusioniert"))
        elif "embedding failed" in retriever:
            steps.append(Step("knowledge", "embedding", "Suchanfrage einbetten", retriever, "warn"))
    steps.append(Step("ui", "user", "Fehler anzeigen" if error else "Textstellen anzeigen",
                      _short(error) if error else f"{hits} Textstellen mit Datei + Seite",
                      "error" if error else "ok"))
    return Trace("RAG-Suche", _short(query, 60), steps, duration_s, "Nur Kontext – Zahlen kommen nie aus der Textsuche.")


def pdf_trace(files: list[str], duration_s: float | None = None, error: str = "") -> Trace:
    """Generation of the German RealBasket PDF reports."""
    status = "error" if error else "ok"
    return Trace("PDF-Berichte", "Berichte erzeugen", [
        Step("user", "ui", "Berichte erzeugen"),
        Step("ui", "reports", "generate_all()", "gecacht (st.cache_data)", status),
        Step("reports", "data", "Echte Daten", "Monatskosten, VPI, Stadtmieten"),
        Step("reports", "core_index", "essential_index + compare_with_cpi"),
        Step("ui", "user", "Download-Buttons", _short(error) if error else f"{len(files)} PDFs", status),
    ], duration_s)


def new_chat_trace(had_agent: bool) -> Trace:
    steps = [Step("user", "ui", "Neuer Chat", "Verlauf löschen")]
    if had_agent:
        steps += [Step("ui", "orchestrator", "agent.cleanup()"),
                  Step("orchestrator", "mcp_client", "MCP-Verbindung schließen", "Server-Subprozess stoppen")]
    return Trace("Neuer Chat", "Verlauf gelöscht", steps, note="" if had_agent else "Es lief noch kein Agent.")


def _content(msg: Any) -> list:
    return msg.get("content", []) if isinstance(msg, dict) else []


def _result_payload(result: dict | None) -> dict | None:
    """JSON payload of a Strands `toolResult` (first JSON text block), if any."""
    for block in (result or {}).get("content", []) or []:
        if isinstance(block, dict) and isinstance(block.get("json"), dict):
            return block["json"]
        if isinstance(block, dict) and isinstance(block.get("text"), str):
            try:
                data = json.loads(block["text"])
            except ValueError:
                continue
            if isinstance(data, dict):
                return data
    return None


def tool_path(name: str) -> list[str]:
    """Path of an MCP tool behind the client; tolerates prefixed names such as `realbasket_get_cpi`."""
    if name in TOOL_PATHS:
        return TOOL_PATHS[name]
    return next((p for tool, p in TOOL_PATHS.items() if name.endswith(tool)), [])


def _tool_steps(use: dict, result: dict | None) -> list[Step]:
    name = str(use.get("name", "?"))
    args = _short(json.dumps(use.get("input") or {}, ensure_ascii=False), 70)
    payload = _result_payload(result)
    if result is None:
        status, outcome = "warn", "kein Ergebnis"
    elif result.get("status") == "error":
        status, outcome = "error", "Fehler"
    elif payload and "error" in payload:
        status, outcome = "warn", f"Tool meldet: {_short(payload['error'], 60)}"
    else:
        status, outcome = "ok", "Ergebnis (JSON)"
    steps = [Step("orchestrator", "mcp_client", "tools/call", f"{name}({args})")]
    path = tool_path(name)
    if not path:
        steps.append(Step("mcp_client", "mcp_client", name, "unbekanntes Tool (keine Zuordnung)", "warn"))
    else:
        steps.append(Step("mcp_client", path[0], name, args))
        steps += [Step(a, b, HOP_ACTION.get(b, "aufrufen")) for a, b in itertools.pairwise(path)]
        retriever = str((payload or {}).get("retriever", ""))
        if name.endswith("search_methodology") and retriever == "embedding":
            steps.append(Step("knowledge", "embedding", "Suchanfrage einbetten", "mit BM25 fusioniert"))
        elif name.endswith("search_methodology") and "embedding failed" in retriever:
            steps.append(Step("knowledge", "embedding", "Suchanfrage einbetten", retriever, "warn"))
        steps.append(Step(path[0], "mcp_client", "Ergebnis", name, status))
    steps.append(Step("mcp_client", "orchestrator", "Tool-Ergebnis", f"{name}: {outcome}", status))
    return steps


def chat_trace(question: str, messages: list, answer: str = "", unverified: list[str] | None = None,
               duration_s: float | None = None, error: str = "", agent_created: bool = False) -> Trace:
    """Use-case path of one chat turn. `messages` = the Strands messages added by this turn."""
    steps = [Step("user", "ui", "Frage", _short(question))]
    if agent_created:
        steps += [Step("ui", "orchestrator", "create_orchestrator()", "Modell + Systemprompt"),
                  Step("orchestrator", "mcp_client", "MCP-Server starten", "stdio-Subprozess oder MCP_URL")]
    steps.append(Step("ui", "orchestrator", "agent(frage)", "Frage + Gesprächsverlauf"))
    results = {b["toolResult"].get("toolUseId"): b["toolResult"] for m in messages for b in _content(m)
               if isinstance(b, dict) and isinstance(b.get("toolResult"), dict)}
    calls = 0
    for msg in messages:
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        calls += 1
        uses = [b["toolUse"] for b in _content(msg) if isinstance(b, dict) and isinstance(b.get("toolUse"), dict)]
        steps.append(Step("orchestrator", "llm", f"LLM-Aufruf {calls}", "Systemprompt + Verlauf + Tool-Schemas"))
        if uses:
            steps.append(Step("llm", "orchestrator", "Tool-Wahl", ", ".join(str(u.get("name")) for u in uses)))
        else:
            text = "".join(b.get("text", "") for b in _content(msg) if isinstance(b, dict))
            steps.append(Step("llm", "orchestrator", "Antworttext", f"{len(text)} Zeichen"))
        for use in uses:
            steps += _tool_steps(use, results.get(use.get("toolUseId")))
    if error:
        steps.append(Step("orchestrator", "ui", "Fehler", _short(error), "error"))
        steps.append(Step("ui", "user", "Fehlermeldung anzeigen", status="error"))
    else:
        unverified = unverified or []
        steps.append(Step("orchestrator", "ui", "Antwort", f"{len(answer)} Zeichen"))
        steps.append(Step("ui", "guardrail", "unverified_figures()",
                          f"{len(answer_figures(answer))} Zahlen gegen Tool-Ergebnisse prüfen"))
        steps.append(Step("guardrail", "ui", "Prüfergebnis",
                          ("Nicht belegt: " + ", ".join(unverified)) if unverified else "alle Zahlen belegt",
                          "warn" if unverified else "ok"))
        steps.append(Step("ui", "user", "Antwort anzeigen", "inkl. genutzter Tools und Guardrail-Hinweis"))
    tools = sum(1 for s in steps if s.action == "tools/call")
    return Trace("Chat", _short(question, 60), steps, duration_s, f"{calls} LLM-Aufrufe · {tools} Tool-Aufrufe")


# --- Graphviz --------------------------------------------------------------------------------------
def _q(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def to_dot(trace: Trace | None = None) -> str:
    """Architecture diagram as DOT; with a trace, its path is highlighted with numbered edges."""
    active: dict[tuple[str, str], list[int]] = {}
    edge_status: dict[tuple[str, str], str] = {}
    node_status: dict[str, str] = {}
    for i, s in enumerate(trace.steps if trace else [], 1):
        key = (s.source, s.target)
        active.setdefault(key, []).append(i)
        edge_status[key] = max(edge_status.get(key, "ok"), s.status, key=_SEVERITY.__getitem__)
        for n in (s.source, s.target):
            node_status.setdefault(n, "ok")
        if s.status != "ok":
            node_status[s.target] = max(node_status[s.target], s.status, key=_SEVERITY.__getitem__)

    def node_line(node: Node) -> str:
        fill = GROUPS[node.group][1] if node.group else "#ffffff"
        attrs = {"fillcolor": fill, "color": "#495057", "fontcolor": "#212529", "penwidth": "1"}
        if trace and node.id in node_status:
            st = node_status[node.id]
            attrs.update(fillcolor={"ok": "#ffe8cc", "warn": "#fff3bf", "error": "#ffe3e3"}[st],
                         color=_EDGE_COLOR[st], penwidth="2.4")
        elif trace:
            attrs.update(fillcolor="#f8f9fa", color="#dee2e6", fontcolor="#adb5bd")
        shape = ', shape="ellipse"' if node.id == "user" else ""
        return (f"  {_q(node.id)} [label={_q(node.label)}{shape}, "
                + ", ".join(f'{k}="{v}"' for k, v in attrs.items()) + "];")

    lines = ["digraph realbasket {",
             ('  graph [rankdir="LR", fontname="Helvetica", fontsize="11", nodesep="0.3", ranksep="0.55", '
              'bgcolor="transparent", compound="true"];'),
             '  node [shape="box", style="rounded,filled", fontname="Helvetica", fontsize="10"];',
             '  edge [fontname="Helvetica", fontsize="9", arrowsize="0.7"];']
    for node in NODES.values():
        if not node.group:
            lines.append(node_line(node))
    for group, (label, _) in GROUPS.items():
        lines.append(f"  subgraph cluster_{group} {{")
        lines.append(f'    label={_q(label)}; style="rounded,dashed"; color="#adb5bd"; fontcolor="#495057";')
        lines += ["  " + node_line(n) for n in NODES.values() if n.group == group]
        lines.append("  }")
    arch = set(ARCH_EDGES)
    for a, b in ARCH_EDGES:
        if (a, b) in active:
            continue
        style = 'color="#dee2e6", style="dashed"' if trace else 'color="#868e96"'
        lines.append(f"  {_q(a)} -> {_q(b)} [{style}];")
    for (a, b), nums in active.items():
        color = _EDGE_COLOR[edge_status[(a, b)]]
        extra = "" if (a, b) in arch else ', style="dashed", constraint="false"'
        label = ", ".join(map(str, nums))
        lines.append(f'  {_q(a)} -> {_q(b)} [color="{color}", fontcolor="{color}", penwidth="2.2", '
                     f"label={_q(label)}{extra}];")
    lines.append("}")
    return "\n".join(lines)
