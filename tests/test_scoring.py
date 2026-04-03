from __future__ import annotations

import unittest

from stockscope.models import Fundamentals, PriceSnapshot
from stockscope.scoring import score_ticker


class ScoringTests(unittest.TestCase):
    def test_strong_stock_gets_high_signal(self) -> None:
        fundamentals = Fundamentals(
            symbol="TEST",
            quote_type="EQUITY",
            short_name="Test Corp",
            sector="Technology",
            industry="Software",
            trailing_pe=20,
            forward_pe=18,
            price_to_sales=4,
            enterprise_to_ebitda=14,
            revenue_growth=0.12,
            earnings_growth=0.18,
            gross_margins=0.55,
            profit_margins=0.22,
            free_cashflow=1000,
            operating_cashflow=1200,
            debt_to_equity=40,
            return_on_equity=0.18,
        )
        price = PriceSnapshot(
            symbol="TEST",
            closes=[100 + i * 0.1 for i in range(180)],
            current_price=112,
            sma20=111,
            sma60=110,
            sma120=107,
            high_52w=118,
            low_52w=90,
            return_6m=0.12,
            return_1y=0.20,
        )
        benchmark = PriceSnapshot(symbol="SPY", closes=[1], return_6m=0.04)

        scored = score_ticker(fundamentals, price, benchmark)
        self.assertGreaterEqual(scored.entry_score, 70)
        self.assertIn(scored.signal, {"A", "B"})

    def test_weak_stock_gets_low_signal(self) -> None:
        fundamentals = Fundamentals(
            symbol="BAD",
            quote_type="EQUITY",
            short_name="Bad Corp",
            trailing_pe=80,
            forward_pe=55,
            price_to_sales=18,
            enterprise_to_ebitda=40,
            revenue_growth=-0.10,
            earnings_growth=-0.20,
            gross_margins=0.10,
            profit_margins=-0.05,
            free_cashflow=-100,
            operating_cashflow=-50,
            debt_to_equity=260,
            return_on_equity=0.01,
        )
        price = PriceSnapshot(
            symbol="BAD",
            closes=[100 - i * 0.2 for i in range(180)],
            current_price=65,
            sma20=70,
            sma60=78,
            sma120=88,
            high_52w=120,
            low_52w=60,
            return_6m=-0.25,
            return_1y=-0.35,
        )
        benchmark = PriceSnapshot(symbol="SPY", closes=[1], return_6m=0.04)

        scored = score_ticker(fundamentals, price, benchmark)
        self.assertLessEqual(scored.entry_score, 45)
        self.assertEqual(scored.signal, "D")


if __name__ == "__main__":
    unittest.main()
