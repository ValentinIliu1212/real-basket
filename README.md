# 🧺 RealBasket

> *What does living really cost?* An agentic AI system that captures prices of essential living costs
> (food, rent, energy, mobility), builds a realistic **essential living cost index** and compares it
> with the official **Consumer Price Index (CPI)**.

**Important:** A deviation does not mean that the official CPI is wrong. The two indices use different
baskets of goods and different weightings.

> ⚠️ **All numbers are currently synthetic demo data** (rough orders of magnitude) — see [Next steps](#next-steps-hackathon-backlog).

## Features

| Feature | Description |
|---------|-------------|
| Essential living cost index | Weighted index of food, rent, energy and mobility (base month = 100), adjustable weights |
| CPI comparison | YoY rate of the essential index vs. official CPI, deviation in percentage points |
| Regional rents | Rent per m² (net cold) for all **16 federal states** and the **15 largest cities**, monthly |
| Average rents | Ø rent per state / city per year and over the whole period, plus Ø across all regions |
| Net salaries | Ø monthly net salary (full-time) per federal state, per year and total |
| Rent burden | Share of net salary needed for the net cold rent of a flat (default 70 m², adjustable) |
| PDF reports | One PDF per year + average rent report + net salary / rent burden report (German, EUR) |
| AI agent | Strands chat agent answering questions in natural language based on tool results |
| **Monitoring flow** | **Non-deterministic multi-agent process** (Strands Graph): planner → collector → validator loop → fixed calculation → analyst with investigation / re-planning → reporter → human approval → publish, with audit trail and memory |

## Architecture

Design rationale and process diagram: [docs/process-redesign.md](docs/process-redesign.md).

**1. Non-deterministic monitoring flow** (`src/real_basket/flow/`, Strands `GraphBuilder`)

```
trigger (schedule / question / price_alert)
  └► PLANNER agent ─► plan_gate ─► COLLECTOR agent ─► quality_checks ─► VALIDATOR agent ─► validation_gate
         ▲                              ▲                                                     │ retry: other source
         │                              └─────────────────────────────────────────────────────┤ (max 3 attempts)
         │                                                     exhausted ─► human_review ─────┤
         │                                                                                    ▼
         └──── re-plan (max 1) ◄── ANALYST agent ◄── calculate (fixed code, no LLM) ◄─────────┘
                                     │ investigate_deviation (category / item / region, max 4)
                                     ▼
                                 REPORTER agent ─► release_gate ─(confidence < 0.7: human approval)─► publish
```

- **Agents decide** (UPPERCASE): what to collect, which source, accept/retry/exclude, how deep to investigate,
  whether to re-plan, which outputs (chat / pdf / alert).
- **Code decides** (lowercase gates): budgets, hard quality rules (critical data can never be accepted),
  the numbers (`core/engine.py`), the confidence score and the mandatory disclaimer + provenance footer.
- Every run is stored in `data_store/runs/<run_id>/` (`run.json`, `dataset.json` with hash, raw source snapshots,
  `audit.jsonl`, published `report.md` / `report.pdf` / `alert.json`); `data_store/memory.json` keeps source
  reliability and past results for the next plan.

**2. Interactive chat agent** (`src/real_basket/agents/`, front door for ad-hoc questions)

```
Streamlit UI / CLI ──► Orchestrator Agent ("RealBasket Analyst")
                         ├─ collect_category_prices ──► Collector Agent ──► fetch_prices
                         ├─ fetch_official_cpi / calculate_essential_vs_cpi
                         ├─ fetch_regional_rents / fetch_net_salaries
                         ├─ investigate_deviation      ──► core/investigation.py
                         └─ run_monitoring_flow        ──► starts the monitoring flow above
```

```
src/real_basket/
├── agents/          # chat agent (orchestrator.py), prompts.py, tools.py
├── flow/            # monitoring flow: graph.py (Strands Graph), steps.py (deterministic nodes),
│                    #   tools.py (tools of the flow agents), context.py (run state), runner.py (CLI)
├── core/
│   ├── engine.py        # deterministic results (index, CPI deviation, dataset hash)
│   ├── index.py         # essential index + CPI comparison
│   ├── investigation.py # drill-down by category / item / region
│   ├── validation.py    # data quality rules (outliers, gaps, provenance)
│   ├── store.py         # data store, audit trail, memory
│   ├── rents.py / income.py  # Ø rents, net salaries, rent burden
│   └── settings.py      # .env based configuration incl. guardrail budgets
├── data/            # demo_data.py (synthetic), sources.py (source registry with alternatives)
├── reports/pdf_report.py  # PDF generation (reportlab)
├── schemas/         # models.py (prices, CPI, ...), flow.py (plan, validation, audit)
├── ui/app.py        # Streamlit dashboard, monitoring tab with approval, agent chat
└── cli.py           # chat CLI
tests/               # pytest (flow tests use scripted agents, no API key needed)
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

## Usage

```powershell
# Dashboard (http://localhost:8501)
poetry run streamlit run src/real_basket/ui/app.py

# Ask the agent from the command line
poetry run real-basket-cli "Are basic living costs rising faster than official inflation?"
poetry run real-basket-cli "In welchem Bundesland ist die Mietbelastung am höchsten?"

# PDF reports for the last 60 months (written to ./reports, git-ignored)
poetry run real-basket-pdf --months 60 --out reports

# Non-deterministic monitoring flow (runs stored in ./data_store, git-ignored)
poetry run real-basket-flow --trigger schedule
poetry run real-basket-flow --trigger question --goal "Why is rent rising faster than the CPI?"
poetry run real-basket-flow --trigger price_alert --goal "Fuel prices jumped" --approve interactive
```

`--approve`: `deferred` (default, low-confidence runs wait for approval in the dashboard), `interactive`
(ask in the terminal) or `auto` (demo only). Guardrails are configurable in `.env`: `MAX_SOURCE_ATTEMPTS`,
`MAX_INVESTIGATION_STEPS`, `MAX_REPLANS`, `MAX_NODE_EXECUTIONS`, `RUN_TIMEOUT_S`, `DEVIATION_THRESHOLD_PP`,
`CONFIDENCE_THRESHOLD`. `DEMO_FAULT_RATE` (default 0.35) makes demo sources randomly deliver faulty data so the
validation loop is exercised; set `DEMO_FAULT_SEED` for reproducible demos, `DEMO_FAULT_RATE=0` for clean data.

### Dashboard tabs

| Tab | Content |
|-----|---------|
| Index | Essential index vs. CPI (base = 100) |
| YoY rates | YoY inflation of both indices and the deviation (pp) |
| Categories | Index per category (food, rent, energy, mobility) |
| 🏠 Miete regional | Rent per m² per state / city: current, Ø period, YoY, comparison chart, Ø per year |
| 💶 Nettogehalt | Ø net salary per state, rent burden with flat-size slider, tables per year |
| 🔄 Monitoring runs | Start a monitoring flow run, see path / datasets / report per run, approve or reject pending runs, audit trail |
| 🤖 Ask the agent | Chat with the RealBasket agent |

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
- **Ø per year:** mean of the available months of that year (first/last year of the period may be incomplete).
- **Ø across all regions:** unweighted mean (not weighted by population).
- **Rent burden:** Ø rent €/m² × flat size (default 70 m²) ÷ Ø monthly net salary × 100.
- The essential index uses the national rent; regional rents are shown separately and do not feed into the index.

## Next steps (hackathon backlog)

> ⚠️ **Current state:** all prices, rents, net salaries and CPI values are **synthetic demo data** generated in
> `src/real_basket/data/demo_data.py`. The numbers shown in the UI, PDFs and agent answers are *not* real yet.

### 1. Replace the demo data with real sources
The tools in `src/real_basket/agents/tools.py`, the UI and the PDF reports currently call `demo_prices()`,
`demo_cpi()`, `demo_regional_rents()` and `demo_net_salaries()`. Replace them with real collectors
(one module per source under `src/real_basket/data/`) that return `PricePoint` / `CpiPoint` / `IncomePoint`
objects, so the calculations stay unchanged.

| Category | Candidate sources |
|----------|-------------------|
| CPI (official) | Destatis GENESIS API, table `61111-0002` (token in `.env`: `DESTATIS_GENESIS_TOKEN`), Eurostat HICP |
| Food | Destatis sub-indices (food 01.1), supermarket price APIs / web scraping |
| Rent | Destatis rent index, Mietspiegel data, rental portals |
| Rent per state / largest cities | BBSR Angebotsmieten (Kreise/Städte), Destatis Mietenindex per Bundesland, empirica/immowelt/ImmoScout24 price atlases |
| Net salary per state | Destatis Verdiensterhebung (gross, per Bundesland) + net calculation, BA Entgeltatlas, VGR der Länder (verfügbares Einkommen) |
| Energy | Bundesnetzagentur, energy tariff comparison portals, Destatis energy sub-indices |
| Mobility | Tankerkoenig fuel price API, public transport tariffs (Deutschlandticket) |

- [ ] Implement `fetch_official_cpi` with the Destatis GENESIS API
- [ ] Implement real collectors per category and switch via `USE_DEMO_DATA=false` (setting exists, not yet evaluated)
- [ ] Real regional rents per state / city (BBSR, Destatis, price atlases)
- [ ] Real net salaries per state (gross from Destatis → net calculation, or BA Entgeltatlas)
- [x] Store the source and a raw snapshot for every data point (monitoring flow, `data_store/`)
- [ ] Register real sources (with alternatives) in `src/real_basket/data/sources.py` so the collector agent can choose them
- [ ] Show sources in the dashboard tabs and the yearly PDFs (so far only in monitoring reports)

### 2. Data & methodology
- [ ] Move the file-based data store to SQLite / parquet so history builds up across runs
- [ ] Validate basket weights (e.g. derive from Destatis household budget survey / EVS)
- [ ] Optional population weighting for "Ø across all regions"
- [ ] Rent burden per city (requires net salaries per city)
- [ ] Household profiles (single, family, commuter) and regional baskets
- [ ] Keep the disclaimer visible: a deviation does **not** mean the CPI is wrong — different basket and weights

### 3. Agents
- [x] Non-deterministic monitoring flow (planner, collector, validator, analyst, reporter as Strands Graph)
- [x] Validation / retry loop, investigation loop, re-planning, human approval, audit trail, source memory
- [x] Monitoring reports always state demo data, provenance and the disclaimer (enforced in code)
- [ ] Make the chat agent always state explicitly when answers are based on demo data
- [ ] Dedicated collector agents per category running in parallel (Swarm / parallel graph nodes)
- [ ] Scheduler for the monthly `schedule` trigger and real price-alert triggers
- [ ] Web search / fetch tools for source discovery; optional: expose collectors as MCP tools
- [ ] Add session management (Strands `FileSessionManager`) for chat history

### 4. UI & reports
- [ ] Align the dashboard period with the PDF period (dashboard currently shows 24 months from 01/2024)
- [ ] PDF download buttons in the dashboard
- [ ] Replace deprecated `use_container_width` with `width="stretch"` (Streamlit ≥ 1.50)

### 5. Engineering
- [ ] CI pipeline (ruff + pytest)
- [ ] Dockerfile for the Streamlit app

## Contributing

1. Clone the repo and run `poetry install`, then copy `.env.example` to `.env`.
2. Create a feature branch: `git checkout -b feature/<short-name>`.
3. Run `poetry run ruff check .` and `poetry run pytest` before pushing.
4. Open a merge/pull request against `main`.

Never commit `.env` or API keys. Generated PDFs (`/reports`) are git-ignored.
