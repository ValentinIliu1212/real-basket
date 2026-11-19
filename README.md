# 🧺 RealBasket

> *What does living really cost?* An agentic AI system that captures prices of essential living costs
> (food, rent, energy, mobility), builds a realistic **essential living cost index** and compares it
> with the official **Consumer Price Index (CPI)**.

**Important:** A deviation does not mean that the official CPI is wrong. The two indices use different
baskets of goods and different weightings.

> **Data:** the essential basket, the CPI (VPI) and the rents of the 15 largest cities are **real data** read
> deterministically from the reference PDFs in `reports/real-data` (ECLI model calculation: Destatis EVS 2023
> expenditure + official price indices, 11/2024–10/2026) and re-checked in code. There is **no synthetic demo
> data**: without the reference PDFs the app shows an error instead of numbers. The sources contain no rent per
> federal state and no net salaries – these are reported as "not in the reference data", never estimated.
> The UI is fully German.

## Demo in 3 minutes

1. `poetry run streamlit run src/real_basket/ui/app.py` → the header shows essential inflation, VPI, the
   deviation and its **biggest driver** ("Größter Einflussfaktor") at a glance (real data 10/2026: 2,93 % vs. 2,83 %, +0,11 PP¹, driver
   Verkehr +0,94 PP). The expander **Datenprüfung** lists the re-checks of the PDF import.

   ¹ The deviation is computed from the unrounded rates (2,9326… − 2,8265… = 0,1061… ≈ 0,11), so it can differ by
   0,01 PP from the difference of the rounded rates (2,93 − 2,83 = 0,10). A test keeps these README figures in sync
   with the data.
2. Move the **basket weights** in the sidebar → index, deviation and drivers update immediately (untouched
   sliders = exact expenditure shares of the reference basket).
3. **🧩 Einflussfaktoren**: which category causes the deviation (contributions add up exactly to the deviation).
4. **🏠 Miete Städte**: real asking rents of the 15 largest cities (€/m² and 75-m² flat, Jan vs. Oct 2026) and
   the coverage per federal state (which cities have published rents – no state averages).
5. **📚 Methodenhinweise (RAG)**: search the unstructured reference PDFs, e.g. *"Ist Wohnen / Energie die
   Nettokaltmiete?"* → passage with file and page.
6. **🤖 Chat mit RealBasket**: click an example question; the answer (always German) shows which tools were used,
   and figures that no tool result backs are flagged below the answer (number guardrail).
7. Sidebar **📄 PDF-Berichte**: download the reference PDFs and the German RealBasket reports generated from them.
8. **🛰️ Monitoring**: the architecture diagram below with the use-case path of every interaction highlighted
   (numbered edges = order of the steps). After a chat question you see e.g. UI → Orchestrator → LLM →
   MCPClient → `analysis` → `core/investigation.py` → `data/` → … → number guardrail → UI.

## Features

| Feature | Description |
|---------|-------------|
| Essential living cost index | Weighted index of the 5 basket groups (Lebensmittel, Wohnen / Energie, Verkehr, Gesundheit, Kommunikation), base 11/2024 = 100, adjustable weights |
| Real-data import | `data/real_data.py`: tables of the reference PDFs parsed without LLM, deterministic re-checks (sums, gaps, printed ECLI and yearly rates recomputed by the engine, city rents, state coverage, …) |
| CPI comparison | YoY rate of the essential index vs. official VPI, deviation in percentage points |
| Deviation drivers | Exact contribution of every category to the deviation (`core/investigation.py`) |
| City rents | 15 largest cities: real asking rents Jan vs. Oct 2026 (immowelt, from the reference PDF), incl. 75-m² flat |
| Coverage per federal state | 16 states: no verified state rent series in the sources; lists the cities with published rents |
| PDF reports | One PDF per year + city rents + CPI report (German, EUR), generated from the real data |
| AI agent | Strands chat agent that decides itself which tools to call; numbers only from deterministic tools; answers in German |
| Number guardrail | `agents/guardrail.py`: every figure of an answer is matched against the tool results of the conversation; unbacked figures are flagged in chat and CLI |
| Method notes (RAG) | Search over method notes and caveats of reference PDFs (`reports/real-data`), cited with file + page. Context only – figures never come from text search |
| Monitoring | `ui/monitoring.py`: every interaction (dashboard load / weight change, RAG search, PDF reports, chat question, new chat) is recorded as a use-case path and drawn on the architecture diagram (Graphviz, rendered in the browser). Chat paths come from the real Strands messages (LLM calls, MCP tool calls, tool errors, guardrail result) |

