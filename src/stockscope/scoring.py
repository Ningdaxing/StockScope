from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone

from stockscope.models import Fundamentals, PriceSnapshot, ScoredTicker


def score_ticker(
    fundamentals: Fundamentals,
    price: PriceSnapshot,
    benchmark_price: PriceSnapshot | None = None,
) -> ScoredTicker:
    """对单个标的执行完整打分并组装最终输出。

    作用：
    - 串联质量分、估值分、趋势分和入场分
    - 生成一条可直接写入报表的结果记录
    """
    asset_type = normalize_asset_type(fundamentals.quote_type)
    quality_score = score_quality(fundamentals) if asset_type == "STOCK" else None
    valuation_score = score_valuation(fundamentals, asset_type)
    trend_score = score_trend(price, benchmark_price)
    entry_score, signal, note = score_entry(
        asset_type=asset_type,
        quality_score=quality_score,
        valuation_score=valuation_score,
        trend_score=trend_score,
        price=price,
        fundamentals=fundamentals,
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


def score_quality(f: Fundamentals) -> int:
    """计算个股质量分。

    作用：
    - 评估企业基本面是否健康
    - 重点衡量增长、利润率、负债和现金流表现
    - 用来过滤基本面恶化的公司
    """
    score = 50
    score += band_score(f.revenue_growth, good=0.08, ok=0.03, bad=-0.05, weight=12)
    score += band_score(f.earnings_growth, good=0.10, ok=0.03, bad=-0.08, weight=12)
    score += margin_score(f.gross_margins, good=0.45, ok=0.30, bad=0.15, weight=8)
    score += margin_score(f.profit_margins, good=0.18, ok=0.10, bad=0.03, weight=10)
    score += roe_score(f.return_on_equity, good=0.15, ok=0.10, bad=0.05, weight=10)
    score += inverse_score(f.debt_to_equity, good=60, ok=120, bad=220, weight=10)
    score += cashflow_score(f.free_cashflow, f.operating_cashflow, weight=8)
    return clamp(score)


def score_valuation(f: Fundamentals, asset_type: str) -> int:
    """计算估值分。

    作用：
    - 评估当前估值是否偏贵
    - 针对股票和 ETF 使用不同阈值
    - 用来降低高估值买入的风险
    """
    score = 50
    if asset_type == "ETF":
        score += inverse_score(f.trailing_pe, good=18, ok=24, bad=32, weight=12)
        score += inverse_score(f.forward_pe, good=17, ok=22, bad=28, weight=12)
        score += yield_score(f.dividend_yield, good=0.03, ok=0.015, weight=6)
        return clamp(score)

    score += inverse_score(f.trailing_pe, good=18, ok=28, bad=45, weight=12)
    score += inverse_score(f.forward_pe, good=17, ok=24, bad=38, weight=12)
    score += inverse_score(f.price_to_sales, good=3, ok=6, bad=12, weight=8)
    score += inverse_score(f.enterprise_to_ebitda, good=12, ok=18, bad=30, weight=8)
    return clamp(score)


def score_trend(price: PriceSnapshot, benchmark_price: PriceSnapshot | None) -> int:
    """计算趋势分。

    作用：
    - 结合均线位置、回撤幅度和相对强弱判断趋势状态
    - 给最终买点判断补充技术面依据
    """
    score = 50
    if price.current_price and price.sma20 and price.current_price >= price.sma20:
        score += 10
    if price.current_price and price.sma60 and price.current_price >= price.sma60:
        score += 12
    if price.current_price and price.sma120 and price.current_price >= price.sma120:
        score += 8

    drawdown = _drawdown_from_high(price.current_price, price.high_52w)
    if drawdown is not None:
        if -0.18 <= drawdown <= -0.03:
            score += 8
        elif drawdown < -0.35:
            score -= 10

    rel_strength = relative_strength(price.return_6m, benchmark_price.return_6m if benchmark_price else None)
    if rel_strength is not None:
        if rel_strength > 0.05:
            score += 10
        elif rel_strength < -0.05:
            score -= 8
    return clamp(score)


def score_entry(
    *,
    asset_type: str,
    quality_score: int | None,
    valuation_score: int,
    trend_score: int,
    price: PriceSnapshot,
    fundamentals: Fundamentals,
) -> tuple[int, str, str]:
    """综合生成入场分、信号等级和说明标签。

    作用：
    - 把估值、趋势、质量三个维度压缩成最终入场判断
    - 对财报临近、离均线过远等情况做额外修正
    - 输出 A/B/C/D 信号供报表展示
    """
    score = round((valuation_score * 0.4) + (trend_score * 0.4) + ((quality_score or 60) * 0.2))
    notes: list[str] = []

    distance = _pct_diff(price.current_price, price.sma60)
    if distance is not None:
        if abs(distance) <= 0.03:
            score += 8
            notes.append("near_60d_ma")
        elif distance > 0.12:
            score -= 8
            notes.append("extended_above_60d")
        elif distance < -0.10:
            score -= 10
            notes.append("below_60d_too_far")

    if quality_score is not None and quality_score < 45:
        score -= 12
        notes.append("weak_quality")

    if valuation_score < 40:
        score -= 10
        notes.append("rich_valuation")

    if is_earnings_soon(fundamentals.earnings_timestamp, days=14):
        score -= 6
        notes.append("earnings_soon")

    score = clamp(score)
    if score >= 78:
        signal = "A"
    elif score >= 64:
        signal = "B"
    elif score >= 50:
        signal = "C"
    else:
        signal = "D"
    note = ",".join(notes) if notes else "balanced"
    return score, signal, note


def band_score(value: float | None, *, good: float, ok: float, bad: float, weight: int) -> int:
    """按分段阈值给“越高越好”的指标打分。

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
    """按分段阈值给“越低越好”的指标打分。

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
