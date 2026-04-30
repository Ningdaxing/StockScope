from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone

from stockscope.models import (
    EtfEntryConfig,
    EtfValuationConfig,
    Fundamentals,
    PositionConfig,
    PriceSnapshot,
    QualityConfig,
    ScoredTicker,
    ScoringConfig,
    StockEntryConfig,
    StockValuationConfig,
    TrendConfig,
)


def score_ticker(
    fundamentals: Fundamentals,
    price: PriceSnapshot,
    benchmark_price: PriceSnapshot | None = None,
    *,
    config: ScoringConfig | None = None,
) -> ScoredTicker:
    """对单个标的执行完整打分并组装最终输出。

    作用：
    - 串联质量分、估值分、趋势分和入场分
    - 生成一条可直接写入报表的结果记录
    """
    if config is None:
        config = ScoringConfig.defaults()

    asset_type = normalize_asset_type(fundamentals.quote_type)
    trend_score = score_trend(price, benchmark_price, config=config.trend)

    if asset_type == "ETF":
        quality_score = None
        valuation_score = score_etf_valuation(fundamentals, config=config.etf_valuation)
        entry_score, signal, note = score_etf_entry(
            valuation_score=valuation_score,
            trend_score=trend_score,
            price=price,
            config=config,
        )
    else:
        quality_score = score_quality(fundamentals, config=config.quality)
        valuation_score = score_stock_valuation(fundamentals, config=config.stock_valuation)
        entry_score, signal, note = score_stock_entry(
            quality_score=quality_score,
            valuation_score=valuation_score,
            trend_score=trend_score,
            price=price,
            fundamentals=fundamentals,
            config=config,
        )

    return ScoredTicker(
        symbol=fundamentals.symbol,
        asset_type=asset_type,
        short_name=fundamentals.short_name or fundamentals.symbol,
        sector=fundamentals.sector or "-",
        industry=fundamentals.industry or "-",
        current_price=price.current_price,
        quality_score=quality_score,
        valuation_score=valuation_score,
        trend_score=trend_score,
        entry_score=entry_score,
        signal=signal,
        note=note,
        distance_to_sma60_pct=_pct_diff(price.current_price, price.sma60),
        drawdown_from_high_pct=_drawdown_from_high(price.current_price, price.high_52w),
        trailing_pe=fundamentals.trailing_pe,
        forward_pe=fundamentals.forward_pe,
        price_to_sales=fundamentals.price_to_sales,
        enterprise_to_ebitda=fundamentals.enterprise_to_ebitda,
        revenue_growth=fundamentals.revenue_growth,
        earnings_growth=fundamentals.earnings_growth,
        gross_margins=fundamentals.gross_margins,
        profit_margins=fundamentals.profit_margins,
        debt_to_equity=fundamentals.debt_to_equity,
        return_on_equity=fundamentals.return_on_equity,
    )


def normalize_asset_type(quote_type: str) -> str:
    """把原始资产类型归一化成项目内部使用的类别。

    作用：
    - 区分股票和 ETF
    - 决定后续该走哪套打分逻辑
    """
    quote_type = quote_type.upper()
    if quote_type in {"ETF", "MUTUALFUND"}:
        return "ETF"
    return "STOCK"