## Architecture

Design rationale: [docs/process-redesign.md](docs/process-redesign.md).

Architecture slides in `docs/architecture/`, German and English: current state (`RealBasket_Architektur_Ist.pptx` /
`RealBasket_Architecture_Current.pptx`) and the target proposal with MCP and A2A
(`RealBasket_Architektur_Vorschlag_MCP_A2A.pptx` / `RealBasket_Architecture_Proposal_MCP_A2A.pptx`). Regenerate
with `poetry run python docs/architecture/build_decks.py` (English texts in `docs/architecture/texts_en.py`; the
build stops if a German text has no translation).

```
Streamlit UI / CLI ──► Orchestrator Agent REALBASKET-ORCHESTRATOR (LLM chooses the tools)
        ▲                └─ MCPClient (stdio subprocess or Streamable HTTP via MCP_URL)
        │                     ▼
        │                MCP server `realbasket` (one process, one module per area)
        │                  ├─ data:      get_basket · get_prices · get_cpi · calculate_index · data_checks
        │                  │             resources basket://weights · basket://checks       ──► core/index.py, data/
        │                  ├─ analysis:  investigate_deviation · get_regional_rents          ──► core/investigation.py
        │                  └─ knowledge: search_methodology · list_documents
        │                                resource doc://{file}/seite/{page} · prompt hinweis_zitieren ──► knowledge/
        └── number guardrail (agents/guardrail.py): figures of the answer vs. tool results
```

- **One MCP server** (`src/real_basket/mcp_servers/server.py`) for the hackathon: one process (PDFs parsed once),
  one client config. The areas are separate modules, so a later split needs only `--areas` – tool names stay the
  same. The dashboard still calls `core/` and `data/` directly (same numbers, no LLM).
- **The agent decides** which tools a question needs and how deep to drill down ("why?" → category, then item
  or region). **Code decides the numbers**: the LLM never calculates rates itself, and the number guardrail
  flags any figure in an answer that no tool result backs.
- **RAG** (`src/real_basket/knowledge/`):
  - *Ingest* (pypdf): prose paragraphs (method notes, caveats, data-quality hints) and the non-numeric cells of
    tables become passages. Numeric cells are dropped on purpose; passages repeated across yearly reports are
    stored once with all locations.
  - *Search*: `bm25` (offline, German-aware: stemming, compounds such as Kaltmiete → Nettokaltmiete,
    English → German glossary) or `embedding` (OpenAI / Azure OpenAI, fused with BM25). `auto` = embedding if an
    LLM provider is configured (`core.llm.is_configured`, i.e. also with Azure); embedding errors fall back to
    BM25. The index `data_store/knowledge/index.json` is rebuilt automatically when the PDFs change; the
    embedding vectors are recomputed automatically when the provider or embedding model changes.

```
src/real_basket/
├── agents/          # orchestrator.py (chat agent), guardrail.py (number check of answers), mcp_clients.py,
│                    # prompts.py, tools.py (plain-Python access to the tool functions)
├── mcp_servers/     # MCP server `realbasket`: server.py + data_tools / analysis_tools / knowledge_tools
├── core/
│   ├── index.py         # essential index + CPI comparison
│   ├── investigation.py # deviation drivers, drill-down by item / city, state coverage
│   ├── llm.py           # OpenAI / Azure OpenAI provider
│   └── settings.py      # .env based configuration
├── data/
│   ├── real_data.py     # deterministic import + re-checks of the reference PDF tables
│   └── basket.py        # load_basket(): real data only, raises RealDataError
├── knowledge/       # RAG: ingest.py (passages), search.py (index, BM25 / embeddings, CLI)
├── reports/pdf_report.py  # PDF generation (reportlab)
├── schemas/models.py
├── ui/app.py        # Streamlit dashboard
├── ui/monitoring.py # use-case paths of the interactions + architecture diagram (DOT)
└── cli.py           # chat CLI
```

## Setup

