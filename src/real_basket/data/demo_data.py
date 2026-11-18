"""Deterministic synthetic demo data - replace with real collectors (scrapers / APIs) during the hackathon."""

from __future__ import annotations

from datetime import date

from real_basket.schemas.models import Category, CpiPoint, PricePoint

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


def demo_cpi(start: date = date(2024, 1, 1), months: int = 24) -> list[CpiPoint]:
    return [CpiPoint(period=p, index_value=round(_CPI_BASE * (1 + _CPI_MONTHLY_GROWTH) ** i, 2))
            for i, p in enumerate(_months(start, months))]
