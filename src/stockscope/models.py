from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PriceSnapshot:
    symbol: str
    closes: list[float] = field(default_factory=list)
    current_price: float | None = None
    sma20: float | None = None
    sma60: float | None = None
    sma120: float | None = None
    high_52w: float | None = None
    low_52w: float | None = None
    return_6m: float | None = None
    return_1y: float | None = None


@dataclass
class Fundamentals:
    symbol: str
    quote_type: str
    short_name: str | None = None
    sector: str | None = None
    industry: str | None = None
    market_cap: float | None = None
    trailing_pe: float | None = None
    forward_pe: float | None = None
    price_to_sales: float | None = None
    enterprise_to_ebitda: float | None = None
    revenue_growth: float | None = None
    earnings_growth: float | None = None
    gross_margins: float | None = None
    profit_margins: float | None = None
    free_cashflow: float | None = None
    operating_cashflow: float | None = None
    debt_to_equity: float | None = None
    return_on_equity: float | None = None
    return_on_assets: float | None = None
    dividend_yield: float | None = None
    earnings_timestamp: int | None = None


@dataclass
class ScoredTicker:
    symbol: str
    asset_type: str
    short_name: str
    sector: str
    industry: str
    current_price: float | None
    quality_score: int | None
    valuation_score: int | None
    trend_score: int | None
    entry_score: int
    signal: str
    note: str
    distance_to_sma60_pct: float | None
    drawdown_from_high_pct: float | None
    trailing_pe: float | None
    forward_pe: float | None
    price_to_sales: float | None
    enterprise_to_ebitda: float | None
    revenue_growth: float | None
    earnings_growth: float | None
    gross_margins: float | None
    profit_margins: float | None
    debt_to_equity: float | None
    return_on_equity: float | None
    group: str | None = None


# ---------------------------------------------------------------------------
# 评分配置
# ---------------------------------------------------------------------------

@dataclass
class FactorThresholds:
    """单因子阈值（越高越好型 & 越低越好型通用）。"""
    good: float
    ok: float
    bad: float
    weight: int


@dataclass
class YieldThresholds:
    """股息率等收益型因子阈值（无 bad 档）。"""
    good: float
    ok: float
    weight: int


@dataclass
class QualityConfig:
    base: int
    revenue_growth: FactorThresholds
    earnings_growth: FactorThresholds
    gross_margins: FactorThresholds
    profit_margins: FactorThresholds
    return_on_equity: FactorThresholds
    debt_to_equity: FactorThresholds
    cashflow_weight: int


@dataclass
class StockValuationConfig:
    base: int
    trailing_pe: FactorThresholds
    forward_pe: FactorThresholds
    price_to_sales: FactorThresholds
    enterprise_to_ebitda: FactorThresholds


@dataclass
class EtfValuationConfig:
    base: int
    trailing_pe: FactorThresholds
    forward_pe: FactorThresholds
    dividend_yield: YieldThresholds


@dataclass
class TrendConfig:
    base: int
    sma20_bonus: int
    sma60_bonus: int
    sma120_bonus: int
    drawdown_mild_lower: float
    drawdown_mild_upper: float
    drawdown_mild_bonus: int
    drawdown_severe_threshold: float
    drawdown_severe_penalty: int
    rs_strong_threshold: float
    rs_strong_bonus: int
    rs_weak_threshold: float
    rs_weak_penalty: int


@dataclass
class StockEntryConfig:
    valuation_weight: float
    trend_weight: float
    quality_weight: float
    weak_quality_threshold: int
    weak_quality_penalty: int
    rich_valuation_threshold: int
    rich_valuation_penalty: int
    earnings_soon_days: int
    earnings_soon_penalty: int


@dataclass
class EtfEntryConfig:
    valuation_weight: float
    trend_weight: float
    rich_valuation_threshold: int
    rich_valuation_penalty: int


