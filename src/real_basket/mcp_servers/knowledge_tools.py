"""Area `knowledge` of the MCP server `realbasket`: method notes and caveats of the reference PDFs (RAG).

Tools:     search_methodology · list_documents
Resources: doc://{file}/seite/{page}   (text of one page of a reference PDF)
Prompts:   hinweis_zitieren            (template: answer a method question with citations)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

INSTRUCTIONS = ("knowledge: method notes and caveats of the reference documents (German PDF reports). Passages "
                "are context only: never take figures from them. Cite as [Datei S. N].")


def search_methodology(query: str, year: int = 0) -> dict:
    """Search method notes and caveats in the reference documents (German PDF reports on the ECLI model
    calculation). Returns passages with file, page and section. Use for methodological questions, e.g. what
    'Wohnen / Energie' contains, modelled vs. measured data, which federal states have verified rent series.
    Never take figures from the passages.

    Args:
        query: search terms; German keywords work best (e.g. 'Nettokaltmiete Wohnen Energie')
        year: only documents of this year (0 = all)
    """
    from real_basket.knowledge import KnowledgeBase

    try:
        res = KnowledgeBase().search(query, year=year or None)
    except Exception as exc:  # noqa: BLE001 - the chat must keep working without documents
        return {"error": f"Method-note search failed: {exc}"}
    return {"query": query, "retriever": res["retriever"], "note": res["note"],
            "passages": [{"cite": f"{p['source']} p. {p['page']}",
                          **{k: p[k] for k in ("section", "text", "also_in")}} for p in res["passages"]]}


def list_documents() -> dict:
    """List the indexed reference documents (file, pages, year) and the active retriever."""
    from real_basket.knowledge import KnowledgeBase

    try:
        status = KnowledgeBase().status()
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Knowledge base not available: {exc}"}
    return {k: status[k] for k in ("documents", "chunks", "notes", "tables", "retriever")}


def page_text(file: str, page: int) -> str:
    """Text of page `page` (1-based) of the reference PDF `file` (only files inside KNOWLEDGE_DIR)."""
    from real_basket.knowledge import KnowledgeBase
    from real_basket.knowledge.ingest import extract_pages

    doc_dir = KnowledgeBase().doc_dir.resolve()
    path = (doc_dir / file).resolve()
    if path.parent != doc_dir or path.suffix.lower() != ".pdf" or not path.is_file():
        raise ValueError(f"Unknown reference document: {file}")
    pages = extract_pages(path)
    if not 1 <= page <= len(pages):
        raise ValueError(f"{file} has {len(pages)} pages, requested page {page}")
    return "\n".join(pages[page - 1])


def doc_page(file: str, page: str) -> str:
    return page_text(file, int(page))


def hinweis_zitieren(frage: str) -> str:
    return (f"Beantworte die Methodenfrage auf Deutsch: „{frage}“.\n"
            "1. Rufe `search_methodology` mit deutschen Stichworten auf.\n"
            "2. Antworte knapp und zitiere jede Aussage als [Datei S. N].\n"
            "3. Übernimm keine Zahlen aus den Textstellen – Zahlen kommen nur aus den Rechen-Tools.\n"
            "4. Wenn keine passende Textstelle gefunden wird, sage das offen.")


TOOLS = (search_methodology, list_documents)


def register(server: MCPServer) -> None:
    for fn in TOOLS:
        server.tool()(fn)
    server.resource("doc://{file}/seite/{page}", name="reference-page", mime_type="text/plain",
                    description="Text of one page of a reference PDF, e.g. doc://Bericht_2026.pdf/seite/3")(doc_page)
    server.prompt(name="hinweis_zitieren",
                  description="Methodenfrage mit Zitat aus den Referenzberichten beantworten")(hinweis_zitieren)