Requirements: Python ≥ 3.11, [Poetry](https://python-poetry.org/) ≥ 2.0, an OpenAI API key (only for the agent).

```powershell
git clone https://github.com/ValentinIliu1212/real-basket.git
cd real-basket
poetry install
copy .env.example .env   # add your own OPENAI_API_KEY
poetry run pytest
```

> Windows: if `poetry` is not on PATH, use `& "$env:APPDATA\Python\Scripts\poetry.exe"` instead.

### Eclipse (optional)

The repo contains an Eclipse `.project` file (UTF-8 encoding preset).

1. **File → Import… → General → Existing Projects into Workspace**, select the repo folder, leave
   "Copy projects into workspace" unchecked.
2. Install **PyDev** (Eclipse Marketplace), add the Poetry virtualenv interpreter
   (`poetry env info --path` → `Scripts\python.exe`) under **Preferences → PyDev → Interpreters**.
3. Right-click the project → **PyDev → Set as PyDev Project**, add `/real-basket/src` to the PYTHONPATH.
4. Start Streamlit from a terminal (no Eclipse launcher).

## Usage

```powershell
# Dashboard (http://localhost:8501)
poetry run streamlit run src/real_basket/ui/app.py

# Ask the agent from the command line
poetry run real-basket-cli "Are basic living costs rising faster than official inflation? Why?"
poetry run real-basket-cli "In welchen Großstädten sind die Mieten am stärksten gestiegen?"

# PDF reports from the real data (written to ./reports, git-ignored)
poetry run real-basket-pdf --out reports

# Method notes of the reference PDFs (versioned in ./reports/real-data)
poetry run real-basket-knowledge --rebuild
poetry run real-basket-knowledge --query "Ist Wohnen / Energie die Nettokaltmiete?"

# MCP server `realbasket` (the chat agent starts it itself via stdio)
poetry run real-basket-mcp                                          # stdio
poetry run real-basket-mcp --transport streamable-http --port 8001  # then MCP_URL=http://127.0.0.1:8001/mcp
poetry run real-basket-mcp --areas data,analysis                    # subset of the areas
```

**Use the MCP server from Claude Desktop / VS Code** (`claude_desktop_config.json` or `.vscode/mcp.json`; use the
interpreter of `poetry env info --path`):

```json
{"mcpServers": {"realbasket": {"command": "<venv>\\Scripts\\python.exe",
  "args": ["-m", "real_basket.mcp_servers.server"], "cwd": "<path>\\real-basket"}}}
```

Settings in `.env` (template: `.env.example`): `OPENAI_API_KEY`, `OPENAI_MODEL_ID`, `EMBEDDING_MODEL_ID`
(OpenAI only, default `text-embedding-3-small`; Azure uses `AZURE_EMBEDDING_MODEL`),
`KNOWLEDGE_DIR` (default `reports/real-data`; source of the real data and the method notes), `KNOWLEDGE_RETRIEVER` (`auto` | `bm25` | `embedding`),
`KNOWLEDGE_TOP_K` (4), `MCP_URL` (empty = stdio subprocess), `MCP_STARTUP_TIMEOUT` (60 s). Relative paths are resolved against the project root if they do not
exist in the current folder, and `.env` is read from the project root – so the app works from any folder.

The provider settings are validated (`core.llm.config_issues`): missing key / endpoint or an unknown
`OPENAI_API_TYPE` stop the chat agent at start-up with a clear message; contradictions (e.g. the Azure key also in
`OPENAI_API_KEY`, or a non-`sk-` key sent to api.openai.com) are shown as warnings in the sidebar and by the CLI.

> **"0 Dokumente" in the method-notes tab?** Up to commit `cd9772a` the whole `/reports` folder was git-ignored,
> so the reference PDFs never reached other machines. They are now versioned (`reports/real-data/*.pdf`):
> `git pull` and restart Streamlit.

**Azure OpenAI** instead of api.openai.com (an Azure key sent to OpenAI fails with `401 Incorrect API key`).
Leave `OPENAI_API_KEY` **empty** with Azure – the key belongs in `AZURE_OPENAI_API_KEY` only:

```dotenv
OPENAI_API_KEY=
OPENAI_API_TYPE=azure
OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com/
AZURE_OPENAI_API_KEY=<key>
AZURE_COMPLETION_MODEL=gpt-4o                  # chat deployment name
AZURE_EMBEDDING_MODEL=text-embedding-3-large   # embedding deployment name (method-note search)
```

The sidebar shows the active provider (`Azure OpenAI · gpt-4o`). Provider selection lives in
`src/real_basket/core/llm.py`.
Without the reference PDFs the dashboard, the agent tools and the PDF reports stop with an error (no fallback).

### Dashboard tabs

| Tab | Content |
|-----|---------|
| Header | Essential inflation, VPI, deviation and biggest driver of the latest month + disclaimer + data check |
| 📈 Index vs. VPI | Both indices (base = 100), YoY rates and deviation (PP), monthly costs per group |
| 🧩 Einflussfaktoren | Contribution of each category to the deviation, index per category |
| 🏠 Miete Städte | Real asking rents of the 15 largest cities Jan/Oct 2026 (€/m², 75 m²); coverage per federal state |
| 📚 Methodenhinweise (RAG) | Index status and search over the reference PDFs with file + page |
| 🤖 Chat mit RealBasket | Chat (German) with follow-up questions, example questions, tools used per answer |
| 🛰️ Monitoring | Architecture diagram with the highlighted use-case path of the selected interaction (latest first), step table (from → to, action, details, status), history of the session |

### PDF reports

| File | Content |
|------|---------|
| `realbasket_preise_<year>.pdf` | 2024–2026: modelled monthly costs (EUR) per group + sum; ECLI (recomputed and printed) and VPI |
| `realbasket_miete_staedte.pdf` | Asking rents of the 15 largest cities (€/m², 75 m², Jan vs. Oct 2026); coverage per federal state |
| `realbasket_verbraucherpreisindex.pdf` | VPI vs. ECLI (11/2024 = 100) per month, YoY rates, deviation; data checks |

## Methodology

- **Category index:** mean of item price relatives vs. base month (= 100). The reference data has one item per
  group (its modelled monthly cost), so this is the price relative of the group.
- **Essential index:** fixed-weight sum of category indices. Default weights – real data: expenditure shares of the
  ECLI reference basket (base amounts 11/2024 ÷ 2.174 €: Wohnen / Energie 52,3 %, Lebensmittel 20,1 %, Verkehr
  16,6 %, Kommunikation 6,5 %, Gesundheit 4,5 %). With these weights the index equals a Laspeyres index of the
  modelled monthly costs (Σ costs(t) ÷ Σ costs(11/2024)).
- **Fixed base 11/2024 = 100:** every tool indexes the full series and slices only its output. The base month fixes
  the effective weights, so `months` never changes a rate (before the review, `months=13` gave 2,91 % instead of
  2,93 %).
- **Real-data re-checks** (`data/real_data.py`): base amounts sum to the total, first month = base basket, no
  gaps, row sums, ECLI recomputed by the engine = printed ECLI (≤ 0,05), both ECLI tables agree, printed yearly
  rates reproduced, repeated values identical across reports, VPI present for every month, city rent changes and
  75-m² rents recomputed, federal-state coverage consistent with the city table.
- **CPI comparison:** YoY rates of both indices, matched **by date** (a missing month gives no rate instead of a
  comparison with the wrong month); deviation = essential YoY − CPI YoY in percentage points (pp), computed from
  the unrounded rates.
- **Drivers:** contribution_pp = weight × change of the category index ÷ previous essential index × 100;
  gap_pp = contribution − weight × CPI YoY. Weights are normalised to 1, so the gaps always add up to the deviation.
- **Ø across all cities:** unweighted mean (not weighted by population).
- **Federal states:** no state averages are derived from city values (not representative); only the coverage is shown.
- The essential index uses "Wohnen / Energie" of the reference basket (more than the net cold rent); city rents
  are shown separately and do not feed into the index.

## Known limitations

- **Modelled, not measured:** the monthly costs are EVS 2023 expenditure amounts updated with official price
  indices (ECLI model calculation) – no shop prices, no own price collection.
- **Fixed data range:** 11/2024–10/2026 from the reference PDFs; no live updates (today is later than the data).
- **Coarse drill-down:** one item per expenditure group, so the `item` level only repeats the group's own change.
- **Regions:** 15 city asking rents (immowelt, Jan vs. Oct 2026); no rent per federal state, no net salaries, no
  rent burden. "Ø alle Städte" is unweighted (not by population).
- **One household type:** expenditure shares of an average household; no profiles (single, family, commuter).
- **Guardrail scope:** it checks figures, not statements – a correct figure attached to the wrong group is not
  detected; plain integers without unit (counts, page numbers) are not checked.
- **Rounding:** deviations are computed from unrounded rates and can differ by 0,01 PP from the difference of the
  rounded rates.

## Review decisions (11/2026)

| Topic | Decision | Reason |
|-------|----------|--------|
| Group name "Verkehr" vs. "Verkehr / Mobilität" | **"Verkehr"** everywhere (UI, prompt, PDFs, slides); a test pins the labels to the PDF group names | wording of the source PDFs / Destatis COICOP 07, so citations, RAG passages and answers match |
| Collector sub-agent | **removed**; `get_prices` returns a deterministic `summary` (first / last value, change %, YoY) | it added an LLM call per group and let an LLM compute percentages; planned again as an A2A service once live sources exist |
| Number guardrail | **flag, don't rewrite**: unbacked figures are listed below the answer | deterministic, no second LLM call; the user sees exactly what is unverified |
| Provider config | errors stop the agent at start-up, contradictions are warnings | the dashboard (no LLM) must keep working with a broken LLM config |
| Rounded deviation | keep the unrounded calculation, document it (README, dashboard tooltip, slides) | more accurate than subtracting rounded rates |
| Figures on slides | generated from the data when building the decks; test counts removed | slides cannot go stale |
| `months` parameter | kept for compatibility; only selects the output window (`history`) | the base period is always 11/2024 |
| ruff | updated to 0.17 and its default rules kept (findings fixed) | current tooling; CI enforces it |

## Next steps (hackathon backlog)

> **Current state:** all figures are real data from the reference PDFs (11/2024–10/2026). Not available in the
> sources and therefore not shown: rents per federal state, net salaries / rent burden, live updates.

### 1. Extend the real data
Add live collectors (one module per source under `src/real_basket/data/`) that return `PricePoint` / `CpiPoint`
objects, so the calculations stay unchanged.

| Category | Candidate sources |
|----------|-------------------|
| CPI (official) | Destatis GENESIS API, table `61111-0002` (token in `.env`: `DESTATIS_GENESIS_TOKEN`), Eurostat HICP |
| Food | Destatis sub-indices (food 01.1), supermarket price APIs / web scraping |
| Rent | Destatis rent index, Mietspiegel data, rental portals |
| Rent per state / largest cities | BBSR Angebotsmieten, Destatis Mietenindex per Bundesland, price atlases |
| Net salary per state | Destatis Verdiensterhebung + net calculation, BA Entgeltatlas |
| Energy | Bundesnetzagentur, tariff comparison portals, Destatis energy sub-indices |
| Mobility | Tankerkoenig fuel price API, public transport tariffs (Deutschlandticket) |

- [x] Import the monthly tables of the reference PDFs (`reports/real-data`) as a data source, re-checked in code
- [ ] Live VPI collector with the Destatis GENESIS API, table `61111-0002` (updates beyond 10/2026; today `get_cpi`
      / its alias `fetch_official_cpi` only read the reference PDFs)
- [x] Generate the PDF reports from the real basket
- [x] Remove the synthetic demo data (no fallback)
- [ ] Verified rent series per federal state and net salaries (new sources) – then rent burden

### 2. Later (out of hackathon scope)
- [ ] Scheduled monitoring with validation, human approval and audit trail (a first version existed as a
      Strands Graph up to commit `f9344ef` and was removed to keep the demo focused)
- [ ] Compare a focus category with the matching CPI sub-index (e.g. energy vs. CPI energy)
- [ ] Household profiles (single, family, commuter), population weighting, rent burden per city
- [x] CI pipeline (ruff + pytest + deck build, `.github/workflows/ci.yml`)
- [ ] Dockerfile

## Contributing

1. Clone the repo and run `poetry install`, then copy `.env.example` to `.env`.
2. Create a feature branch: `git checkout -b feature/<short-name>`.
3. Run `poetry run ruff check .` and `poetry run pytest` before pushing (CI runs both plus the deck build).
4. Open a merge/pull request against `main`.

Never commit `.env` or API keys. Generated PDFs (`/reports/*.pdf`) and the local index (`/data_store`) are
git-ignored; the reference PDFs in `reports/real-data` are versioned (source of the real data).