from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone

from stockscope.models import (
    BreakdownCollector,
    EtfEntryConfig,
    EtfValuationConfig,
    Fundamentals,
    PositionConfig,
    PriceSnapshot,
    QualityConfig,
    ScoreBreakdown,
    ScoredTicker,
    ScoringConfig,
    StockEntryConfig,
    StockValuationConfig,
    TrendConfig,
)


def _fmt_v(value: float | None, *, is_pct: bool = False) -> str:
    """格式化数值用于拆解展示。"""
    if value is None:
        return "-"
    if is_pct:
        return f"{value:.1%}"
    return f"{value:.2f}"


def _higher_detail(value: float | None, good: float, ok: float, bad: float, weight: int) -> tuple[int, str]:
    """越高越好型因子的得分与说明。"""
    if value is None:
        return 0, "无数据 → 0"
    if value >= good:
        return weight, f"{_fmt_v(value, is_pct=True)} ≥ {_fmt_v(good, is_pct=True)} → +{weight}"
    if value >= ok:
        return round(weight * 0.5), f"{_fmt_v(ok, is_pct=True)} ≤ {_fmt_v(value, is_pct=True)} < {_fmt_v(good, is_pct=True)} → +{round(weight * 0.5)}"
    if value <= bad:
        return -weight, f"{_fmt_v(value, is_pct=True)} ≤ {_fmt_v(bad, is_pct=True)} → { -weight}"
    return 0, f"{_fmt_v(bad, is_pct=True)} < {_fmt_v(value, is_pct=True)} < {_fmt_v(ok, is_pct=True)} → 0"


