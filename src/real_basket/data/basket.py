"""Data source of the essential basket: real data from the reference PDFs (default) or synthetic demo data.

DATA_SOURCE=auto  -> real data if the PDFs in KNOWLEDGE_DIR can be read and re-checked, otherwise demo data
DATA_SOURCE=real  -> real data (falls back to demo data with an error message if unavailable)
DATA_SOURCE=demo  -> demo data
"""

from __future__ import annotations

from dataclasses import dataclass

from real_basket.core.settings import get_settings
from real_basket.data.demo_data import demo_cpi, demo_prices
from real_basket.data.real_data import RealDataError, RealDataset, load_real_data
from real_basket.schemas.models import BasketWeights, Category, CpiPoint, PricePoint


@dataclass
class Basket:
    source: str                      # "real" | "demo"
    label: str                       # German description for UI / agent
    prices: list[PricePoint]
    cpi: list[CpiPoint]
    weights: BasketWeights           # default weights of this basket
    real: RealDataset | None = None
    error: str | None = None         # why real data could not be used

    @property
    def categories(self) -> list[Category]:
        return [c for c in Category if c in self.weights.weights]


_active_source: str | None = None


def set_data_source(source: str | None) -> None:
    """Override DATA_SOURCE for all later `load_basket()` calls (e.g. the agent tools follow the data source
    chosen in the dashboard sidebar). None -> back to the DATA_SOURCE setting."""
    global _active_source
    if source is not None and source.lower() not in ("auto", "real", "demo"):
        raise ValueError(f"unknown data source {source!r} (auto | real | demo)")
    _active_source = source.lower() if source else None


def active_data_source() -> str:
    return _active_source or get_settings().DATA_SOURCE.lower()


def load_basket(source: str | None = None) -> Basket:
    source = (source or active_data_source()).lower()
    error = None
    if source in ("auto", "real"):
        try:
            ds = load_real_data()
            return Basket(source="real", prices=ds.prices, cpi=ds.cpi, weights=ds.weights, real=ds,
                          label="Echte Daten: ECLI-Referenzwarenkorb (Destatis EVS 2023 + VPI), "
                                + f"{ds.periods[0]:%m/%Y}–{ds.periods[-1]:%m/%Y}")
        except (RealDataError, OSError, ValueError) as exc:
            error = str(exc)
    return Basket(source="demo", prices=demo_prices(), cpi=demo_cpi(), weights=BasketWeights(),
                  label="Synthetische Demo-Daten", error=error)
