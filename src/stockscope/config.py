from __future__ import annotations

from pathlib import Path
import tomllib

from stockscope.models import (
    EtfEntryConfig,
    EtfValuationConfig,
    FactorThresholds,
    PositionConfig,
    QualityConfig,
    ScoringConfig,
    StockEntryConfig,
    StockValuationConfig,
    TrendConfig,
    YieldThresholds,
)


def load_raw_config(path: str | Path) -> dict:
    """读取并返回原始 TOML 配置。

    作用：
    - 统一处理配置文件读取
    - 给观察池、名称覆盖等不同读取逻辑复用
    """
    return tomllib.loads(Path(path).read_text())


def load_watchlist(path: str | Path) -> list[str]:
    """读取观察池配置并返回去重后的 ticker 列表。

    作用：
    - 从 TOML 文件中收集分组里的标的
    - 合并手动补充的标的
    - 统一转成大写并做去重
    """
    raw = load_raw_config(path)
    symbols: list[str] = []
    groups = raw.get("groups", {})
    for values in groups.values():
        symbols.extend(values)
    symbols.extend(raw.get("tickers", {}).get("manual", []))
    deduped: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        normalized = symbol.strip().upper()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def load_name_overrides(path: str | Path) -> dict[str, str]:
    """读取 ticker 到名称覆盖值的映射表。

    作用：
    - 从配置文件里加载少量人工名称覆盖
    - 兼容旧版 `aliases` 字段，避免升级时直接报错
    """
    raw = load_raw_config(path)
    overrides = raw.get("name_overrides", {}) or raw.get("aliases", {})
    normalized: dict[str, str] = {}
    for symbol, name in overrides.items():
        key = str(symbol).strip().upper()
        value = str(name).strip()
        if key and value:
            normalized[key] = value
    return normalized


def load_groups(path: str | Path) -> dict[str, list[str]]:
    """读取分组配置，返回 group_name -> symbols 的映射。

    作用：
    - 按配置中的 [groups] 组织标的
    - 用于报表生成分组视图
    """
    raw = load_raw_config(path)
    groups = raw.get("groups", {})
    normalized: dict[str, list[str]] = {}
    for group_name, symbols in groups.items():
        normalized[group_name] = [str(s).strip().upper() for s in symbols]
    return normalized


def load_benchmark(path: str | Path) -> str:
    """读取默认基准指数配置。

    作用：
    - 从 [defaults] 段读取 benchmark 字段
    - 未配置时回退到 SPY
    """
    raw = load_raw_config(path)
    defaults = raw.get("defaults", {})
    benchmark = defaults.get("benchmark", "SPY")
    return str(benchmark).strip().upper()


def get_symbol_to_group_map(path: str | Path) -> dict[str, str]:
    """返回 symbol -> group_name 的反向映射。

    作用：
    - 每个标的归属到其第一个出现的分组
    - 用于给 ScoredTicker 标记所属分组
    """
    groups = load_groups(path)
    symbol_to_group: dict[str, str] = {}
    for group_name, symbols in groups.items():
        for symbol in symbols:
            if symbol not in symbol_to_group:
                symbol_to_group[symbol] = group_name
    return symbol_to_group


def _merge_factor(defaults: FactorThresholds, overrides: dict | None) -> FactorThresholds:
    """合并单个因子阈值，未配置的键沿用默认值。"""
    if not overrides:
        return defaults
    return FactorThresholds(
        good=overrides.get("good", defaults.good),
        ok=overrides.get("ok", defaults.ok),
        bad=overrides.get("bad", defaults.bad),
        weight=overrides.get("weight", defaults.weight),
    )


def _merge_yield(defaults: YieldThresholds, overrides: dict | None) -> YieldThresholds:
    """合并股息率等收益型因子阈值。"""
    if not overrides:
        return defaults
    return YieldThresholds(
        good=overrides.get("good", defaults.good),
        ok=overrides.get("ok", defaults.ok),
        weight=overrides.get("weight", defaults.weight),
    )