def score_quality(f: Fundamentals, *, config: QualityConfig) -> int:
    """计算个股质量分。

    作用：
    - 评估企业基本面是否健康
    - 重点衡量增长、利润率、负债和现金流表现
    - 用来过滤基本面恶化的公司
    """
    q = config
    score = q.base
    score += band_score(f.revenue_growth, good=q.revenue_growth.good, ok=q.revenue_growth.ok, bad=q.revenue_growth.bad, weight=q.revenue_growth.weight)
    score += band_score(f.earnings_growth, good=q.earnings_growth.good, ok=q.earnings_growth.ok, bad=q.earnings_growth.bad, weight=q.earnings_growth.weight)
    score += margin_score(f.gross_margins, good=q.gross_margins.good, ok=q.gross_margins.ok, bad=q.gross_margins.bad, weight=q.gross_margins.weight)
    score += margin_score(f.profit_margins, good=q.profit_margins.good, ok=q.profit_margins.ok, bad=q.profit_margins.bad, weight=q.profit_margins.weight)
    score += roe_score(f.return_on_equity, good=q.return_on_equity.good, ok=q.return_on_equity.ok, bad=q.return_on_equity.bad, weight=q.return_on_equity.weight)
    score += inverse_score(f.debt_to_equity, good=q.debt_to_equity.good, ok=q.debt_to_equity.ok, bad=q.debt_to_equity.bad, weight=q.debt_to_equity.weight)
    score += cashflow_score(f.free_cashflow, f.operating_cashflow, weight=q.cashflow_weight)
    return clamp(score)


def score_stock_valuation(f: Fundamentals, *, config: StockValuationConfig) -> int:
    """计算个股估值分。

    作用：
    - 评估当前估值是否偏贵
    - 重点参考 PE、预期 PE、PS、EV/EBITDA
    - 用来降低高估值买入的风险
    """
    v = config
    score = v.base
    score += inverse_score(f.trailing_pe, good=v.trailing_pe.good, ok=v.trailing_pe.ok, bad=v.trailing_pe.bad, weight=v.trailing_pe.weight)
    score += inverse_score(f.forward_pe, good=v.forward_pe.good, ok=v.forward_pe.ok, bad=v.forward_pe.bad, weight=v.forward_pe.weight)
    score += inverse_score(f.price_to_sales, good=v.price_to_sales.good, ok=v.price_to_sales.ok, bad=v.price_to_sales.bad, weight=v.price_to_sales.weight)
    score += inverse_score(f.enterprise_to_ebitda, good=v.enterprise_to_ebitda.good, ok=v.enterprise_to_ebitda.ok, bad=v.enterprise_to_ebitda.bad, weight=v.enterprise_to_ebitda.weight)
    return clamp(score)


def score_etf_valuation(f: Fundamentals, *, config: EtfValuationConfig) -> int:
    """计算 ETF 估值分。

    作用：
    - 对 ETF 使用更轻量的估值逻辑
    - 重点参考 PE、预期 PE 和股息率
    """
    v = config
    score = v.base
    score += inverse_score(f.trailing_pe, good=v.trailing_pe.good, ok=v.trailing_pe.ok, bad=v.trailing_pe.bad, weight=v.trailing_pe.weight)
    score += inverse_score(f.forward_pe, good=v.forward_pe.good, ok=v.forward_pe.ok, bad=v.forward_pe.bad, weight=v.forward_pe.weight)
    score += yield_score(f.dividend_yield, good=v.dividend_yield.good, ok=v.dividend_yield.ok, weight=v.dividend_yield.weight)
    return clamp(score)


def score_trend(price: PriceSnapshot, benchmark_price: PriceSnapshot | None, *, config: TrendConfig) -> int:
    """计算趋势分。

    作用：
    - 结合均线位置、回撤幅度和相对强弱判断趋势状态
    - 给最终买点判断补充技术面依据
    """
    t = config
    score = t.base
    if price.current_price and price.sma20 and price.current_price >= price.sma20:
        score += t.sma20_bonus
    if price.current_price and price.sma60 and price.current_price >= price.sma60:
        score += t.sma60_bonus
    if price.current_price and price.sma120 and price.current_price >= price.sma120:
        score += t.sma120_bonus

    drawdown = _drawdown_from_high(price.current_price, price.high_52w)
    if drawdown is not None:
        if t.drawdown_mild_lower <= drawdown <= t.drawdown_mild_upper:
            score += t.drawdown_mild_bonus
        elif drawdown < t.drawdown_severe_threshold:
            score -= t.drawdown_severe_penalty

    rel_strength = relative_strength(price.return_6m, benchmark_price.return_6m if benchmark_price else None)
    if rel_strength is not None:
        if rel_strength > t.rs_strong_threshold:
            score += t.rs_strong_bonus
        elif rel_strength < t.rs_weak_threshold:
            score -= t.rs_weak_penalty
    return clamp(score)


