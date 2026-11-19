# Process: agentic analysis with a deterministic core

> Status: November 2026. Optimised for the hackathon demo: one interactive agent, no background runs.
> The earlier non-deterministic monitoring flow (Strands Graph with planner, collector, validator, analyst,
> reporter, human approval and data store) was removed; it is available in git history up to commit `f9344ef`.
> The review of 11/2026 also removed the collector sub-agent and added a number guardrail (see section 7).

## 1. Design principle

**Non-deterministic shell, deterministic core.**

- **LLM agent decides:** which tools a question needs, in which order, how deep to drill down, and how to word
  the answer (always German).
- **Code decides:** every number (index, YoY rates, deviation, driver contributions, city rents). An LLM never
  calculates an inflation rate. The disclaimer is part of the system prompt and always shown in the dashboard.
- **Code checks the answer:** the number guardrail (`agents/guardrail.py`) matches every figure of an answer
  against the tool results of the conversation and flags unbacked figures in chat and CLI.
- **Reference documents** (`reports/real-data`) serve two separate purposes:
  - *Tables → real data* (`data/real_data.py`): parsed deterministically (no LLM, no text search), re-checked
    in code (sums, gaps, printed ECLI and yearly rates reproduced by the engine, consistency across reports, city
    rents, federal-state coverage).
  - *Prose → method notes (RAG)*: context and caveats only, never figures.
- **Real data only:** there is no synthetic demo data and no fallback. If the PDFs are missing or unreadable,
  `load_basket()` raises `RealDataError`; the dashboard shows the error and every tool returns `{"error": …}`.
  Untouched weight sliders use the exact (unrounded) basket weights, so dashboard, agent and printed ECLI agree.
- **No invented figures:** the sources contain no rent per federal state and no net salaries. The agent and the
  dashboard say so and show only which cities of a state have published rents.

## 2. Process diagram

```mermaid
flowchart TD
    U(["Question<br/>dashboard chat · real-basket-cli"]) --> O
    O["REALBASKET-ORCHESTRATOR (agent)<br/>chooses tools"]
    O -- "MCP (stdio / HTTP)" --> M
    subgraph M["MCP server realbasket (one process)"]
        C["data: calculate_index, get_cpi, get_prices, data_checks<br/>(code: core/index.py)"]
        I["analysis: investigate_deviation<br/>category → item / city<br/>(code: core/investigation.py)"]
        R["analysis: get_regional_rents (cities, state coverage)"]
        K["knowledge: search_methodology<br/>(RAG: knowledge/, BM25 / embeddings)"]
    end
    K --> PDF[("reports/real-data/*.pdf<br/>method notes, caveats")]
    C & I & R --> B[("load_basket()<br/>real data: PDF tables, re-checked<br/>no fallback")]
    B --> PDF
    C & I & R & K --> A(["Answer (German): headline + max. 5 bullets,<br/>data basis, citations [Datei S. N], disclaimer"])
    A --> G{{"number guardrail<br/>figures vs. tool results"}}
    G --> U2(["answer + flagged unbacked figures"])
```

Typical "why" path: `investigate_deviation(level='category')` → category with the largest |gap_pp| →
`level='item'` (or `'region'` for rent) → optional `search_methodology` for caveats.

## 3. Deviation drivers (deterministic)

For the latest month *t* and *t−12* (matched by date; the index always uses the full series, base 11/2024 = 100,
because the base month fixes the effective weights):

- contribution_pp(c) = w_c × (I_c(t) − I_c(t−12)) ÷ E(t−12) × 100 — sums to the essential YoY rate
- gap_pp(c) = contribution_pp(c) − w_c × CPI YoY — sums to the deviation (essential YoY − CPI YoY)
- weights are normalised to 1 inside the calculation, so the sums hold for any weights; the deviation is computed
  from unrounded rates (it can differ by 0,01 PP from the difference of the rounded rates)

The dashboard header shows the category with the largest |gap_pp| as "Größter Einflussfaktor" (biggest driver).

## 4. Method notes (RAG)

| Step | Implementation |
|------|----------------|
| Ingest | pypdf text per page; repeated headers removed; prose blocks → `note` passages, non-numeric table cells → `table` passages; numeric cells dropped; identical passages across yearly reports deduplicated with all locations |
| Index | `data_store/knowledge/index.json`, rebuilt when file size / mtime of a PDF changes |
| Retrieval | `bm25` offline (German stemming, compounds, English → German glossary); `embedding` (OpenAI / Azure OpenAI) fused with BM25 by reciprocal rank fusion; `auto` picks embedding if an LLM provider is configured (`core.llm.is_configured`); errors fall back to BM25; vectors are recomputed when the embedding model changes |
| Use | Chat tool `search_methodology` (cite as `[file p. N]`), dashboard tab 📚 Method notes, CLI `real-basket-knowledge` |
| Guardrail | Prompt + tool docstring: never take figures from passages; numbers only from the calculation tools |

## 5. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Hallucinated numbers | All figures from deterministic tools; prompt forbids own calculations; number guardrail flags every figure not backed by a tool result |
| LLM derives numbers (e.g. subtracts rounded rates) | Prompt: quote `deviation_pp` as returned; tools return `deviation_note`; guardrail flags derived figures |
| Wrong rates through a shifted base month | Tools always index the full series (base 11/2024); tests pin results independent of `months` |
| Broken / contradictory LLM settings | `core.llm.config_issues`: errors stop the agent at start-up, warnings (e.g. Azure key in `OPENAI_API_KEY`) in sidebar and CLI |
| Misreading the deviation as "CPI is wrong" | Disclaimer in prompt, dashboard header and PDFs |
| Invented regional figures | No state rents / salaries in the sources → tools return the coverage only, prompt forbids estimates |
| Misparsed PDF tables | Deterministic re-checks, shown in the dashboard (Datenprüfung) and the VPI report |
| Stale figures in docs / slides | Slide figures computed when the decks are built; a test compares the README figures with the data; CI builds the decks |
| PDFs missing on another machine | Reference PDFs versioned in git; relative paths resolved against the project root; otherwise a clear error (no fallback) |
| Figures quoted from PDFs | Numeric table cells are not indexed; passages are context only |
| No API key during the demo | Dashboard, drivers, PDFs and method-note search (BM25) work offline; only the chat needs a key |

## 6. Out of scope for the hackathon

Scheduled monitoring with validation / retry loops, human approval, audit trail and source memory (see git
history `f9344ef`), live data collectors (Destatis GENESIS), verified federal-state rent series and net salaries
(new sources needed; then rent burden).

## 7. Review 11/2026: decisions

- **One group name "Verkehr"** (not "Verkehr / Mobilität"): the wording of the source PDFs, pinned by a test.
- **Collector sub-agent removed:** it cost one LLM call per group and let an LLM compute percentages; `get_prices`
  now returns a deterministic `summary`. A price-collector agent returns in phase 2 (A2A) with live sources.
- **Number guardrail flags, it does not rewrite:** deterministic, no second LLM call, the user sees what is
  unverified. Scope: figures, not statements.
- **Provider configuration:** errors fail fast (chat agent), contradictions are warnings; the dashboard keeps
  working without LLM.
- **`months`** only selects the output window; rates never depend on it.
- Details and the full list: README, sections "Known limitations" and "Review decisions".
