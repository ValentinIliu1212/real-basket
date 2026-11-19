"""Shared helpers of the tool areas of the MCP server `realbasket`.

All figures are real data parsed deterministically from the reference PDFs (reports/real-data). There is no
synthetic data: if the PDFs are unavailable, every tool returns an `error` instead of numbers.
"""

from __future__ import annotations

from real_basket.data.basket import Basket, RealDataError, load_basket
from real_basket.schemas.models import CATEGORY_LABEL_DE, Category


def last_months(points: list, months: int) -> list:
    """The points of the most recent `months` periods - for OUTPUT only. Never slice prices before indexing: the
    base period (first month) fixes the effective weights of the essential index (see core.index)."""
    keep = set(sorted({p.period for p in points})[-max(months, 1):])
    return [p for p in points if p.period in keep]


def basket_or_error() -> tuple[Basket | None, dict | None]:
    try:
        return load_basket(), None
    except (RealDataError, OSError, ValueError) as exc:
        return None, {"error": f"Echte Daten nicht verfügbar (Referenz-PDFs in reports/real-data): {exc}"}


def basket_info(basket: Basket) -> dict:
    return {"data_basis": basket.label, "documents": basket.real.documents,
            "checks_passed": f"{sum(c.ok for c in basket.real.checks)}/{len(basket.real.checks)}",
            "categories": {c.value: CATEGORY_LABEL_DE[c] for c in basket.categories}}


def parse_category(basket: Basket, category: str) -> Category | None:
    try:
        cat = Category(category.lower().strip())
    except ValueError:
        return None
    return cat if cat in basket.categories else None


def category_error(basket: Basket) -> dict:
    return {"error": f"category must be one of {[c.value for c in basket.categories]}", **basket_info(basket)}
