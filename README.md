# 🧺 RealBasket

> *What does living really cost?* An agentic AI system that captures prices of essential living costs
> (food, rent, energy, mobility), builds a realistic **essential living cost index** and compares it
> with the official **Consumer Price Index (CPI)**.

**Important:** A deviation does not mean that the official CPI is wrong. The two indices use different
baskets of goods and different weightings.

> **Data:** the essential basket, the CPI (VPI) and the rents of the 15 largest cities are **real data** read
> deterministically from the reference PDFs in `reports/real-data` (ECLI model calculation: Destatis EVS 2023
> expenditure + official price indices, 11/2024–10/2026) and re-checked in code. Rents per federal state and net
> salaries are still **synthetic demo data** and labelled as such. The UI is fully German.

## Demo in 3 minutes

1. `poetry run streamlit run src/real_basket/ui/app.py` → the header shows essential inflation, VPI, the
   deviation and its **biggest driver** ("Größter Einflussfaktor") at a glance (real data 10/2026: 2,93 % vs. 2,83 %, +0,11 PP, driver
   Verkehr / Mobilität). The expander **Datenprüfung** lists the 9 re-checks of the PDF import.
2. Move the **basket weights** in the sidebar → index, deviation and drivers update immediately (untouched
   sliders = exact expenditure shares of the reference basket). Switch **Datenquelle** real ↔ demo; the chat
   agent follows that choice (a new chat starts).
3. **🧩 Einflussfaktoren**: which category causes the deviation (contributions add up exactly to the deviation).
4. **🏠 Miete regional / 💶 Nettogehalt**: rents per state (demo) / city (real), rent burden (demo).
5. **📚 Methodenhinweise (RAG)**: search the unstructured reference PDFs, e.g. *"Ist Wohnen / Energie die
   Nettokaltmiete?"* → passage with file and page.
6. **🤖 Chat mit RealBasket**: click an example question; the answer (always German) shows which tools were used.
7. Sidebar **📄 PDF-Berichte**: download the reference PDFs and the generated German demo reports.

## Features

| Feature | Description |
|---------|-------------|
| Essential living cost index | Weighted index of the basket groups (real: Lebensmittel, Wohnen / Energie, Verkehr, Gesundheit, Kommunikation; demo: food, rent, energy, mobility), base month = 100, adjustable weights |
| Real-data import | `data/real_data.py`: tables of the reference PDFs parsed without LLM, 9 re-checks (sums, gaps, printed ECLI and yearly rates recomputed by the engine, …) |
| CPI comparison | YoY rate of the essential index vs. official VPI, deviation in percentage points |
| Deviation drivers | Exact contribution of every category to the deviation (`core/investigation.py`) |
| Regional rents | 15 largest cities: real asking rents Jan vs. Oct 2026 (immowelt, from the reference PDF); 16 federal states: demo |
| Net salaries & rent burden | Ø monthly net salary per state; share needed for the rent of a flat (default 70 m²) – demo |
| PDF reports | One PDF per year + average rent + net salary / rent burden + CPI report (German, EUR) – demo |
| AI agent | Strands chat agent that decides itself which tools to call; numbers only from deterministic tools; answers in German |
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
├── data/
│   ├── real_data.py     # deterministic import + re-checks of the reference PDF tables
│   ├── basket.py        # load_basket(): DATA_SOURCE auto | real | demo
│   └── demo_data.py     # synthetic demo data
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

# PDF reports (demo data) for the last 60 months (written to ./reports, git-ignored)
poetry run real-basket-pdf --months 60 --out reports