def score_stock_entry(
    *,
    quality_score: int,
    valuation_score: int,
    trend_score: int,
    price: PriceSnapshot,
    fundamentals: Fundamentals,
    config: ScoringConfig,
) -> tuple[int, str, str]:
    """综合生成个股入场分、信号等级和说明标签。

    作用：
    - 按个股逻辑综合估值、趋势、质量三个维度
    - 对财报临近、离均线过远、质量过弱等情况做修正
    - 输出 A/B/C/D 信号供报表展示
    """
    e = config.stock_entry
    score = round((valuation_score * e.valuation_weight) + (trend_score * e.trend_weight) + (quality_score * e.quality_weight))
    notes: list[str] = []
    score += score_position_adjustment(price, notes, config=config.position)

    if quality_score < e.weak_quality_threshold:
        score -= e.weak_quality_penalty
        notes.append("weak_quality")

    if valuation_score < e.rich_valuation_threshold:
        score -= e.rich_valuation_penalty
        notes.append("rich_valuation")

    if is_earnings_soon(fundamentals.earnings_timestamp, days=e.earnings_soon_days):
        score -= e.earnings_soon_penalty
        notes.append("earnings_soon")

    return finalize_signal(score, notes, config=config)


def score_etf_entry(
    *,
    valuation_score: int,
    trend_score: int,
    price: PriceSnapshot,
    config: ScoringConfig,
) -> tuple[int, str, str]:
    """综合生成 ETF 入场分、信号等级和说明标签。

    作用：
    - 让 ETF 不再沿用个股的质量和财报逻辑
    - 更强调估值和趋势两层
    """
    e = config.etf_entry
    score = round((valuation_score * e.valuation_weight) + (trend_score * e.trend_weight))
    notes: list[str] = []
    score += score_position_adjustment(price, notes, config=config.position)

    if valuation_score < e.rich_valuation_threshold:
        score -= e.rich_valuation_penalty
        notes.append("rich_valuation")

    return finalize_signal(score, notes, config=config)


def score_position_adjustment(price: PriceSnapshot, notes: list[str], *, config: PositionConfig) -> int:
    """根据价格相对 60 日线的位置给入场分做修正。

    作用：
    - 提取个股和 ETF 共用的位置判断逻辑
    - 统一"接近均线、离均线过远"的加减分规则
    """
    p = config
    adjustment = 0
    distance = _pct_diff(price.current_price, price.sma60)
    if distance is None:
        return adjustment
    if abs(distance) <= p.near_ma_threshold:
        adjustment += p.near_ma_bonus
        notes.append("near_60d_ma")
    elif distance > p.extended_above_threshold:
        adjustment -= p.extended_above_penalty
        notes.append("extended_above_60d")
    elif distance < -p.below_ma_threshold:
        adjustment -= p.below_ma_penalty
        notes.append("below_60d_too_far")
    return adjustment


def finalize_signal(score: int, notes: list[str], *, config: ScoringConfig) -> tuple[int, str, str]:
    """把原始入场分归一化并映射成信号等级。

    作用：
    - 统一个股和 ETF 的信号阈值
    - 生成最终的 A/B/C/D 信号和说明标签
    """
    score = clamp(score, lower=config.clamp_lower, upper=config.clamp_upper)
    if score >= config.a_threshold:
        signal = "A"
    elif score >= config.b_threshold:
        signal = "B"
    elif score >= config.c_threshold:
        signal = "C"
    else:
        signal = "D"
    note = ",".join(notes) if notes else "balanced"
    return score, signal, note


def band_score(value: float | None, *, good: float, ok: float, bad: float, weight: int) -> int:
    """按分段阈值给"越高越好"的指标打分。

    作用：
    - 适合营收增长、利润增长这类指标
    - 把原始财务值映射成统一分数
    """
    if value is None:
        return 0
    if value >= good:
        return weight
    if value >= ok:
        return round(weight * 0.5)
    if value <= bad:
        return -weight
    return 0


