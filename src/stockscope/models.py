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