# Method notes of the reference PDFs (versioned in ./reports/real-data)
poetry run real-basket-knowledge --rebuild
poetry run real-basket-knowledge --query "Ist Wohnen / Energie die Nettokaltmiete?"
```

Settings in `.env`: `DATA_SOURCE` (`auto` | `real` | `demo`), `OPENAI_API_KEY`, `OPENAI_MODEL_ID`,
`KNOWLEDGE_DIR` (default `reports/real-data`), `KNOWLEDGE_RETRIEVER` (`auto` | `bm25` | `embedding`),
`EMBEDDING_MODEL_ID`, `KNOWLEDGE_TOP_K` (4). Relative paths are resolved against the project root if they do not
exist in the current folder, and `.env` is read from the project root – so the app works from any folder.

> **"0 Dokumente" in the method-notes tab?** Up to commit `cd9772a` the whole `/reports` folder was git-ignored,
> so the reference PDFs never reached other machines. They are now versioned (`reports/real-data/*.pdf`):
> `git pull` and restart Streamlit.

**Azure OpenAI** instead of api.openai.com (an Azure key sent to OpenAI fails with `401 Incorrect API key`):

```dotenv
OPENAI_API_TYPE=azure
OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com/
AZURE_OPENAI_API_KEY=<key>
AZURE_COMPLETION_MODEL=gpt-4o                  # chat deployment name
AZURE_EMBEDDING_MODEL=text-embedding-3-large   # embedding deployment name (method-note search)
```

The sidebar shows the active provider (`Azure OpenAI · gpt-4o`). Provider selection lives in
`src/real_basket/core/llm.py`.
Without PDFs the search returns no passages; everything else works unchanged.

### Dashboard tabs

| Tab | Content |
|-----|---------|
| Header | Essential inflation, VPI, deviation and biggest driver of the latest month + disclaimer + data check |
| 📈 Index vs. VPI | Both indices (base = 100), YoY rates and deviation (PP); real data: monthly costs per group |
| 🧩 Einflussfaktoren | Contribution of each category to the deviation, index per category |
| 🏠 Miete regional | Cities: real asking rents Jan/Oct 2026; states: demo rent per m², YoY, comparison chart |
| 💶 Nettogehalt | Ø net salary per state, rent burden with flat-size slider, tables per year (demo) |
| 📚 Methodenhinweise (RAG) | Index status and search over the reference PDFs with file + page |
| 🤖 Chat mit RealBasket | Chat (German) with follow-up questions, example questions, tools used per answer |

### PDF reports

| File | Content |
|------|---------|
| `realbasket_preise_<year>.pdf` | Monthly prices (EUR) of all basket items + CPI; rent per state and per city with Ø row (3 pages) |
| `realbasket_miete_durchschnitt.pdf` | Ø rent per state and per city, per year and total |
| `realbasket_nettogehalt_durchschnitt.pdf` | Ø net salary per state per year and total; rent burden (70 m²) per year |
| `realbasket_verbraucherpreisindex.pdf` | CPI (2020 = 100) per month, inflation rate vs. previous year's month, yearly comparison CPI vs. essential index |

## Methodology

- **Category index:** mean of item price relatives vs. base month (= 100).
- **Essential index:** weighted sum of category indices. Default weights – real data: expenditure shares of the
  ECLI reference basket (base amounts 11/2024 ÷ 2.174 €: Wohnen / Energie 52,3 %, Lebensmittel 20,1 %, Verkehr
  16,6 %, Kommunikation 6,5 %, Gesundheit 4,5 %); demo: rent 40 %, food 30 %, energy 15 %, mobility 15 %.
- **Real-data re-checks** (`data/real_data.py`): base amounts sum to the total, first month = base basket, no
  gaps, row sums, ECLI recomputed by the engine = printed ECLI (≤ 0,05), both ECLI tables agree, printed yearly
  rates reproduced, repeated values identical across reports, VPI present for every month.
- **CPI comparison:** YoY rates of both indices; deviation = essential YoY − CPI YoY in percentage points (pp).
- **Drivers:** contribution_pp = weight × change of the category index ÷ previous essential index × 100;
  gap_pp = contribution − weight × CPI YoY. The gaps add up to the deviation.
- **Ø per year:** mean of the available months of that year (first/last year of the period may be incomplete).
- **Ø across all regions:** unweighted mean (not weighted by population).
- **Rent burden:** Ø rent €/m² × flat size (default 70 m²) ÷ Ø monthly net salary × 100.
- The essential index uses the national rent; regional rents are shown separately and do not feed into the index.

## Next steps (hackathon backlog)

> ⚠️ **Current state:** basket, VPI and city rents are real data from the reference PDFs. Rents per federal state,
> net salaries and the generated PDF reports are still **synthetic demo data** (`src/real_basket/data/demo_data.py`).

### 1. Replace the remaining demo data with real sources
Replace `demo_regional_rents()` and `demo_net_salaries()` (and live updates of the basket) with real collectors
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

- [x] Import the monthly tables of the reference PDFs (`reports/real-data`) as a data source, re-checked in code
- [ ] Implement `fetch_official_cpi` with the Destatis GENESIS API (live updates beyond 10/2026)
- [ ] Generate the PDF reports from the real basket

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

Never commit `.env` or API keys. Generated PDFs (`/reports/*.pdf`) and the local index (`/data_store`) are
git-ignored; the reference PDFs in `reports/real-data` are versioned (source of the real data).