def margin_score(value: float | None, *, good: float, ok: float, bad: float, weight: int) -> int:
    """按阈值给利润率类指标打分。

    作用：
    - 适合毛利率、净利率这类质量指标
    - 把不同量纲的指标统一转成可累加分数
    """
    if value is None:
        return 0
    if value >= good:
        return weight
    if value >= ok:
        return round(weight * 0.5)
    if value <= bad:
        return -weight
    return 0


def roe_score(value: float | None, *, good: float, ok: float, bad: float, weight: int) -> int:
    """对 ROE 复用利润率类打分逻辑。

    作用：
    - 避免重复实现相同阈值判断
    - 让 ROE 的评分口径与其他质量指标保持一致
    """
    return margin_score(value, good=good, ok=ok, bad=bad, weight=weight)


def inverse_score(value: float | None, *, good: float, ok: float, bad: float, weight: int) -> int:
    """按分段阈值给"越低越好"的指标打分。

    作用：
    - 适合 PE、PS、EV/EBITDA、负债等指标
    - 把估值和杠杆风险统一转成分数
    """
    if value is None:
        return 0
    if value <= good:
        return weight
    if value <= ok:
        return round(weight * 0.5)
    if value >= bad:
        return -weight
    return 0


def yield_score(value: float | None, *, good: float, ok: float, weight: int) -> int:
    """给股息率这类收益型指标打分。

    作用：
    - 为 ETF 或高股息标的补充收益维度
    - 在估值判断里加入分红收益参考
    """
    if value is None:
        return 0
    if value >= good:
        return weight
    if value >= ok:
        return round(weight * 0.5)
    return 0


def cashflow_score(fcf: float | None, ocf: float | None, *, weight: int) -> int:
    """根据自由现金流和经营现金流情况打分。

    作用：
    - 判断公司是否具备真实现金创造能力
    - 对利润看起来好但现金流差的公司做约束
    """
    if fcf is None and ocf is None:
        return 0
    if (fcf or 0) > 0 and (ocf or 0) > 0:
        return weight
    if (ocf or 0) > 0:
        return round(weight * 0.5)
    return -weight


def relative_strength(asset_return: float | None, benchmark_return: float | None) -> float | None:
    """计算标的相对基准的强弱表现。

    作用：
    - 判断标的是否跑赢基准指数
    - 为趋势分提供相对强弱信号
    """
    if asset_return is None or benchmark_return is None:
        return None
    return asset_return - benchmark_return


def is_earnings_soon(timestamp: int | None, *, days: int) -> bool:
    """判断标的是否临近财报日期。

    作用：
    - 在财报前对入场分做风险折扣
    - 避免在短期不确定性较高的时间点盲目入场
    """
    if not timestamp:
        return False
    event_date = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    now = datetime.now(timezone.utc)
    delta_days = (event_date - now).days
    return 0 <= delta_days <= days


def clamp(value: float, *, lower: int = 0, upper: int = 100) -> int:
    """把分数限制在指定区间内。

    作用：
    - 防止多项规则叠加后超出 0 到 100 的范围
    - 保证所有分数口径一致
    """
    return max(lower, min(upper, round(value)))


def _pct_diff(current: float | None, moving_average: float | None) -> float | None:
    """计算当前价格相对均线的偏离比例。

    作用：
    - 判断价格是否贴近均线
    - 为趋势分析和买点判断提供依据
    """
    if current is None or moving_average in (None, 0):
        return None
    return (current / moving_average) - 1


def _drawdown_from_high(current: float | None, high_52w: float | None) -> float | None:
    """计算当前价格相对 52 周高点的回撤幅度。

    作用：
    - 区分温和回撤和趋势破坏
    - 为趋势分和买点判断提供参考
    """
    if current is None or high_52w in (None, 0):
        return None
    return (current / high_52w) - 1
