from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from stockscope.models import ScoredTicker
from stockscope.reports import print_terminal_summary, write_csv, write_dashboard


def _make_item(
    symbol: str = "AAPL",
    asset_type: str = "STOCK",
    entry_score: int = 80,
    valuation_score: int = 65,
    trend_score: int = 70,
    quality_score: int = 85,
    signal: str = "A",
    note: str = "balanced",
    **overrides,
) -> ScoredTicker:
    """构建一条测试用的评分结果。"""
    defaults = dict(
        symbol=symbol,
        asset_type=asset_type,
        short_name="Apple Inc",
        sector="Technology",
        industry="Consumer Electronics",
        current_price=150.0,
        quality_score=quality_score if asset_type == "STOCK" else None,
        valuation_score=valuation_score,
        trend_score=trend_score,
        entry_score=entry_score,
        signal=signal,
        note=note,
        distance_to_sma60_pct=0.01,
        drawdown_from_high_pct=-0.05,
        trailing_pe=25.0,
        forward_pe=22.0,
        price_to_sales=5.0,
        enterprise_to_ebitda=15.0,
        revenue_growth=0.10,
        earnings_growth=0.12,
        gross_margins=0.45,
        profit_margins=0.20,
        debt_to_equity=50.0,
        return_on_equity=0.18,
    )
    defaults.update(overrides)
    return ScoredTicker(**{k: v for k, v in defaults.items() if k in {f.name for f in ScoredTicker.__dataclass_fields__.values()}})  # type: ignore[arg-type]


class CsvOutputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.output = Path(self.tmpdir.name) / "signals.csv"

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_write_csv_creates_file(self) -> None:
        items = [_make_item(), _make_item(symbol="MSFT")]
        write_csv(items, self.output)
        self.assertTrue(self.output.exists())

    def test_write_csv_has_header_and_rows(self) -> None:
        items = [_make_item(), _make_item(symbol="MSFT")]
        write_csv(items, self.output)
        with self.output.open(encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
        self.assertEqual(len(reader), 2)
        self.assertIn("symbol", reader[0])
        self.assertEqual(reader[0]["symbol"], "AAPL")
        self.assertEqual(reader[1]["symbol"], "MSFT")

    def test_write_csv_empty_list_ok(self) -> None:
        write_csv([], self.output)
        self.assertTrue(self.output.exists())


class DashboardOutputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.output = Path(self.tmpdir.name) / "dashboard.html"

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_write_dashboard_creates_html(self) -> None:
        items = [_make_item(symbol="AAPL"), _make_item(symbol="MSFT")]
        write_dashboard(items, self.output)
        content = self.output.read_text(encoding="utf-8")
        self.assertIn("<!doctype html>", content)
        self.assertIn("AAPL", content)
        self.assertIn("MSFT", content)

    def test_write_dashboard_contains_signal(self) -> None:
        items = [_make_item(signal="A")]
        write_dashboard(items, self.output)
        content = self.output.read_text(encoding="utf-8")
        self.assertIn("A", content)

    def test_write_dashboard_includes_etf_quality_placeholder(self) -> None:
        items = [_make_item(symbol="SPY", asset_type="ETF", quality_score=None)]
        write_dashboard(items, self.output)
        content = self.output.read_text(encoding="utf-8")
        self.assertIn("SPY", content)

    def test_write_dashboard_empty_list_ok(self) -> None:
        write_dashboard([], self.output)
        self.assertTrue(self.output.exists())


class TerminalSummaryTests(unittest.TestCase):
    def test_print_terminal_summary_returns_string(self) -> None:
        items = [_make_item(symbol="AAPL")]
        output = print_terminal_summary(items, limit=10)
        self.assertIsInstance(output, str)
        self.assertIn("AAPL", output)

    def test_print_terminal_summary_respects_limit(self) -> None:
        items = [_make_item() for _ in range(20)]
        output = print_terminal_summary(items, limit=5)
        lines = output.strip().split("\n")
        # 2 lines of header + separator + 5 data rows = 8
        data_rows = [l for l in lines if l and not l.startswith("代码") and not l.startswith("---")]
        self.assertLessEqual(len(data_rows), 5)

    def test_print_terminal_summary_empty(self) -> None:
        output = print_terminal_summary([], limit=10)
        self.assertIn("代码", output)
        self.assertNotIn("AAPL", output)

    def test_print_terminal_summary_chinese_labels(self) -> None:
        items = [_make_item(note="near_60d_ma")]
        output = print_terminal_summary(items, limit=10)
        self.assertIn("接近60日线", output)  # note is translated

    def test_print_terminal_summary_etf_quality_dash(self) -> None:
        items = [_make_item(symbol="SPY", asset_type="ETF", quality_score=None)]
        output = print_terminal_summary(items, limit=10)
        self.assertIn("-", output)


if __name__ == "__main__":
    unittest.main()
