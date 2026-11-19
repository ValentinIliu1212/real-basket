"""Documentation must not drift from the data and the code (review 11/2026)."""

from pathlib import Path

import pytest

from real_basket.core.investigation import deviation_breakdown
from real_basket.data.basket import load_basket
from real_basket.schemas.models import CATEGORY_LABEL_DE, Category

ROOT = Path(__file__).resolve().parents[1]
REAL_DOCS = ROOT / "reports" / "real-data"
needs_docs = pytest.mark.skipif(not REAL_DOCS.is_dir(), reason="reference PDFs not available")


def de(value: float, sign: bool = False) -> str:
    return f"{value:{'+' if sign else ''}.2f}".replace(".", ",")


@needs_docs
def test_readme_figures_match_the_data():
    b = load_basket()
    res = deviation_breakdown(b.prices, b.cpi, b.weights)
    driver = res["categories"][0]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    expected = [f"{de(res['essential_yoy_pct'])} % vs. {de(res['cpi_yoy_pct'])} %",
                f"{de(res['deviation_pp'], sign=True)} PP",
                f"{CATEGORY_LABEL_DE[Category(driver['category'])]} {de(driver['gap_pp'], sign=True)} PP"]
    for text in expected:
        assert text in readme, f"README is stale, expected {text!r}"


def test_docs_do_not_mention_removed_parts():
    """Outside the documented review decisions, the docs must not describe removed parts or old names."""
    for path, decisions in [(ROOT / "README.md", "## Review decisions"),
                            (ROOT / "docs" / "process-redesign.md", "## 7. Review")]:
        text = path.read_text(encoding="utf-8")
        assert decisions in text, path
        before, after = text.split(decisions, 1)
        rest = after.split("\n## ", 1)                       # the decision section ends at the next heading
        text = before + (rest[1] if len(rest) > 1 else "")
        assert "collect_category_prices" not in text, path
        assert "Verkehr / Mobilität" not in text, path
        assert "11 re-checks" not in text, path
