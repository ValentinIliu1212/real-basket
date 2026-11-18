"""Source registry: alternative data sources per dataset.

The collector agent chooses a source at runtime (informed by reliability memory) and switches to an
alternative when the validator rejects the data. Demo "primary" sources randomly return faulty data
(unit errors, gaps, missing provenance) so that the non-deterministic validation loop is exercised
even without real APIs.

TODO (hackathon): add real sources here, e.g. Destatis GENESIS (61111-0002), Tankerkoenig,
BBSR rents, supermarket price APIs. A source only needs `available()` and `fetch()`.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, datetime

from real_basket.core.settings import get_settings
from real_basket.data.demo_data import demo_cpi, demo_prices
from real_basket.schemas.flow import Row
from real_basket.schemas.models import Category

CPI_ITEM = "VPI (2020=100)"


class SourceUnavailableError(RuntimeError):
    pass


def period_range(months: int, end: date | None = None) -> tuple[date, date]:
    """(start, end) of `months` months ending with `end` (default: the last completed month)."""
    if end is None:
        today = date.today()
        last = date(today.year - (today.month == 1), (today.month - 2) % 12 + 1, 1)
    else:
        last = date(end.year, end.month, 1)
    idx = last.year * 12 + last.month - 1 - (months - 1)
    return date(idx // 12, idx % 12 + 1, 1), last


@dataclass(frozen=True)
class Source:
    name: str
    dataset: str
    description: str
    prior_reliability: float = 0.8
    demo: bool = True
    faulty: bool = False             # demo only: injects faults with DEMO_FAULT_RATE
    requires_token: str | None = None

    def available(self) -> bool:
        if self.requires_token:
            return bool(getattr(get_settings(), self.requires_token, ""))
        return True

    def fetch(self, months: int, attempt: int = 0, end: date | None = None) -> list[Row]:
        if not self.available():
            raise SourceUnavailableError(f"{self.name}: not configured ({self.requires_token} missing)")
        if not self.demo:
            raise SourceUnavailableError(f"{self.name}: real connector not implemented yet")
        start, _ = period_range(months, end)
        rows = _demo_rows(self.dataset, start, months, self.name)
        if self.faulty:
            rows = _inject_fault(rows, self, attempt)
        return rows


def _demo_rows(dataset: str, start: date, months: int, source: str) -> list[Row]:
    now = datetime.now().isoformat(timespec="seconds")
    if dataset == "cpi":
        return [Row(dataset="cpi", item=CPI_ITEM, period=c.period.isoformat(), value=c.index_value,
                    unit="index", source=source, retrieved_at=now) for c in demo_cpi(start, months)]
    return [Row(dataset=dataset, item=p.item, period=p.period.isoformat(), value=p.price, unit=p.unit,
                source=source, retrieved_at=now)
            for p in demo_prices(start, months, Category(dataset))]


def _inject_fault(rows: list[Row], source: Source, attempt: int) -> list[Row]:
    settings = get_settings()
    seed = settings.DEMO_FAULT_SEED
    rng = random.Random(f"{seed}-{source.name}-{attempt}") if seed is not None else random.Random()
    if rng.random() >= settings.DEMO_FAULT_RATE:
        return rows
    fault = rng.choice(["unit_error", "missing_months", "missing_provenance"])
    rows = [r.model_copy() for r in rows]
    if fault == "unit_error":          # e.g. prices scraped in cent instead of EUR
        victim = rng.choice(rows[1:])
        victim.value = round(victim.value * 100, 4)
    elif fault == "missing_months":
        periods = sorted({r.period for r in rows})
        drop = set(rng.sample(periods[1:], k=min(2, len(periods) - 1)))
        rows = [r for r in rows if r.period not in drop]
    else:
        for r in rows:
            r.source = ""
    return rows


SOURCES: list[Source] = [
    Source("demo-supermarket-api", "food", "Supermarket price API (demo, error-prone)", 0.80, faulty=True),
    Source("demo-price-comparison", "food", "Price comparison portal (demo)", 0.70),
    Source("demo-rental-portal", "rent", "Rental portal asking rents (demo, error-prone)", 0.80, faulty=True),
    Source("demo-mietspiegel", "rent", "Municipal rent index / Mietspiegel (demo)", 0.70),
    Source("demo-tariff-portal", "energy", "Energy tariff comparison portal (demo, error-prone)", 0.80,
           faulty=True),
    Source("demo-bnetza-monitoring", "energy", "Bundesnetzagentur monitoring report (demo)", 0.70),
    Source("demo-tankerkoenig", "mobility", "Fuel price API (demo, error-prone)", 0.80, faulty=True),
    Source("demo-transport-tariffs", "mobility", "Public transport tariffs (demo)", 0.70),
    Source("destatis-genesis", "cpi", "Destatis GENESIS table 61111-0002 (official CPI)", 0.95, demo=False,
           requires_token="DESTATIS_GENESIS_TOKEN"),
    Source("demo-destatis", "cpi", "Official CPI (demo values, roughly realistic)", 0.90),
]


def sources_for(dataset: str) -> list[Source]:
    return [s for s in SOURCES if s.dataset == dataset]


def get_source(name: str) -> Source:
    for s in SOURCES:
        if s.name == name:
            return s
    raise KeyError(f"Unknown source '{name}'")