def _lower_detail(value: float | None, good: float, ok: float, bad: float, weight: int) -> tuple[int, str]:
    """越低越好型因子的得分与说明。"""
    if value is None:
        return 0, "无数据 → 0"
    if value <= good:
        return weight, f"{_fmt_v(value)} ≤ {_fmt_v(good)} → +{weight}"
    if value <= ok:
        return round(weight * 0.5), f"{_fmt_v(good)} < {_fmt_v(value)} ≤ {_fmt_v(ok)} → +{round(weight * 0.5)}"
    if value >= bad:
        return -weight, f"{_fmt_v(value)} ≥ {_fmt_v(bad)} → { -weight}"
    return 0, f"{_fmt_v(ok)} < {_fmt_v(value)} < {_fmt_v(bad)} → 0"


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

    collector = BreakdownCollector()
    asset_type = normalize_asset_type(fundamentals.quote_type)
    trend_score = score_trend(price, benchmark_price, config=config.trend, collector=collector)

    if asset_type == "ETF":
        quality_score = None
        valuation_score = score_etf_valuation(fundamentals, config=config.etf_valuation, collector=collector)
        entry_score, signal, note, entry_formula = score_etf_entry(
            valuation_score=valuation_score,
            trend_score=trend_score,
            price=price,
            config=config,
            collector=collector,
        )
        breakdown = ScoreBreakdown(
            quality_base=0,
            valuation_base=config.etf_valuation.base,
            valuation_items=collector.by_category("valuation"),
            trend_base=config.trend.base,
            trend_items=collector.by_category("trend"),
            entry_formula=entry_formula,
            adjustments=collector.by_category("adjustment"),
        )
    else:
        quality_score = score_quality(fundamentals, config=config.quality, collector=collector)
        valuation_score = score_stock_valuation(fundamentals, config=config.stock_valuation, collector=collector)
        entry_score, signal, note, entry_formula = score_stock_entry(
            quality_score=quality_score,
            valuation_score=valuation_score,
            trend_score=trend_score,
            price=price,
            fundamentals=fundamentals,
            config=config,
            collector=collector,
        )
        breakdown = ScoreBreakdown(
            quality_base=config.quality.base,
            quality_items=collector.by_category("quality"),
            valuation_base=config.stock_valuation.base,
            valuation_items=collector.by_category("valuation"),
            trend_base=config.trend.base,
            trend_items=collector.by_category("trend"),
            entry_formula=entry_formula,
            adjustments=collector.by_category("adjustment"),
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
        breakdown=breakdown,
        data_date=price.last_date,
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


def score_quality(f: Fundamentals, *, config: QualityConfig, collector: BreakdownCollector | None = None) -> int:
    """计算个股质量分。"""
    q = config
    score = q.base

    pct_factors = [
        ("营收增长", f.revenue_growth, q.revenue_growth, "band"),
        ("盈利增长", f.earnings_growth, q.earnings_growth, "band"),
        ("毛利率", f.gross_margins, q.gross_margins, "margin"),
        ("净利率", f.profit_margins, q.profit_margins, "margin"),
        ("ROE", f.return_on_equity, q.return_on_equity, "margin"),
    ]
    for label, value, thresh, kind in pct_factors:
        if kind == "inverse":
            s, detail = _lower_detail(value, thresh.good, thresh.ok, thresh.bad, thresh.weight)
        else:
            s, detail = _higher_detail(value, thresh.good, thresh.ok, thresh.bad, thresh.weight)
        score += s
        if collector:
            collector.add(factor=label, value=_fmt_v(value, is_pct=True), score=s, detail=detail, category="quality")

    # 负债权益比（比值，非百分比）
    de = f.debt_to_equity
    de_s, de_detail = _lower_detail(de, q.debt_to_equity.good, q.debt_to_equity.ok, q.debt_to_equity.bad, q.debt_to_equity.weight)
    score += de_s
    if collector:
        collector.add(factor="负债权益比", value=_fmt_v(de), score=de_s, detail=de_detail, category="quality")

    # 现金流特殊处理
    cf_score = cashflow_score(f.free_cashflow, f.operating_cashflow, weight=q.cashflow_weight)
    score += cf_score
    if collector:
        if f.free_cashflow is None and f.operating_cashflow is None:
            cf_detail = "无数据 → 0"
        elif (f.free_cashflow or 0) > 0 and (f.operating_cashflow or 0) > 0:
            cf_detail = f"FCF>0 且 OCF>0 → +{q.cashflow_weight}"
        elif (f.operating_cashflow or 0) > 0:
            cf_detail = f"FCF≤0 但 OCF>0 → +{round(q.cashflow_weight * 0.5)}"
        else:
            cf_detail = f"FCF≤0 且 OCF≤0 → { -q.cashflow_weight}"
        collector.add(factor="现金流", value=f"FCF={_fmt_v(f.free_cashflow)} OCF={_fmt_v(f.operating_cashflow)}", score=cf_score, detail=cf_detail, category="quality")

    return clamp(score)


def score_stock_valuation(f: Fundamentals, *, config: StockValuationConfig, collector: BreakdownCollector | None = None) -> int:
    """计算个股估值分。"""
    v = config
    score = v.base

    factors = [
        ("Trailing PE", f.trailing_pe, v.trailing_pe),
        ("Forward PE", f.forward_pe, v.forward_pe),
        ("PS(TTM)", f.price_to_sales, v.price_to_sales),
        ("EV/EBITDA", f.enterprise_to_ebitda, v.enterprise_to_ebitda),
    ]
    for label, value, thresh in factors:
        s, detail = _lower_detail(value, thresh.good, thresh.ok, thresh.bad, thresh.weight)
        score += s
        if collector:
            collector.add(factor=label, value=_fmt_v(value), score=s, detail=detail, category="valuation")

    return clamp(score)


def score_etf_valuation(f: Fundamentals, *, config: EtfValuationConfig, collector: BreakdownCollector | None = None) -> int:
    """计算 ETF 估值分。"""
    v = config
    score = v.base

    for label, value, thresh in [
        ("Trailing PE", f.trailing_pe, v.trailing_pe),
        ("Forward PE", f.forward_pe, v.forward_pe),
    ]:
        s, detail = _lower_detail(value, thresh.good, thresh.ok, thresh.bad, thresh.weight)
        score += s
        if collector:
            collector.add(factor=label, value=_fmt_v(value), score=s, detail=detail, category="valuation")

    dy_score = yield_score(f.dividend_yield, good=v.dividend_yield.good, ok=v.dividend_yield.ok, weight=v.dividend_yield.weight)
    score += dy_score
    if collector:
        if f.dividend_yield is None:
            dy_detail = "无数据 → 0"
        elif f.dividend_yield >= v.dividend_yield.good:
            dy_detail = f"{_fmt_v(f.dividend_yield, is_pct=True)} ≥ {_fmt_v(v.dividend_yield.good, is_pct=True)} → +{v.dividend_yield.weight}"
        elif f.dividend_yield >= v.dividend_yield.ok:
            dy_detail = f"{_fmt_v(v.dividend_yield.ok, is_pct=True)} ≤ {_fmt_v(f.dividend_yield, is_pct=True)} < {_fmt_v(v.dividend_yield.good, is_pct=True)} → +{round(v.dividend_yield.weight * 0.5)}"
        else:
            dy_detail = f"{_fmt_v(f.dividend_yield, is_pct=True)} < {_fmt_v(v.dividend_yield.ok, is_pct=True)} → 0"
        collector.add(factor="股息率", value=_fmt_v(f.dividend_yield, is_pct=True), score=dy_score, detail=dy_detail, category="valuation")

    return clamp(score)


def score_trend(price: PriceSnapshot, benchmark_price: PriceSnapshot | None, *, config: TrendConfig, collector: BreakdownCollector | None = None) -> int:
    """计算趋势分。"""
    t = config
    score = t.base

    # 均线位置
    trade_date = f"({price.last_date})" if price.last_date else ""
    sma_checks = [
        ("20日线", price.current_price, price.sma20, t.sma20_bonus),
        ("60日线", price.current_price, price.sma60, t.sma60_bonus),
        ("120日线", price.current_price, price.sma120, t.sma120_bonus),
    ]
    for label, cp, ma, bonus in sma_checks:
        if cp and ma and cp >= ma:
            score += bonus
            if collector:
                collector.add(factor=f"站上{label}", value=f"现价{trade_date} {_fmt_v(cp)} ≥ MA{_fmt_v(ma)}", score=bonus, detail=f"现价{trade_date} ≥ {label} → +{bonus}", category="trend")

    # 回撤
    drawdown = _drawdown_from_high(price.current_price, price.high_52w)
    if drawdown is not None:
        if t.drawdown_mild_lower <= drawdown <= t.drawdown_mild_upper:
            score += t.drawdown_mild_bonus
            if collector:
                collector.add(factor="温和回撤", value=f"{_fmt_v(drawdown, is_pct=True)}{trade_date}", score=t.drawdown_mild_bonus,
                              detail=f"{_fmt_v(t.drawdown_mild_lower, is_pct=True)} ≤ 回撤{trade_date} ≤ {_fmt_v(t.drawdown_mild_upper, is_pct=True)} → +{t.drawdown_mild_bonus}", category="trend")
        elif drawdown < t.drawdown_severe_threshold:
            score -= t.drawdown_severe_penalty
            if collector:
                collector.add(factor="严重回撤", value=f"{_fmt_v(drawdown, is_pct=True)}{trade_date}", score=-t.drawdown_severe_penalty,
                              detail=f"回撤{trade_date} < {_fmt_v(t.drawdown_severe_threshold, is_pct=True)} → { -t.drawdown_severe_penalty}", category="trend")

    # 相对强度
    rel_strength = relative_strength(price.return_6m, benchmark_price.return_6m if benchmark_price else None)
    if rel_strength is not None:
        if rel_strength > t.rs_strong_threshold:
            score += t.rs_strong_bonus
            if collector:
                collector.add(factor="相对强势", value=f"{_fmt_v(rel_strength, is_pct=True)}{trade_date}", score=t.rs_strong_bonus,
                              detail=f"相对强度(6m){trade_date} > {_fmt_v(t.rs_strong_threshold, is_pct=True)} → +{t.rs_strong_bonus}", category="trend")
        elif rel_strength < t.rs_weak_threshold:
            score -= t.rs_weak_penalty
            if collector:
                collector.add(factor="相对弱势", value=f"{_fmt_v(rel_strength, is_pct=True)}{trade_date}", score=-t.rs_weak_penalty,
                              detail=f"相对强度(6m){trade_date} < {_fmt_v(t.rs_weak_threshold, is_pct=True)} → { -t.rs_weak_penalty}", category="trend")

    return clamp(score)


def score_stock_entry(
    *,
    quality_score: int,
    valuation_score: int,
    trend_score: int,
    price: PriceSnapshot,
    fundamentals: Fundamentals,
    config: ScoringConfig,
    collector: BreakdownCollector | None = None,
) -> tuple[int, str, str, str]:
    """综合生成个股入场分、信号等级、说明标签和公式描述。"""
    e = config.stock_entry
    raw = round((valuation_score * e.valuation_weight) + (trend_score * e.trend_weight) + (quality_score * e.quality_weight))
    formula = (
        f"入场分 = 估值({valuation_score}) × {e.valuation_weight} + "
        f"趋势({trend_score}) × {e.trend_weight} + "
        f"质量({quality_score}) × {e.quality_weight} = {raw}"
    )
    notes: list[str] = []
    score = raw
    score += score_position_adjustment(price, notes, config=config.position, collector=collector)

    if quality_score < e.weak_quality_threshold:
        score -= e.weak_quality_penalty
        notes.append("weak_quality")
        if collector:
            collector.add(factor="质量偏弱惩罚", value=f"质量分{quality_score} < {e.weak_quality_threshold}",
                          score=-e.weak_quality_penalty, detail=f"质量分 < {e.weak_quality_threshold} → { -e.weak_quality_penalty}", category="adjustment")

    if valuation_score < e.rich_valuation_threshold:
        score -= e.rich_valuation_penalty
        notes.append("rich_valuation")
        if collector:
            collector.add(factor="估值偏贵惩罚", value=f"估值分{valuation_score} < {e.rich_valuation_threshold}",
                          score=-e.rich_valuation_penalty, detail=f"估值分 < {e.rich_valuation_threshold} → { -e.rich_valuation_penalty}", category="adjustment")

    if is_earnings_soon(fundamentals.earnings_timestamp, days=e.earnings_soon_days):
        score -= e.earnings_soon_penalty
        notes.append("earnings_soon")
        if collector:
            collector.add(factor="财报临近折扣", value=f"{e.earnings_soon_days}天内",
                          score=-e.earnings_soon_penalty, detail=f"财报在 {e.earnings_soon_days} 天内 → { -e.earnings_soon_penalty}", category="adjustment")

    final, signal, note = finalize_signal(score, notes, config=config)
    if collector and score != final:
        formula += f"\n原始分数 {raw}，经各修正后得分 {score}，clamp 后 = {final}"
    return final, signal, note, formula


def score_etf_entry(
    *,
    valuation_score: int,
    trend_score: int,
    price: PriceSnapshot,
    config: ScoringConfig,
    collector: BreakdownCollector | None = None,
) -> tuple[int, str, str, str]:
    """综合生成 ETF 入场分、信号等级、说明标签和公式描述。"""
    e = config.etf_entry
    raw = round((valuation_score * e.valuation_weight) + (trend_score * e.trend_weight))
    formula = f"入场分 = 估值({valuation_score}) × {e.valuation_weight} + 趋势({trend_score}) × {e.trend_weight} = {raw}"
    notes: list[str] = []
    score = raw
    score += score_position_adjustment(price, notes, config=config.position, collector=collector)

    if valuation_score < e.rich_valuation_threshold:
        score -= e.rich_valuation_penalty
        notes.append("rich_valuation")
        if collector:
            collector.add(factor="估值偏贵惩罚", value=f"估值分{valuation_score} < {e.rich_valuation_threshold}",
                          score=-e.rich_valuation_penalty, detail=f"估值分 < {e.rich_valuation_threshold} → { -e.rich_valuation_penalty}", category="adjustment")

    final, signal, note = finalize_signal(score, notes, config=config)
    if collector and score != final:
        formula += f"\n原始分数 {raw}，经修正后得分 {score}，clamp 后 = {final}"
    return final, signal, note, formula


def score_position_adjustment(price: PriceSnapshot, notes: list[str], *, config: PositionConfig, collector: BreakdownCollector | None = None) -> int:
    """根据价格相对 60 日线的位置给入场分做修正。"""
    p = config
    adjustment = 0
    distance = _pct_diff(price.current_price, price.sma60)
    if distance is None:
        return adjustment
    if abs(distance) <= p.near_ma_threshold:
        adjustment += p.near_ma_bonus
        notes.append("near_60d_ma")
        if collector:
            collector.add(factor="贴近60日线", value=_fmt_v(distance, is_pct=True), score=p.near_ma_bonus,
                          detail=f"偏离 {_fmt_v(distance, is_pct=True)}，|偏离| ≤ {_fmt_v(p.near_ma_threshold, is_pct=True)} → +{p.near_ma_bonus}", category="adjustment")
    elif distance > p.extended_above_threshold:
        adjustment -= p.extended_above_penalty
        notes.append("extended_above_60d")
        if collector:
            collector.add(factor="高于60日线过远", value=_fmt_v(distance, is_pct=True), score=-p.extended_above_penalty,
                          detail=f"偏离 {_fmt_v(distance, is_pct=True)} > {_fmt_v(p.extended_above_threshold, is_pct=True)} → { -p.extended_above_penalty}", category="adjustment")
    elif distance < -p.below_ma_threshold:
        adjustment -= p.below_ma_penalty
        notes.append("below_60d_too_far")
        if collector:
            collector.add(factor="低于60日线过远", value=_fmt_v(distance, is_pct=True), score=-p.below_ma_penalty,
                          detail=f"偏离 {_fmt_v(distance, is_pct=True)} < {_fmt_v(-p.below_ma_threshold, is_pct=True)} → { -p.below_ma_penalty}", category="adjustment")
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