@dataclass
class PositionConfig:
    near_ma_threshold: float
    near_ma_bonus: int
    extended_above_threshold: float
    extended_above_penalty: int
    below_ma_threshold: float
    below_ma_penalty: int


@dataclass
class ScoringConfig:
    """评分策略总配置，所有阈值集中管理。"""
    a_threshold: int
    b_threshold: int
    c_threshold: int
    clamp_lower: int
    clamp_upper: int
    quality: QualityConfig
    stock_valuation: StockValuationConfig
    etf_valuation: EtfValuationConfig
    trend: TrendConfig
    stock_entry: StockEntryConfig
    etf_entry: EtfEntryConfig
    position: PositionConfig

    @classmethod
    def defaults(cls) -> "ScoringConfig":
        """返回与硬编码完全一致的默认配置。"""
        return cls(
            a_threshold=78,
            b_threshold=64,
            c_threshold=50,
            clamp_lower=0,
            clamp_upper=100,
            quality=QualityConfig(
                base=50,
                revenue_growth=FactorThresholds(good=0.08, ok=0.03, bad=-0.05, weight=12),
                earnings_growth=FactorThresholds(good=0.10, ok=0.03, bad=-0.08, weight=12),
                gross_margins=FactorThresholds(good=0.45, ok=0.30, bad=0.15, weight=8),
                profit_margins=FactorThresholds(good=0.18, ok=0.10, bad=0.03, weight=10),
                return_on_equity=FactorThresholds(good=0.15, ok=0.10, bad=0.05, weight=10),
                debt_to_equity=FactorThresholds(good=60.0, ok=120.0, bad=220.0, weight=10),
                cashflow_weight=8,
            ),
            stock_valuation=StockValuationConfig(
                base=50,
                trailing_pe=FactorThresholds(good=18.0, ok=28.0, bad=45.0, weight=12),
                forward_pe=FactorThresholds(good=17.0, ok=24.0, bad=35.0, weight=12),
                price_to_sales=FactorThresholds(good=3.0, ok=6.0, bad=12.0, weight=8),
                enterprise_to_ebitda=FactorThresholds(good=12.0, ok=18.0, bad=30.0, weight=8),
            ),
            etf_valuation=EtfValuationConfig(
                base=50,
                trailing_pe=FactorThresholds(good=18.0, ok=24.0, bad=32.0, weight=12),
                forward_pe=FactorThresholds(good=17.0, ok=22.0, bad=28.0, weight=12),
                dividend_yield=YieldThresholds(good=0.03, ok=0.015, weight=6),
            ),
            trend=TrendConfig(
                base=50,
                sma20_bonus=10,
                sma60_bonus=12,
                sma120_bonus=8,
                drawdown_mild_lower=-0.18,
                drawdown_mild_upper=-0.03,
                drawdown_mild_bonus=8,
                drawdown_severe_threshold=-0.35,
                drawdown_severe_penalty=10,
                rs_strong_threshold=0.05,
                rs_strong_bonus=10,
                rs_weak_threshold=-0.05,
                rs_weak_penalty=8,
            ),
            stock_entry=StockEntryConfig(
                valuation_weight=0.35,
                trend_weight=0.35,
                quality_weight=0.30,
                weak_quality_threshold=45,
                weak_quality_penalty=12,
                rich_valuation_threshold=40,
                rich_valuation_penalty=10,
                earnings_soon_days=14,
                earnings_soon_penalty=6,
            ),
            etf_entry=EtfEntryConfig(
                valuation_weight=0.45,
                trend_weight=0.55,
                rich_valuation_threshold=40,
                rich_valuation_penalty=8,
            ),
            position=PositionConfig(
                near_ma_threshold=0.03,
                near_ma_bonus=8,
                extended_above_threshold=0.12,
                extended_above_penalty=8,
                below_ma_threshold=0.10,
                below_ma_penalty=10,
            ),
        )
