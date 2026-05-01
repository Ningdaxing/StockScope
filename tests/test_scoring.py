from __future__ import annotations

import unittest

from stockscope.models import (
    EtfEntryConfig,
    EtfValuationConfig,
    FactorThresholds,
    Fundamentals,
    PositionConfig,
    PriceSnapshot,
    QualityConfig,
    ScoredTicker,
    ScoringConfig,
    StockEntryConfig,
    StockValuationConfig,
    TrendConfig,
    YieldThresholds,
)
from stockscope.scoring import (
    band_score,
    cashflow_score,
    clamp,
    finalize_signal,
    inverse_score,
    is_earnings_soon,
    margin_score,
    relative_strength,
    score_etf_entry,
    score_etf_valuation,
    score_position_adjustment,
    score_quality,
    score_stock_entry,
    score_stock_valuation,
    score_ticker,
    score_trend,
    yield_score,
)


def _make_fundamentals(**overrides) -> Fundamentals:
    """构建测试用的 Fundamentals，默认值是一支健康股票。"""
    defaults: dict = dict(
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
    defaults.update(overrides)
    return Fundamentals(**defaults)


def _make_price(**overrides) -> PriceSnapshot:
    """构建测试用的 PriceSnapshot，默认值是一支温和上涨的股票。"""
    defaults: dict = dict(
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
    defaults.update(overrides)
    return PriceSnapshot(**defaults)


# ---------------------------------------------------------------------------
# 已有个股全流程
# ---------------------------------------------------------------------------
class ScoringTests(unittest.TestCase):
    def test_strong_stock_gets_high_signal(self) -> None:
        fundamentals = _make_fundamentals()
        price = _make_price()
        benchmark = PriceSnapshot(symbol="SPY", closes=[1], return_6m=0.04)
        scored = score_ticker(fundamentals, price, benchmark)
        self.assertGreaterEqual(scored.entry_score, 70)
        self.assertIn(scored.signal, {"A", "B"})

    def test_weak_stock_gets_low_signal(self) -> None:
        fundamentals = _make_fundamentals(
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
        price = _make_price(
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


# ---------------------------------------------------------------------------
# ETF 路径
# ---------------------------------------------------------------------------
class EtfScoringTests(unittest.TestCase):
    def test_etf_valuation_and_entry(self) -> None:
        f = _make_fundamentals(quote_type="ETF", trailing_pe=20, forward_pe=18, dividend_yield=0.04)
        p = _make_price()
        benchmark = PriceSnapshot(symbol="SPY", closes=[1], return_6m=0.04)
        scored = score_ticker(f, p, benchmark)
        self.assertEqual(scored.asset_type, "ETF")
        self.assertIsNone(scored.quality_score)
        self.assertGreater(scored.valuation_score, 50)
        self.assertGreater(scored.entry_score, 50)

    def test_etf_high_pe_lowers_valuation(self) -> None:
        f = _make_fundamentals(quote_type="ETF", trailing_pe=50, forward_pe=45, dividend_yield=0)
        p = _make_price()
        scored = score_ticker(f, p)
        self.assertLess(scored.valuation_score, 50)

    def test_mutualfund_treated_as_etf(self) -> None:
        f = _make_fundamentals(quote_type="MUTUALFUND")
        p = _make_price()
        scored = score_ticker(f, p)
        self.assertEqual(scored.asset_type, "ETF")


# ---------------------------------------------------------------------------
# 信号等级边界
# ---------------------------------------------------------------------------
class SignalBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = ScoringConfig.defaults()

    def test_signal_A_at_threshold(self) -> None:
        _, signal, _ = finalize_signal(78, [], config=self.config)
        self.assertEqual(signal, "A")

    def test_signal_B_at_threshold(self) -> None:
        _, signal, _ = finalize_signal(64, [], config=self.config)
        self.assertEqual(signal, "B")

    def test_signal_C_at_threshold(self) -> None:
        _, signal, _ = finalize_signal(50, [], config=self.config)
        self.assertEqual(signal, "C")

    def test_signal_D_below_threshold(self) -> None:
        _, signal, _ = finalize_signal(49, [], config=self.config)
        self.assertEqual(signal, "D")

    def test_signal_B_one_below_A(self) -> None:
        _, signal, _ = finalize_signal(77, [], config=self.config)
        self.assertEqual(signal, "B")

    def test_clamp_floor(self) -> None:
        score, _, _ = finalize_signal(-100, [], config=self.config)
        self.assertEqual(score, 0)

    def test_clamp_ceiling(self) -> None:
        score, _, _ = finalize_signal(200, [], config=self.config)
        self.assertEqual(score, 100)

    def test_no_notes_gives_balanced(self) -> None:
        _, _, note = finalize_signal(70, [], config=self.config)
        self.assertEqual(note, "balanced")


# ---------------------------------------------------------------------------
# 缺失数据
# ---------------------------------------------------------------------------
class MissingDataTests(unittest.TestCase):
    def test_all_none_fundamentals_still_scores(self) -> None:
        f = Fundamentals(symbol="X", quote_type="EQUITY")
        p = _make_price()
        scored = score_ticker(f, p)
        self.assertIsInstance(scored.entry_score, int)
        self.assertIn(scored.signal, {"A", "B", "C", "D"})

    def test_no_price_closes(self) -> None:
        f = _make_fundamentals()
        p = PriceSnapshot(symbol="X", closes=[])
        scored = score_ticker(f, p)
        self.assertIsInstance(scored.entry_score, int)

    def test_no_benchmark(self) -> None:
        f = _make_fundamentals()
        p = _make_price()
        scored = score_ticker(f, p, benchmark_price=None)
        self.assertGreater(scored.trend_score, 0)


# ---------------------------------------------------------------------------
# 质量分
# ---------------------------------------------------------------------------
class QualityScoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = ScoringConfig.defaults().quality

    def test_strong_quality_above_70(self) -> None:
        f = _make_fundamentals()
        score = score_quality(f, config=self.config)
        self.assertGreaterEqual(score, 75)

    def test_weak_quality_below_30(self) -> None:
        f = _make_fundamentals(
            revenue_growth=-0.10, earnings_growth=-0.20,
            gross_margins=0.10, profit_margins=-0.05,
            return_on_equity=0.01, debt_to_equity=260,
            free_cashflow=-100, operating_cashflow=-50,
        )
        score = score_quality(f, config=self.config)
        self.assertLessEqual(score, 30)

    def test_all_none_fields_neutral(self) -> None:
        f = _make_fundamentals(
            revenue_growth=None, earnings_growth=None,
            gross_margins=None, profit_margins=None,
            return_on_equity=None, debt_to_equity=None,
            free_cashflow=None, operating_cashflow=None,
        )
        score = score_quality(f, config=self.config)
        self.assertEqual(score, 50)


# ---------------------------------------------------------------------------
# 个股估值分
# ---------------------------------------------------------------------------
class StockValuationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = ScoringConfig.defaults().stock_valuation

    def test_low_pe_gets_high_score(self) -> None:
        f = _make_fundamentals(trailing_pe=10, forward_pe=10, price_to_sales=2, enterprise_to_ebitda=8)
        score = score_stock_valuation(f, config=self.config)
        self.assertGreaterEqual(score, 80)

    def test_high_pe_gets_low_score(self) -> None:
        f = _make_fundamentals(trailing_pe=100, forward_pe=80, price_to_sales=20, enterprise_to_ebitda=50)
        score = score_stock_valuation(f, config=self.config)
        self.assertLessEqual(score, 30)


# ---------------------------------------------------------------------------
# ETF 估值分
# ---------------------------------------------------------------------------
class EtfValuationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = ScoringConfig.defaults().etf_valuation

    def test_high_dividend_boosts_score(self) -> None:
        f = _make_fundamentals(trailing_pe=20, forward_pe=18, dividend_yield=0.05)
        score = score_etf_valuation(f, config=self.config)
        self.assertGreater(score, 50)

    def test_no_dividend_no_extra_boost(self) -> None:
        f = _make_fundamentals(trailing_pe=20, forward_pe=18, dividend_yield=0)
        score = score_etf_valuation(f, config=self.config)
        self.assertLessEqual(score, 62)  # base 50 + trailing_pe + forward_pe


# ---------------------------------------------------------------------------
# 趋势分
# ---------------------------------------------------------------------------
class TrendScoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = ScoringConfig.defaults().trend
        self.benchmark = PriceSnapshot(symbol="SPY", closes=[1], return_6m=0.04)

    def test_all_smas_above_gives_high_score(self) -> None:
        p = _make_price(current_price=115, sma20=110, sma60=105, sma120=100)
        score = score_trend(p, self.benchmark, config=self.config)
        self.assertGreaterEqual(score, 80)

    def test_all_smas_below_gives_low_score(self) -> None:
        p = _make_price(
            current_price=90, sma20=110, sma60=105, sma120=100,
            high_52w=120, return_6m=-0.15,
        )
        score = score_trend(p, self.benchmark, config=self.config)
        self.assertLess(score, 55)

    def test_mild_drawdown_gets_bonus(self) -> None:
        p = _make_price(
            current_price=106, high_52w=118,
            sma20=104, sma60=102, sma120=99,
        )
        score = score_trend(p, None, config=self.config)
        self.assertGreater(score, 55)

    def test_severe_drawdown_gets_penalty(self) -> None:
        p = _make_price(current_price=70, high_52w=120)
        score = score_trend(p, None, config=self.config)
        self.assertLess(score, 45)

    def test_strong_relative_strength_boost(self) -> None:
        p = _make_price(return_6m=0.20)
        b = PriceSnapshot(symbol="SPY", closes=[1], return_6m=0.04)
        score = score_trend(p, b, config=self.config)
        self.assertGreaterEqual(score, 55)

    def test_weak_relative_strength_penalty(self) -> None:
        p = _make_price(
            return_6m=-0.15,
            current_price=100, sma20=105, sma60=105, sma120=105,
            high_52w=105,
        )
        b = PriceSnapshot(symbol="SPY", closes=[1], return_6m=0.04)
        score = score_trend(p, b, config=self.config)
        self.assertLessEqual(score, 50)


# ---------------------------------------------------------------------------
# 位置修正
# ---------------------------------------------------------------------------
class PositionAdjustmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = ScoringConfig.defaults().position

    def test_near_ma_gets_bonus(self) -> None:
        p = _make_price(current_price=110, sma60=110)
        notes: list[str] = []
        adj = score_position_adjustment(p, notes, config=self.config)
        self.assertGreater(adj, 0)
        self.assertIn("near_60d_ma", notes)

    def test_extended_above_gets_penalty(self) -> None:
        p = _make_price(current_price=130, sma60=110)
        notes: list[str] = []
        adj = score_position_adjustment(p, notes, config=self.config)
        self.assertLess(adj, 0)
        self.assertIn("extended_above_60d", notes)

    def test_below_ma_too_far_gets_penalty(self) -> None:
        p = _make_price(current_price=95, sma60=110)
        notes: list[str] = []
        adj = score_position_adjustment(p, notes, config=self.config)
        self.assertLess(adj, 0)
        self.assertIn("below_60d_too_far", notes)

    def test_no_sma60_no_adjustment(self) -> None:
        p = _make_price(sma60=None)
        notes: list[str] = []
        adj = score_position_adjustment(p, notes, config=self.config)
        self.assertEqual(adj, 0)


# ---------------------------------------------------------------------------
# 入场修正
# ---------------------------------------------------------------------------
class EntryPenaltyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = ScoringConfig.defaults()

    def test_weak_quality_penalty(self) -> None:
        p = _make_price()
        f = _make_fundamentals()
        score, _, note = score_stock_entry(
            quality_score=30, valuation_score=60, trend_score=60,
            price=p, fundamentals=f, config=self.config,
        )
        self.assertIn("weak_quality", note)
        self.assertLess(score, 60)

    def test_rich_valuation_penalty_stock(self) -> None:
        p = _make_price()
        f = _make_fundamentals()
        score, _, note = score_stock_entry(
            quality_score=70, valuation_score=30, trend_score=60,
            price=p, fundamentals=f, config=self.config,
        )
        self.assertIn("rich_valuation", note)

    def test_rich_valuation_penalty_etf(self) -> None:
        p = _make_price()
        score, _, note = score_etf_entry(
            valuation_score=30, trend_score=60, price=p, config=self.config,
        )
        self.assertIn("rich_valuation", note)

    def test_earnings_soon_penalty(self) -> None:
        import time
        from datetime import datetime, timezone

        p = _make_price()
        future_ts = int((datetime.now(timezone.utc).timestamp() + 86400 * 7))
        f = _make_fundamentals(earnings_timestamp=future_ts)
        score, _, note = score_stock_entry(
            quality_score=70, valuation_score=60, trend_score=60,
            price=p, fundamentals=f, config=self.config,
        )
        self.assertIn("earnings_soon", note)


# ---------------------------------------------------------------------------
# 底层 helper
# ---------------------------------------------------------------------------
class HelperFunctionTests(unittest.TestCase):
    def test_band_score_good(self) -> None:
        self.assertEqual(band_score(0.15, good=0.08, ok=0.03, bad=-0.05, weight=12), 12)

    def test_band_score_ok(self) -> None:
        self.assertEqual(band_score(0.05, good=0.08, ok=0.03, bad=-0.05, weight=12), 6)

    def test_band_score_bad(self) -> None:
        self.assertEqual(band_score(-0.10, good=0.08, ok=0.03, bad=-0.05, weight=12), -12)

    def test_band_score_none(self) -> None:
        self.assertEqual(band_score(None, good=0.08, ok=0.03, bad=-0.05, weight=12), 0)

    def test_inverse_score_good(self) -> None:
        self.assertEqual(inverse_score(10, good=18, ok=28, bad=45, weight=12), 12)

    def test_inverse_score_bad(self) -> None:
        self.assertEqual(inverse_score(60, good=18, ok=28, bad=45, weight=12), -12)

    def test_inverse_score_none(self) -> None:
        self.assertEqual(inverse_score(None, good=18, ok=28, bad=45, weight=12), 0)

    def test_margin_score_good(self) -> None:
        self.assertEqual(margin_score(0.50, good=0.45, ok=0.30, bad=0.15, weight=8), 8)

    def test_margin_score_bad(self) -> None:
        self.assertEqual(margin_score(0.05, good=0.45, ok=0.30, bad=0.15, weight=8), -8)

    def test_yield_score_good(self) -> None:
        self.assertEqual(yield_score(0.04, good=0.03, ok=0.015, weight=6), 6)

    def test_yield_score_none(self) -> None:
        self.assertEqual(yield_score(None, good=0.03, ok=0.015, weight=6), 0)

    def test_yield_score_ok(self) -> None:
        self.assertEqual(yield_score(0.02, good=0.03, ok=0.015, weight=6), 3)

    def test_cashflow_both_positive(self) -> None:
        self.assertEqual(cashflow_score(100, 200, weight=8), 8)

    def test_cashflow_only_ocf(self) -> None:
        self.assertEqual(cashflow_score(0, 200, weight=8), 4)

    def test_cashflow_both_negative(self) -> None:
        self.assertEqual(cashflow_score(-100, -200, weight=8), -8)

    def test_cashflow_all_none(self) -> None:
        self.assertEqual(cashflow_score(None, None, weight=8), 0)

    def test_clamp_mid(self) -> None:
        self.assertEqual(clamp(55.3), 55)

    def test_clamp_low(self) -> None:
        self.assertEqual(clamp(-5, lower=0, upper=100), 0)

    def test_clamp_high(self) -> None:
        self.assertEqual(clamp(150, lower=0, upper=100), 100)

    def test_relative_strength_positive(self) -> None:
        self.assertAlmostEqual(relative_strength(0.10, 0.04), 0.06)

    def test_relative_strength_no_benchmark(self) -> None:
        self.assertIsNone(relative_strength(0.10, None))

    def test_is_earnings_far_future(self) -> None:
        import time
        far = int(time.time()) + 86400 * 365
        self.assertFalse(is_earnings_soon(far, days=14))

    def test_is_earnings_none(self) -> None:
        self.assertFalse(is_earnings_soon(None, days=14))


# ---------------------------------------------------------------------------
# 自定义配置
# ---------------------------------------------------------------------------
class CustomConfigTests(unittest.TestCase):
    def test_custom_signal_thresholds(self) -> None:
        config = ScoringConfig.defaults()
        config = ScoringConfig(
            a_threshold=90, b_threshold=75, c_threshold=60,
            clamp_lower=config.clamp_lower, clamp_upper=config.clamp_upper,
            quality=config.quality, stock_valuation=config.stock_valuation,
            etf_valuation=config.etf_valuation, trend=config.trend,
            stock_entry=config.stock_entry, etf_entry=config.etf_entry,
            position=config.position,
        )
        f = _make_fundamentals()
        p = _make_price()
        scored = score_ticker(f, p, config=config)
        # 原默认下是 A(>=78)，新阈值下可能降级
        self.assertIn(scored.signal, {"A", "B", "C"})
        self.assertGreaterEqual(scored.entry_score, 50)


if __name__ == "__main__":
    unittest.main()