def load_scoring_config(path: str | Path = "config/scoring.toml") -> ScoringConfig:
    """加载评分配置，未配置或文件缺失时使用默认值。

    作用：
    - 从独立 TOML 文件读取评分阈值
    - 与 ScoringConfig.defaults() 做逐层合并
    - 用户只需在配置文件中写要改的项
    """
    defaults = ScoringConfig.defaults()
    try:
        raw = load_raw_config(path)
    except (FileNotFoundError, OSError):
        return defaults

    # 信号等级
    sig = raw.get("signals", {})
    a_threshold = sig.get("a_threshold", defaults.a_threshold)
    b_threshold = sig.get("b_threshold", defaults.b_threshold)
    c_threshold = sig.get("c_threshold", defaults.c_threshold)

    # 裁剪
    clamp_cfg = raw.get("clamp", {})
    clamp_lower = clamp_cfg.get("lower", defaults.clamp_lower)
    clamp_upper = clamp_cfg.get("upper", defaults.clamp_upper)

    # 质量分
    q = raw.get("quality", {})
    quality = QualityConfig(
        base=q.get("base", defaults.quality.base),
        revenue_growth=_merge_factor(defaults.quality.revenue_growth, q.get("revenue_growth")),
        earnings_growth=_merge_factor(defaults.quality.earnings_growth, q.get("earnings_growth")),
        gross_margins=_merge_factor(defaults.quality.gross_margins, q.get("gross_margins")),
        profit_margins=_merge_factor(defaults.quality.profit_margins, q.get("profit_margins")),
        return_on_equity=_merge_factor(defaults.quality.return_on_equity, q.get("return_on_equity")),
        debt_to_equity=_merge_factor(defaults.quality.debt_to_equity, q.get("debt_to_equity")),
        cashflow_weight=q.get("cashflow", {}).get("weight", defaults.quality.cashflow_weight),
    )

    # 个股估值
    sv = raw.get("stock_valuation", {})
    stock_valuation = StockValuationConfig(
        base=sv.get("base", defaults.stock_valuation.base),
        trailing_pe=_merge_factor(defaults.stock_valuation.trailing_pe, sv.get("trailing_pe")),
        forward_pe=_merge_factor(defaults.stock_valuation.forward_pe, sv.get("forward_pe")),
        price_to_sales=_merge_factor(defaults.stock_valuation.price_to_sales, sv.get("price_to_sales")),
        enterprise_to_ebitda=_merge_factor(defaults.stock_valuation.enterprise_to_ebitda, sv.get("enterprise_to_ebitda")),
    )

    # ETF 估值
    ev = raw.get("etf_valuation", {})
    etf_valuation = EtfValuationConfig(
        base=ev.get("base", defaults.etf_valuation.base),
        trailing_pe=_merge_factor(defaults.etf_valuation.trailing_pe, ev.get("trailing_pe")),
        forward_pe=_merge_factor(defaults.etf_valuation.forward_pe, ev.get("forward_pe")),
        dividend_yield=_merge_yield(defaults.etf_valuation.dividend_yield, ev.get("dividend_yield")),
    )

    # 趋势
    t = raw.get("trend", {})
    dd = t.get("drawdown", {})
    rs = t.get("relative_strength", {})
    trend = TrendConfig(
        base=t.get("base", defaults.trend.base),
        sma20_bonus=t.get("sma20_bonus", defaults.trend.sma20_bonus),
        sma60_bonus=t.get("sma60_bonus", defaults.trend.sma60_bonus),
        sma120_bonus=t.get("sma120_bonus", defaults.trend.sma120_bonus),
        drawdown_mild_lower=dd.get("mild_lower", defaults.trend.drawdown_mild_lower),
        drawdown_mild_upper=dd.get("mild_upper", defaults.trend.drawdown_mild_upper),
        drawdown_mild_bonus=dd.get("mild_bonus", defaults.trend.drawdown_mild_bonus),
        drawdown_severe_threshold=dd.get("severe_threshold", defaults.trend.drawdown_severe_threshold),
        drawdown_severe_penalty=dd.get("severe_penalty", defaults.trend.drawdown_severe_penalty),
        rs_strong_threshold=rs.get("strong_threshold", defaults.trend.rs_strong_threshold),
        rs_strong_bonus=rs.get("strong_bonus", defaults.trend.rs_strong_bonus),
        rs_weak_threshold=rs.get("weak_threshold", defaults.trend.rs_weak_threshold),
        rs_weak_penalty=rs.get("weak_penalty", defaults.trend.rs_weak_penalty),
    )

    # 个股入场
    se = raw.get("stock_entry", {})
    wq = se.get("weak_quality", {})
    rv = se.get("rich_valuation", {})
    es = se.get("earnings_soon", {})
    stock_entry = StockEntryConfig(
        valuation_weight=se.get("valuation_weight", defaults.stock_entry.valuation_weight),
        trend_weight=se.get("trend_weight", defaults.stock_entry.trend_weight),
        quality_weight=se.get("quality_weight", defaults.stock_entry.quality_weight),
        weak_quality_threshold=wq.get("threshold", defaults.stock_entry.weak_quality_threshold),
        weak_quality_penalty=wq.get("penalty", defaults.stock_entry.weak_quality_penalty),
        rich_valuation_threshold=rv.get("threshold", defaults.stock_entry.rich_valuation_threshold),
        rich_valuation_penalty=rv.get("penalty", defaults.stock_entry.rich_valuation_penalty),
        earnings_soon_days=es.get("days", defaults.stock_entry.earnings_soon_days),
        earnings_soon_penalty=es.get("penalty", defaults.stock_entry.earnings_soon_penalty),
    )

    # ETF 入场
    ee = raw.get("etf_entry", {})
    erv = ee.get("rich_valuation", {})
    etf_entry = EtfEntryConfig(
        valuation_weight=ee.get("valuation_weight", defaults.etf_entry.valuation_weight),
        trend_weight=ee.get("trend_weight", defaults.etf_entry.trend_weight),
        rich_valuation_threshold=erv.get("threshold", defaults.etf_entry.rich_valuation_threshold),
        rich_valuation_penalty=erv.get("penalty", defaults.etf_entry.rich_valuation_penalty),
    )

    # 位置修正
    pos = raw.get("position", {})
    position = PositionConfig(
        near_ma_threshold=pos.get("near_ma_threshold", defaults.position.near_ma_threshold),
        near_ma_bonus=pos.get("near_ma_bonus", defaults.position.near_ma_bonus),
        extended_above_threshold=pos.get("extended_above_threshold", defaults.position.extended_above_threshold),
        extended_above_penalty=pos.get("extended_above_penalty", defaults.position.extended_above_penalty),
        below_ma_threshold=pos.get("below_ma_threshold", defaults.position.below_ma_threshold),
        below_ma_penalty=pos.get("below_ma_penalty", defaults.position.below_ma_penalty),
    )

    return ScoringConfig(
        a_threshold=a_threshold,
        b_threshold=b_threshold,
        c_threshold=c_threshold,
        clamp_lower=clamp_lower,
        clamp_upper=clamp_upper,
        quality=quality,
        stock_valuation=stock_valuation,
        etf_valuation=etf_valuation,
        trend=trend,
        stock_entry=stock_entry,
        etf_entry=etf_entry,
        position=position,
    )
