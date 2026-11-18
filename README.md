# 🧺 RealBasket

> *What does living really cost?* An agentic AI system that captures prices of essential living costs
> (food, rent, energy, mobility), builds a realistic **essential living cost index** and compares it
> with the official **Consumer Price Index (CPI)**.

**Important:** A deviation does not mean that the official CPI is wrong. The two indices use different
baskets of goods and different weightings.

## Architecture

```
Streamlit UI ──► Orchestrator Agent (Strands, "RealBasket Analyst")
                   ├─ collect_category_prices ──► Collector Agent ──► fetch_prices (food/rent/energy/mobility)
                   ├─ fetch_official_cpi
                   └─ calculate_essential_vs_cpi ──► core/index.py (Laspeyres-style weighted index)
```

```
src/real_basket/
├── agents/        # Strands agents, prompts, tools
├── core/          # settings, index calculation
├── data/          # demo data (replace with real collectors)
├── schemas/       # pydantic models
├── ui/app.py      # Streamlit dashboard + agent chat
└── cli.py         # CLI entry point
```

## Setup

```powershell
poetry install
copy .env.example .env   # add OPENAI_API_KEY
poetry run pytest
poetry run streamlit run src/real_basket/ui/app.py
poetry run real-basket-cli "Are basic living costs rising faster than official inflation?"
poetry run real-basket-pdf --months 60 --out reports   # one PDF per year with monthly prices in EUR
```

## Methodology

- Category index: mean of item price relatives vs. base month (=100)
- Essential index: weighted sum of category indices (default: rent 40 %, food 30 %, energy 15 %, mobility 15 %)
- Comparison: YoY rates of both indices, deviation in percentage points (pp)

## Next steps (hackathon backlog)

> ⚠️ **Current state:** all prices and CPI values are **synthetic demo data** generated in
> `src/real_basket/data/demo_data.py`. The numbers shown in the UI are *not* real yet.

### 1. Replace the demo data with real sources
Each tool in `src/real_basket/agents/tools.py` currently calls `demo_prices()` / `demo_cpi()`.
Replace them with real collectors (one module per source under `src/real_basket/data/`) that return
`PricePoint` / `CpiPoint` objects, so the index calculation stays unchanged.

| Category | Candidate sources |
|----------|-------------------|
| CPI (official) | Destatis GENESIS API, table `61111-0002` (token in `.env`: `DESTATIS_GENESIS_TOKEN`), Eurostat HICP |
| Food | Destatis sub-indices (food 01.1), supermarket price APIs / web scraping |
| Rent | Destatis rent index, Mietspiegel data, rental portals |
| Energy | Bundesnetzagentur, energy tariff comparison portals, Destatis energy sub-indices |
| Mobility | Tankerkoenig fuel price API, public transport tariffs (Deutschlandticket) |

- [ ] Implement `fetch_official_cpi` with the Destatis GENESIS API
- [ ] Implement real collectors per category and switch via `USE_DEMO_DATA=false`
- [ ] Store the source (URL / API) in every `PricePoint.source` and show it in the UI

### 2. Data & methodology
- [ ] Persist collected prices (SQLite / parquet) so that history builds up over time
- [ ] Validate basket weights (e.g. derive from Destatis household budget survey / EVS)
- [ ] Household profiles (single, family, commuter) and regional baskets
- [ ] Keep the disclaimer visible: a deviation does **not** mean the CPI is wrong — different basket and weights

### 3. Agents
- [ ] Turn the collector into dedicated agents per category (multi-agent / graph pattern)
- [ ] Add session management (Strands `FileSessionManager`) for chat history
- [ ] Optional: expose collectors as MCP tools

### 4. Engineering
- [ ] CI pipeline (ruff + pytest)
- [ ] Dockerfile for the Streamlit app

## Contributing

1. Clone the repo and run `poetry install`, then copy `.env.example` to `.env`.
2. Create a feature branch: `git checkout -b feature/<short-name>`.
3. Run `poetry run ruff check .` and `poetry run pytest` before pushing.
4. Open a merge/pull request against `main`.

Never commit `.env` or API keys.
