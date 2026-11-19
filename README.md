# 🧺 RealBasket

> *What does living really cost?* An agentic AI system that captures prices of essential living costs
> (food, rent, energy, mobility), builds a realistic **essential living cost index** and compares it
> with the official **Consumer Price Index (CPI)**.

**Important:** A deviation does not mean that the official CPI is wrong. The two indices use different
baskets of goods and different weightings.

> ⚠️ **All numbers are currently synthetic demo data** (rough orders of magnitude) — see [Next steps](#next-steps-hackathon-backlog).

## Demo in 3 minutes

1. `poetry run streamlit run src/real_basket/ui/app.py` → the header shows essential inflation, CPI, the
   deviation and its **biggest driver** at a glance.
2. Move the **basket weights** in the sidebar → index, deviation and drivers update immediately.
3. **🧩 Drivers**: which category causes the deviation (contributions add up exactly to the deviation).
4. **🏠 Miete regional / 💶 Nettogehalt**: rents per state / city, rent burden in % of the net salary.
5. **📚 Method notes (RAG)**: search the unstructured reference PDFs, e.g. *"Ist Wohnen / Energie die
   Nettokaltmiete?"* → passage with file and page.
6. **🤖 Ask the agent**: click an example question; the answer shows which tools the agent chose.
7. Sidebar **📄 PDF reports**: download the German PDF reports.

## Features

| Feature | Description |
|---------|-------------|
| Essential living cost index | Weighted index of food, rent, energy and mobility (base month = 100), adjustable weights |
| CPI comparison | YoY rate of the essential index vs. official CPI, deviation in percentage points |
| Deviation drivers | Exact contribution of every category to the deviation (`core/investigation.py`) |
| Regional rents | Rent per m² (net cold) for all **16 federal states** and the **15 largest cities**, monthly |
| Net salaries & rent burden | Ø monthly net salary per state; share needed for the rent of a flat (default 70 m²) |
| PDF reports | One PDF per year + average rent + net salary / rent burden + CPI report (German, EUR) |
| AI agent | Strands chat agent that decides itself which tools to call; numbers only from deterministic tools |
| Method notes (RAG) | Search over method notes and caveats of reference PDFs (`reports/real-data`), cited with file + page. Context only – figures never come from text search |

## Architecture

Design rationale: [docs/process-redesign.md](docs/process-redesign.md).

```
Streamlit UI / CLI ──► Orchestrator Agent REALBASKET-ORCHESTRATOR (LLM chooses the tools)
                         ├─ calculate_essential_vs_cpi  ──► core/index.py          (deterministic)
                         ├─ investigate_deviation       ──► core/investigation.py  (category → item → region)
                         ├─ collect_category_prices     ──► Collector Agent ──► fetch_prices
                         ├─ fetch_official_cpi / fetch_regional_rents / fetch_net_salaries
                         └─ search_methodology          ──► knowledge/ (RAG over reference PDFs)
```

- **The agent decides** which tools a question needs and how deep to drill down ("why?" → category, then item
  or region). **Code decides the numbers**: the LLM never calculates rates itself.
- **RAG** (`src/real_basket/knowledge/`):
  - *Ingest* (pypdf): prose paragraphs (method notes, caveats, data-quality hints) and the non-numeric cells of
    tables become passages. Numeric cells are dropped on purpose; passages repeated across yearly reports are
    stored once with all locations.
  - *Search*: `bm25` (offline, German-aware: stemming, compounds such as Kaltmiete → Nettokaltmiete,
    English → German glossary) or `embedding` (OpenAI, fused with BM25). `auto` = embedding if an API key is
    set; embedding errors fall back to BM25. The index `data_store/knowledge/index.json` is rebuilt
    automatically when the PDFs change.

```
src/real_basket/
├── agents/          # orchestrator.py (chat agent + collector sub-agent), prompts.py, tools.py
├── core/
│   ├── index.py         # essential index + CPI comparison
│   ├── investigation.py # deviation drivers, drill-down by item / region
│   ├── rents.py / income.py  # Ø rents, net salaries, rent burden
│   └── settings.py      # .env based configuration
├── data/demo_data.py # synthetic demo data
├── knowledge/       # RAG: ingest.py (passages), search.py (index, BM25 / embeddings, CLI)
├── reports/pdf_report.py  # PDF generation (reportlab)
├── schemas/models.py
├── ui/app.py        # Streamlit dashboard
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
poetry run real-basket-cli "In welchem Bundesland ist die Mietbelastung am höchsten?"

# PDF reports for the last 60 months (written to ./reports, git-ignored)
poetry run real-basket-pdf --months 60 --out reports

# Method notes of the reference PDFs (put them into ./reports/real-data, git-ignored)
poetry run real-basket-knowledge --rebuild
poetry run real-basket-knowledge --query "Ist Wohnen / Energie die Nettokaltmiete?"
```

Settings in `.env`: `OPENAI_API_KEY`, `OPENAI_MODEL_ID`, `KNOWLEDGE_DIR` (default `reports/real-data`),
`KNOWLEDGE_RETRIEVER` (`auto` | `bm25` | `embedding`), `EMBEDDING_MODEL_ID`, `KNOWLEDGE_TOP_K` (4).
Without PDFs the search returns no passages; everything else works unchanged.

### Dashboard tabs

| Tab | Content |
|-----|---------|
| Header | Essential inflation, CPI, deviation and biggest driver of the latest month + disclaimer |
| 📈 Index vs. CPI | Both indices (base = 100), YoY rates and deviation (pp) |
| 🧩 Drivers | Contribution of each category to the deviation, index per category |
| 🏠 Miete regional | Rent per m² per state / city: current, Ø period, YoY, comparison chart, Ø per year |
| 💶 Nettogehalt | Ø net salary per state, rent burden with flat-size slider, tables per year |
| 📚 Method notes (RAG) | Index status and search over the reference PDFs with file + page |
| 🤖 Ask the agent | Chat with follow-up questions, example questions, tools used per answer |

### PDF reports

| File | Content |
|------|---------|
| `realbasket_preise_<year>.pdf` | Monthly prices (EUR) of all basket items + CPI; rent per state and per city with Ø row (3 pages) |
| `realbasket_miete_durchschnitt.pdf` | Ø rent per state and per city, per year and total |
| `realbasket_nettogehalt_durchschnitt.pdf` | Ø net salary per state per year and total; rent burden (70 m²) per year |
| `realbasket_verbraucherpreisindex.pdf` | CPI (2020 = 100) per month, inflation rate vs. previous year's month, yearly comparison CPI vs. essential index |

## Methodology

- **Category index:** mean of item price relatives vs. base month (= 100).
- **Essential index:** weighted sum of category indices (default: rent 40 %, food 30 %, energy 15 %, mobility 15 %).
- **CPI comparison:** YoY rates of both indices; deviation = essential YoY − CPI YoY in percentage points (pp).
- **Drivers:** contribution_pp = weight × change of the category index ÷ previous essential index × 100;
  gap_pp = contribution − weight × CPI YoY. The gaps add up to the deviation.
- **Ø per year:** mean of the available months of that year (first/last year of the period may be incomplete).
- **Ø across all regions:** unweighted mean (not weighted by population).
- **Rent burden:** Ø rent €/m² × flat size (default 70 m²) ÷ Ø monthly net salary × 100.
- The essential index uses the national rent; regional rents are shown separately and do not feed into the index.

## Next steps (hackathon backlog)

> ⚠️ **Current state:** all prices, rents, net salaries and CPI values are **synthetic demo data** generated in
> `src/real_basket/data/demo_data.py`. The numbers shown in the UI, PDFs and agent answers are *not* real yet.

### 1. Replace the demo data with real sources
Replace `demo_prices()`, `demo_cpi()`, `demo_regional_rents()` and `demo_net_salaries()` with real collectors
(one module per source under `src/real_basket/data/`) that return `PricePoint` / `CpiPoint` / `IncomePoint`
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

- [ ] Import the monthly tables of the reference PDFs (`reports/real-data`) as a data source, re-checked in code
- [ ] Implement `fetch_official_cpi` with the Destatis GENESIS API; switch via `USE_DEMO_DATA=false`
- [ ] Show sources in the dashboard and the PDFs

### 2. Later (out of hackathon scope)
- [ ] Scheduled monitoring with validation, human approval and audit trail (a first version existed as a
      Strands Graph up to commit `f9344ef` and was removed to keep the demo focused)
- [ ] Compare a focus category with the matching CPI sub-index (e.g. energy vs. CPI energy)
- [ ] Household profiles (single, family, commuter), population weighting, rent burden per city
- [ ] CI pipeline (ruff + pytest), Dockerfile

## Contributing

1. Clone the repo and run `poetry install`, then copy `.env.example` to `.env`.
2. Create a feature branch: `git checkout -b feature/<short-name>`.
3. Run `poetry run ruff check .` and `poetry run pytest` before pushing.
4. Open a merge/pull request against `main`.

Never commit `.env` or API keys. Generated PDFs (`/reports`) and the local index (`/data_store`) are git-ignored.
