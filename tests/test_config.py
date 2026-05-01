from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from stockscope.config import (
    get_symbol_to_group_map,
    load_benchmark,
    load_groups,
    load_name_overrides,
    load_scoring_config,
    load_watchlist,
)


def _write_toml(content: str) -> str:
    """写入临时 TOML 文件并返回路径。"""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False, encoding="utf-8")
    tmp.write(content)
    tmp.close()
    return tmp.name


class WatchlistTests(unittest.TestCase):
    def test_load_watchlist_from_groups_and_manual(self) -> None:
        path = _write_toml("""\
[groups]
tech = ["AAPL", "MSFT"]
etfs = ["SPY"]

[tickers]
manual = ["BABA", "TSLA"]
""")
        symbols = load_watchlist(path)
        self.assertEqual(symbols, ["AAPL", "MSFT", "SPY", "BABA", "TSLA"])

    def test_load_watchlist_deduplicates(self) -> None:
        path = _write_toml("""\
[groups]
a = ["AAPL", "MSFT"]
b = ["AAPL"]
""")
        symbols = load_watchlist(path)
        self.assertEqual(symbols, ["AAPL", "MSFT"])

    def test_load_watchlist_lowercase_normalized(self) -> None:
        path = _write_toml("""\
[groups]
a = ["aapl", "Msft"]
""")
        symbols = load_watchlist(path)
        self.assertEqual(symbols, ["AAPL", "MSFT"])

    def test_load_watchlist_empty_config(self) -> None:
        path = _write_toml("")
        symbols = load_watchlist(path)
        self.assertEqual(symbols, [])


class NameOverridesTests(unittest.TestCase):
    def test_load_name_overrides(self) -> None:
        path = _write_toml("""\
[name_overrides]
KO = "可口可乐"
TSM = "台积电"
""")
        overrides = load_name_overrides(path)
        self.assertEqual(overrides["KO"], "可口可乐")
        self.assertEqual(overrides["TSM"], "台积电")

    def test_load_aliases_fallback(self) -> None:
        path = _write_toml("""\
[aliases]
KO = "可乐"
""")
        overrides = load_name_overrides(path)
        self.assertEqual(overrides["KO"], "可乐")

    def test_name_overrides_priority_over_aliases(self) -> None:
        path = _write_toml("""\
[name_overrides]
KO = "可口可乐"

[aliases]
KO = "可乐"
""")
        overrides = load_name_overrides(path)
        self.assertEqual(overrides["KO"], "可口可乐")

    def test_empty_name_overrides(self) -> None:
        path = _write_toml("")
        overrides = load_name_overrides(path)
        self.assertEqual(overrides, {})


class GroupsTests(unittest.TestCase):
    def test_load_groups(self) -> None:
        path = _write_toml("""\
[groups]
tech = ["AAPL", "MSFT"]
etfs = ["SPY", "QQQ"]
""")
        groups = load_groups(path)
        self.assertEqual(groups["tech"], ["AAPL", "MSFT"])
        self.assertEqual(groups["etfs"], ["SPY", "QQQ"])

    def test_load_groups_empty(self) -> None:
        path = _write_toml("")
        groups = load_groups(path)
        self.assertEqual(groups, {})


class BenchmarkTests(unittest.TestCase):
    def test_load_benchmark_custom(self) -> None:
        path = _write_toml("""\
[defaults]
benchmark = "QQQ"
""")
        self.assertEqual(load_benchmark(path), "QQQ")

    def test_load_benchmark_default(self) -> None:
        path = _write_toml("")
        self.assertEqual(load_benchmark(path), "SPY")


class SymbolToGroupMapTests(unittest.TestCase):
    def test_first_group_wins(self) -> None:
        path = _write_toml("""\
[groups]
a = ["AAPL", "MSFT"]
b = ["AAPL", "GOOGL"]
""")
        mapping = get_symbol_to_group_map(path)
        self.assertEqual(mapping["AAPL"], "a")
        self.assertEqual(mapping["MSFT"], "a")
        self.assertEqual(mapping["GOOGL"], "b")


class ScoringConfigTests(unittest.TestCase):
    def test_missing_file_returns_defaults(self) -> None:
        config = load_scoring_config("nonexistent.toml")
        self.assertEqual(config.a_threshold, 78)
        self.assertEqual(config.quality.base, 50)

    def test_partial_override_preserves_other_defaults(self) -> None:
        path = _write_toml("""\
[signals]
a_threshold = 85
""")
        config = load_scoring_config(path)
        self.assertEqual(config.a_threshold, 85)
        self.assertEqual(config.b_threshold, 64)  # unchanged
        self.assertEqual(config.quality.base, 50)  # unchanged

    def test_full_custom_config_loads(self) -> None:
        path = _write_toml("""\
[signals]
a_threshold = 90
b_threshold = 75
c_threshold = 60

[clamp]
lower = 5
upper = 95

[quality]
base = 55
""")
        config = load_scoring_config(path)
        self.assertEqual(config.a_threshold, 90)
        self.assertEqual(config.b_threshold, 75)
        self.assertEqual(config.c_threshold, 60)
        self.assertEqual(config.clamp_lower, 5)
        self.assertEqual(config.clamp_upper, 95)
        self.assertEqual(config.quality.base, 55)

    def test_nested_factor_override(self) -> None:
        path = _write_toml("""\
[quality.revenue_growth]
good = 0.10
weight = 15
""")
        config = load_scoring_config(path)
        self.assertEqual(config.quality.revenue_growth.good, 0.10)
        self.assertEqual(config.quality.revenue_growth.weight, 15)
        # unchanged nested fields
        self.assertEqual(config.quality.revenue_growth.ok, 0.03)
        self.assertEqual(config.quality.revenue_growth.bad, -0.05)


if __name__ == "__main__":
    unittest.main()
