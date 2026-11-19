"""Tests of the method-notes retrieval (RAG) and its guardrails in the monitoring flow."""

import re
from datetime import date
from pathlib import Path

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from real_basket.core.settings import get_settings
from real_basket.core.store import DataStore
from real_basket.flow.graph import FunctionNode, auto_approver, run_flow
from real_basket.flow.tools import FlowTools
from real_basket.knowledge import KnowledgeBase
from real_basket.knowledge.ingest import page_chunks, strip_repeated_headers, table_text_cells
from real_basket.schemas.flow import DatasetStatus, RunStatus, Trigger

REAL_DOCS = Path(__file__).resolve().parents[1] / "reports" / "real-data"

CAVEAT = [
    "Wichtig: Die Modellposition Wohnen / Energie ist keine Nettokaltmiete und enthält",
    "auch Nebenkosten sowie die Instandhaltung der Wohnung durch die Haushalte.",
]
TABLE = ["Bundesland-Abdeckung", "Bundesland", "Monatliche Miete", "Bayern", "Keine verifizierte Monatsreihe",
         "Hamburg", "Keine verifizierte Monatsreihe", "Berlin", "12,50 €", "13,10 €"]
LIMITS = ["Grenzen: Modellierte Eurobeträge können konkrete Preisbeobachtungen im Laden nicht ersetzen."]


def make_pdf(path: Path, pages: list[list[str]]) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    for n, lines in enumerate(pages, 1):
        y = 800
        for line in ["Lebenshaltungskosten Bericht", *lines, str(n)]:
            c.drawString(40, y, line)
            y -= 16
        c.showPage()
    c.save()


@pytest.fixture
def docs(tmp_path):
    d = tmp_path / "docs"
    d.mkdir()
    make_pdf(d / "Bericht_2025.pdf", [["Methodische Hinweise", *CAVEAT], [*TABLE, *LIMITS]])
    make_pdf(d / "Bericht_2026.pdf", [["Methodische Hinweise", *CAVEAT]])
    return d


@pytest.fixture
def settings(monkeypatch):
    def apply(**env):
        base = {"DEMO_FAULT_RATE": "0", "DEMO_FAULT_SEED": "1", "DESTATIS_GENESIS_TOKEN": "",
                "KNOWLEDGE_RETRIEVER": "bm25", "OPENAI_API_KEY": ""}
        for k, v in {**base, **env}.items():
            monkeypatch.setenv(k, str(v))
        get_settings.cache_clear()
        return get_settings()
    yield apply
    get_settings.cache_clear()


# --- ingestion --------------------------------------------------------------------------------
def test_table_keeps_descriptive_cells_and_drops_numbers():
    # 'Berlin' sits between rent values: a label of a numeric row -> dropped together with the numbers
    cells = ["Bayern", "Keine verifizierte Monatsreihe", "11,80 €", "Berlin", "12,50 €", "Hamburg",
             "Keine verifizierte Monatsreihe"]
    assert table_text_cells(cells) == ["Bayern", "Keine verifizierte Monatsreihe", "Hamburg",
                                       "Keine verifizierte Monatsreihe"]


def test_page_chunks_join_wrapped_prose():
    chunks = page_chunks(["Methodische Hinweise", *CAVEAT])
    notes = [c for c in chunks if c["kind"] == "note"]
    assert len(notes) == 1 and notes[0]["text"] == " ".join(CAVEAT)


def test_repeated_headers_and_page_numbers_are_removed():
    pages = strip_repeated_headers([["Kopfzeile", "1", "Text A"], ["Kopfzeile", "2", "Text B"]])
    assert pages == [["Text A"], ["Text B"]]


def test_index_dedups_and_never_contains_figures(docs, tmp_path, settings):
    kb = KnowledgeBase(doc_dir=docs, index_path=tmp_path / "idx.json", settings=settings())
    idx = kb.index()
    caveat = next(c for c in idx["chunks"] if "Nettokaltmiete" in c["text"])
    assert [loc["file"] for loc in caveat["locations"]] == ["Bericht_2025.pdf", "Bericht_2026.pdf"]
    assert caveat["years"] == [2025, 2026]
    assert not any(re.search(r"\d+,\d{2}", c["text"]) for c in idx["chunks"])
    assert any(c["kind"] == "table" and "Keine verifizierte Monatsreihe" in c["text"] for c in idx["chunks"])
    assert not any("Lebenshaltungskosten Bericht" in c["text"] for c in idx["chunks"])


