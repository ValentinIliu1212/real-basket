"""Deterministic synthetic demo data - replace with real collectors (scrapers / APIs) during the hackathon."""

from __future__ import annotations

from datetime import date

from real_basket.schemas.models import Category, CpiPoint, PricePoint, RegionType

# item -> (category, base price EUR, monthly growth rate)
_DEMO_ITEMS: dict[str, tuple[Category, float, float]] = {
    "bread 1kg": (Category.FOOD, 3.20, 0.0040),
    "milk 1l": (Category.FOOD, 1.15, 0.0035),
    "butter 250g": (Category.FOOD, 2.29, 0.0020),
    "rent per m2 (net cold)": (Category.RENT, 10.50, 0.0042),
    "electricity per kWh": (Category.ENERGY, 0.40, -0.0010),
    "natural gas per kWh": (Category.ENERGY, 0.12, -0.0020),
    "public transport monthly ticket": (Category.MOBILITY, 49.00, 0.0050),
    "petrol per litre": (Category.MOBILITY, 1.80, 0.0005),
}

# Approximate asking rents (EUR per m2, net cold) as of start of the series + monthly growth rate.
# Rough orders of magnitude for demo purposes only - replace with real sources (see README).
RENT_ITEM = "Miete pro m² (nettokalt)"

STATE_RENTS: dict[str, tuple[float, float]] = {
    "Baden-Württemberg": (10.20, 0.0035),
    "Bayern": (11.60, 0.0038),
    "Berlin": (12.80, 0.0055),
    "Brandenburg": (7.90, 0.0032),
    "Bremen": (8.80, 0.0030),
    "Hamburg": (13.20, 0.0036),
    "Hessen": (10.30, 0.0034),
    "Mecklenburg-Vorpommern": (7.00, 0.0025),
    "Niedersachsen": (7.90, 0.0033),
    "Nordrhein-Westfalen": (8.30, 0.0034),
    "Rheinland-Pfalz": (8.00, 0.0030),
    "Saarland": (6.90, 0.0024),
    "Sachsen": (6.40, 0.0030),
    "Sachsen-Anhalt": (6.00, 0.0022),
    "Schleswig-Holstein": (9.10, 0.0031),
    "Thüringen": (6.30, 0.0026),
}

# 15 largest German cities by population
CITY_RENTS: dict[str, tuple[float, float]] = {
    "Berlin": (12.80, 0.0055),
    "Hamburg": (13.20, 0.0036),
    "München": (19.00, 0.0040),
    "Köln": (12.20, 0.0038),
    "Frankfurt am Main": (14.50, 0.0040),
    "Stuttgart": (13.80, 0.0037),
    "Düsseldorf": (11.50, 0.0036),
    "Leipzig": (7.40, 0.0045),
    "Dortmund": (8.10, 0.0036),
    "Essen": (7.70, 0.0034),
    "Bremen": (9.00, 0.0032),
    "Dresden": (7.80, 0.0035),
    "Hannover": (9.60, 0.0036),
    "Nürnberg": (10.60, 0.0036),
    "Duisburg": (6.90, 0.0030),
}

_CPI_BASE = 117.0
_CPI_MONTHLY_GROWTH = 0.0018  # ~2.2 % p.a.


def _months(start: date, n: int) -> list[date]:
    return [date(start.year + (start.month - 1 + i) // 12, (start.month - 1 + i) % 12 + 1, 1) for i in range(n)]


def demo_prices(start: date = date(2024, 1, 1), months: int = 24,
                category: Category | None = None) -> list[PricePoint]:
    result: list[PricePoint] = []
    for i, period in enumerate(_months(start, months)):
        for item, (cat, base, growth) in _DEMO_ITEMS.items():
            if category and cat != category:
                continue
            result.append(PricePoint(category=cat, item=item, period=period,
                                     price=round(base * (1 + growth) ** i, 4)))
    return result


def demo_regional_rents(start: date = date(2024, 1, 1), months: int = 24,
                        region_type: RegionType | None = None) -> list[PricePoint]:
    """Monthly rent per m2 for all federal states and the largest cities (demo data)."""
    sources = {RegionType.STATE: STATE_RENTS, RegionType.CITY: CITY_RENTS}
    result: list[PricePoint] = []
    for rtype, regions in sources.items():
        if region_type and rtype != region_type:
            continue
        for region, (base, growth) in regions.items():
            for i, period in enumerate(_months(start, months)):
                result.append(PricePoint(category=Category.RENT, item=RENT_ITEM, period=period,
                                         price=round(base * (1 + growth) ** i, 4), unit="EUR/m²",
                                         region=region, region_type=rtype))
    return result


def demo_cpi(start: date = date(2024, 1, 1), months: int = 24) -> list[CpiPoint]:
    return [CpiPoint(period=p, index_value=round(_CPI_BASE * (1 + _CPI_MONTHLY_GROWTH) ** i, 2))
            for i, p in enumerate(_months(start, months))]
