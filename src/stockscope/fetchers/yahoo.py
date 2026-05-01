from __future__ import annotations

import contextlib
import io
from statistics import mean

try:
    import yfinance as yf
except ImportError:  # pragma: no cover
    yf = None

from stockscope.models import Fundamentals, PriceSnapshot


class YahooClient:
    def __init__(self) -> None:
        """初始化 Yahoo 数据客户端。

        作用：
        - 检查 `yfinance` 依赖是否可用
        - 在程序启动阶段尽早暴露环境问题
        """
        if yf is None:
            raise RuntimeError("yfinance is required. Install it in the local virtual environment.")

    def fetch_summary(self, symbol: str) -> Fundamentals:
        """拉取单个标的的基础面摘要信息。

        作用：
        - 识别标的是股票还是 ETF
        - 获取估值、盈利能力、现金流、行业等字段
        - 统一整理成 `Fundamentals` 对象供后续打分使用
        """
        ticker = yf.Ticker(symbol)
        fast_info = dict(ticker.fast_info or {})
        quote_type = (fast_info.get("quoteType") or "").upper() or "UNKNOWN"
        if quote_type == "ETF":
            info = {}
        else:
            with contextlib.redirect_stderr(io.StringIO()):
                info = ticker.info or {}
        short_name = info.get("shortName") or info.get("longName") or symbol
        earnings_timestamp = _extract_earnings_timestamp(ticker)
        return Fundamentals(
            symbol=symbol,
            quote_type=quote_type,
            short_name=short_name,
            sector=info.get("sector") or info.get("category"),
            industry=info.get("industry"),
            market_cap=info.get("marketCap") or fast_info.get("marketCap"),
            trailing_pe=info.get("trailingPE"),
            forward_pe=info.get("forwardPE"),
            price_to_sales=info.get("priceToSalesTrailing12Months"),
            enterprise_to_ebitda=info.get("enterpriseToEbitda"),
            revenue_growth=info.get("revenueGrowth"),
            earnings_growth=info.get("earningsGrowth"),
            gross_margins=info.get("grossMargins"),
            profit_margins=info.get("profitMargins"),
            free_cashflow=info.get("freeCashflow"),
            operating_cashflow=info.get("operatingCashflow"),
            debt_to_equity=info.get("debtToEquity"),
            return_on_equity=info.get("returnOnEquity"),
            return_on_assets=info.get("returnOnAssets"),
            dividend_yield=info.get("dividendYield"),
            earnings_timestamp=earnings_timestamp,
        )

    def fetch_chart(self, symbol: str, range_: str = "1y", interval: str = "1d") -> PriceSnapshot:
        """拉取单个标的的历史价格并计算基础行情指标。

        作用：
        - 获取收盘价时间序列
        - 计算 20/60/120 日均线
        - 计算 52 周高低点和区间收益率
        - 为趋势分和买点判断提供输入
        """
        ticker = yf.Ticker(symbol)
        history = ticker.history(period=range_, interval=interval, auto_adjust=False)
        closes = [float(item) for item in history["Close"].dropna().tolist()] if not history.empty else []
        last_date = ""
        if not history.empty and hasattr(history.index, "strftime"):
            try:
                last_date = history.index[-1].strftime("%Y-%m-%d")
            except Exception:
                pass
        snapshot = PriceSnapshot(symbol=symbol, closes=closes, last_date=last_date or None)
        if not closes:
            return snapshot

        snapshot.current_price = closes[-1]
        snapshot.sma20 = _sma(closes, 20)
        snapshot.sma60 = _sma(closes, 60)
        snapshot.sma120 = _sma(closes, 120)
        snapshot.high_52w = max(closes)
        snapshot.low_52w = min(closes)
        snapshot.return_6m = _window_return(closes, 126)
        snapshot.return_1y = _window_return(closes, min(252, len(closes) - 1))
        return snapshot


def _sma(values: list[float], period: int) -> float | None:
    """计算简单移动平均线。

    作用：
    - 根据给定周期计算均线值
    - 给趋势判断和入场判断复用
    """
    if len(values) < period:
        return None
    return round(mean(values[-period:]), 4)


def _window_return(values: list[float], period: int) -> float | None:
    """计算指定窗口的区间涨跌幅。

    作用：
    - 计算 6 个月、1 年等区间收益
    - 为相对强弱和趋势分析提供基础数据
    """
    if period <= 0 or len(values) <= period:
        return None
    start = values[-period - 1]
    end = values[-1]
    if start == 0:
        return None
    return (end / start) - 1


def is_network_error(error: Exception) -> bool:
    """判断异常是否属于网络或依赖相关问题。

    作用：
    - 让上层对抓数失败做统一处理
    - 区分预期中的访问错误和代码逻辑错误
    """
    return isinstance(error, (TimeoutError, ConnectionError, RuntimeError))


def _extract_earnings_timestamp(ticker: "yf.Ticker") -> int | None:
    """从 Yahoo 的日历数据中提取最近财报时间。

    作用：
    - 为入场分提供“财报临近”的风险判断
    - 兼容不同返回结构，统一输出时间戳
    """
    calendar = getattr(ticker, "calendar", None)
    if calendar is None:
        return None
    try:
        if hasattr(calendar, "index") and "Earnings Date" in calendar.index:
            value = calendar.loc["Earnings Date"][0]
        elif isinstance(calendar, dict):
            value = calendar.get("Earnings Date")
        else:
            value = None
        if value is None:
            return None
        if hasattr(value, "timestamp"):
            return int(value.timestamp())
    except Exception:
        return None
    return None