def test_search_english_query_and_year_filter(docs, tmp_path, settings):
    kb = KnowledgeBase(doc_dir=docs, index_path=tmp_path / "idx.json", settings=settings())
    res = kb.search("is housing the net cold rent")
    assert res["retriever"] == "bm25" and "Nettokaltmiete" in res["passages"][0]["text"]
    assert res["passages"][0]["also_in"] == ["Bericht_2026.pdf p. 1"]
    assert all(2026 in p["years"] for p in kb.search("Grenzen Modell", year=2026)["passages"])
    assert kb.search("xyzzy")["passages"] == []


def test_index_is_rebuilt_when_documents_change(docs, tmp_path, settings):
    kb = KnowledgeBase(doc_dir=docs, index_path=tmp_path / "idx.json", settings=settings())
    assert len(kb.status()["documents"]) == 2
    make_pdf(docs / "Bericht_2027.pdf", [LIMITS])
    assert len(KnowledgeBase(doc_dir=docs, index_path=tmp_path / "idx.json",
                             settings=settings()).status()["documents"]) == 3


def test_missing_document_folder_returns_no_passages(tmp_path, settings):
    kb = KnowledgeBase(doc_dir=tmp_path / "none", index_path=tmp_path / "idx.json", settings=settings())
    res = kb.search("Miete")
    assert res["passages"] == [] and "No reference documents" in res["note"]


@pytest.mark.skipif(not REAL_DOCS.is_dir(), reason="reference PDFs not available")
def test_real_documents(tmp_path, settings):
    kb = KnowledgeBase(doc_dir=REAL_DOCS, index_path=tmp_path / "idx.json", settings=settings())
    top = kb.search("Ist Wohnen / Energie die Nettokaltmiete?")["passages"][0]
    assert "keine Nettokaltmiete" in top["text"]
    assert kb.search("Brandenburg Miete Bundesland")["passages"]


# --- flow integration ---------------------------------------------------------------------------
def scripted(results: dict, report_md: str, queries: int = 1):
    def factory(ctx):
        ft = FlowTools(ctx)

        def planner():
            return ft.submit_plan(24, "test", 1, "scripted", [])

        def collector():
            for d in ctx.with_status(DatasetStatus.PENDING):
                from real_basket.data.sources import sources_for
                ft.fetch(d, next(s.name for s in sources_for(d) if s.available()))
            return "collected"

        def validator():
            for d in ctx.with_status(DatasetStatus.COLLECTED):
                ft.decide(d, "accept", "scripted")
            return "validated"

        def analyst():
            if ft.results().get("investigation_required"):
                ft.investigate("category")
            results["searches"] = [ft.search_methodology("Nettokaltmiete Wohnen") for _ in range(queries)]
            results["bad_analysis"] = ft.submit_analysis("see [M7]", ["rent"], 0.9)
            ft.submit_analysis("Housing is not net cold rent [M1].", ["rent"], 0.9)
            return "analysed"

        def reporter():
            results["bad_report"] = ft.submit_report("# Report [M9]", ["chat"], 0.9)
            return ft.submit_report(report_md, ["chat"], 0.9)

        fns = {"planner": planner, "collector": collector, "validator": validator, "analyst": analyst,
               "reporter": reporter}
        return {n: FunctionNode(n, f) for n, f in fns.items()}
    return factory


def test_flow_citations_are_checked_and_listed(docs, tmp_path, settings):
    settings(KNOWLEDGE_DIR=str(docs), MAX_KNOWLEDGE_QUERIES="2")
    out: dict = {}
    ctx = run_flow("test goal", Trigger.SCHEDULE, approver=auto_approver,
                   executors=scripted(out, "# Report\nWohnen / Energie is not net cold rent [M1].", queries=3),
                   store=DataStore(tmp_path / "store"), end=date(2025, 12, 1))
    first, second, third = out["searches"]
    assert first["passages"][0]["cite"] == "[M1]" and first["passages"][0]["source"] == "Bericht_2025.pdf"
    assert second["passages"][0]["cite"] == "[M1]"          # same passage -> same citation id
    assert "budget" in third["error"]
    assert out["bad_analysis"].startswith("Rejected") and out["bad_report"].startswith("Rejected")
    assert ctx.run_status == RunStatus.PUBLISHED
    assert ctx.report["cited_notes"] == ["M1"]
    md = ctx.report["final_markdown"]
    assert "Method notes cited" in md and "[M1] Bericht_2025.pdf, p. 1" in md
    events = [e["action"] for e in ctx.store.load_audit(ctx.run_id)]
    assert events.count("unknown_citation_rejected") == 2 and "method_search" in events
    assert ctx.store.load_run(ctx.run_id)["method_notes"]["M1"]["source"] == "Bericht_2025.pdf"
