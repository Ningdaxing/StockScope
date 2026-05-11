from __future__ import annotations

import contextlib
import io
import json
import logging
import time
from pathlib import Path
from statistics import mean

try:
    import yfinance as yf
except ImportError:  # pragma: no cover
    yf = None

from stockscope.models import Fundamentals, PriceSnapshot

logging.getLogger("yfinance").setLevel(logging.CRITICAL)

_CACHE_TTL_SUMMARY = 2 * 3600   # 基本面缓存 2 小时
_CACHE_TTL_CHART = 1 * 3600     # 行情缓存 1 小时
_MAX_RETRIES = 3
_BASE_BACKOFF = 2.0  # 秒
_RATE_LIMIT_SLEEP = 1.2  # 每次请求最小间隔，避免连续触发限流


class YahooClient:
    def __init__(self, cache_dir: str | Path = "outputs/cache") -> None:
        """初始化 Yahoo 数据客户端。

        作用：
        - 检查 `yfinance` 依赖是否可用
        - 初始化本地缓存目录，减少对 Yahoo API 的重复请求
        """
        if yf is None:
            raise RuntimeError("yfinance is required. Install it in the local virtual environment.")
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_path = self._cache_dir / "yahoo_cache.json"
        self._cache: dict[str, dict] = {}
        self._dirty = False
        self._last_request_at = 0.0
        self._load_cache()

    # ------------------------------------------------------------------
    # 缓存读写
    # ------------------------------------------------------------------

    def _load_cache(self) -> None:
        if self._cache_path.exists():
            try:
                self._cache = json.loads(self._cache_path.read_text())
            except Exception:
                self._cache = {}

    def _save_cache(self) -> None:
        if not self._dirty:
            return
        try:
            self._cache_path.write_text(json.dumps(self._cache, ensure_ascii=False, indent=2))
            self._dirty = False
        except Exception:
            pass

    def _cache_get(self, key: str, ttl: int) -> dict | None:
        entry = self._cache.get(key)
        if not entry:
            return None
        if time.time() - entry.get("ts", 0) > ttl:
            return None
        return entry.get("data")

    def _cache_set(self, key: str, data: dict) -> None:
        self._cache[key] = {"ts": time.time(), "data": data}
        self._dirty = True

    # ------------------------------------------------------------------
    # 请求节流 + 重试
    # ------------------------------------------------------------------

    def _throttle(self) -> None:
        """确保两次请求之间有最小间隔，避免触发限流。"""
        elapsed = time.time() - self._last_request_at
        if elapsed < _RATE_LIMIT_SLEEP:
            time.sleep(_RATE_LIMIT_SLEEP - elapsed)
        self._last_request_at = time.time()

    @staticmethod
    def _is_rate_limit(error: Exception) -> bool:
        msg = str(error).lower()
        return "rate limit" in msg or "too many requests" in msg or "429" in msg

    def _retry_call(self, fn, *, label: str = ""):
        """带指数退避的重试调用。"""
        last_error = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                self._throttle()
                return fn()
            except Exception as exc:
                last_error = exc
                if attempt < _MAX_RETRIES and (self._is_rate_limit(exc) or is_network_error(exc)):
                    wait = _BASE_BACKOFF * (2 ** attempt)
                    logging.getLogger("stockscope").warning(
                        "%s 第 %d/%d 次失败（%s），%0.1fs 后重试",
                        label, attempt + 1, _MAX_RETRIES, exc, wait,
                    )
                    time.sleep(wait)
                    continue
                raise
        raise last_error or RuntimeError("retry exhausted")

    # ------------------------------------------------------------------
    # 数据拉取
    # ------------------------------------------------------------------

    def fetch_summary(self, symbol: str) -> Fundamentals:
        """拉取单个标的的基础面摘要信息（带缓存）。"""
        cache_key = f"summary:{symbol}"
        cached = self._cache_get(cache_key, _CACHE_TTL_SUMMARY)
        if cached:
            return Fundamentals(**cached)

        ticker = yf.Ticker(symbol)
        with contextlib.redirect_stderr(io.StringIO()):
            info = self._retry_call(
                lambda: dict(ticker.info or {}),
                label=f"{symbol} summary",
            )
        quote_type = (info.get("quoteType") or "").upper() or "UNKNOWN"
        if quote_type in ("ETF", "MUTUALFUND"):
            for pe_key in ("trailingPE", "forwardPE", "priceToSalesTrailing12Months",
                           "enterpriseToEbitda", "revenueGrowth", "earningsGrowth",
                           "grossMargins", "profitMargins", "operatingMargins",
                           "freeCashflow", "operatingCashflow", "debtToEquity",
                           "returnOnEquity", "returnOnAssets"):
                info.pop(pe_key, None)

        earnings_timestamp = _extract_earnings_timestamp(ticker)
        result = Fundamentals(
            symbol=symbol,
            quote_type=quote_type,
            short_name=info.get("shortName") or info.get("longName") or symbol,
            sector=info.get("sector") or info.get("category"),
            industry=info.get("industry"),
            market_cap=info.get("marketCap"),
            trailing_pe=info.get("trailingPE"),
            forward_pe=info.get("forwardPE"),
            price_to_sales=info.get("priceToSalesTrailing12Months"),
            enterprise_to_ebitda=info.get("enterpriseToEbitda"),
            revenue_growth=info.get("revenueGrowth"),
            earnings_growth=info.get("earningsGrowth"),
            gross_margins=info.get("grossMargins"),
            profit_margins=info.get("profitMargins"),
            operating_margins=info.get("operatingMargins"),
            total_revenue=info.get("totalRevenue"),
            free_cashflow=info.get("freeCashflow"),
            operating_cashflow=info.get("operatingCashflow"),
            debt_to_equity=info.get("debtToEquity"),
            return_on_equity=info.get("returnOnEquity"),
            return_on_assets=info.get("returnOnAssets"),
            dividend_yield=_normalize_yield(info.get("dividendYield")),
            earnings_timestamp=earnings_timestamp,
            business_summary=info.get("longBusinessSummary") or "",
        )
        self._cache_set(cache_key, _fundamentals_to_dict(result))
        self._save_cache()
        return result

    def fetch_chart(self, symbol: str, range_: str = "1y", interval: str = "1d") -> PriceSnapshot:
        """拉取单个标的的历史价格并计算基础行情指标（带缓存）。"""
        cache_key = f"chart:{symbol}"
        cached = self._cache_get(cache_key, _CACHE_TTL_CHART)
        if cached:
            return PriceSnapshot(**cached)

        ticker = yf.Ticker(symbol)
        history = self._retry_call(
            lambda: ticker.history(period=range_, interval=interval, auto_adjust=False),
            label=f"{symbol} chart",
        )
        closes = [float(item) for item in history["Close"].dropna().tolist()] if not history.empty else []
        volumes = [float(item) for item in history["Volume"].dropna().tolist()] if not history.empty else []
        last_date = ""
        if not history.empty and hasattr(history.index, "strftime"):
            try:
                last_date = history.index[-1].strftime("%Y-%m-%d")
            except Exception:
                pass
        snapshot = PriceSnapshot(symbol=symbol, closes=closes, volumes=volumes, last_date=last_date or None)
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
        snapshot.vwap_60 = _vwap(closes, volumes, 60)
        snapshot.trend_slope = _trend_slope(closes, 60)

        self._cache_set(cache_key, _pricesnapshot_to_dict(snapshot))
        self._save_cache()
        return snapshot


# ------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------

def _fundamentals_to_dict(f: Fundamentals) -> dict:
    """把 Fundamentals 转成可 JSON 序列化的 dict（排除 None）。"""
    return {k: v for k, v in {
        "symbol": f.symbol, "quote_type": f.quote_type, "short_name": f.short_name,
        "sector": f.sector, "industry": f.industry, "market_cap": f.market_cap,
        "trailing_pe": f.trailing_pe, "forward_pe": f.forward_pe,
        "price_to_sales": f.price_to_sales, "enterprise_to_ebitda": f.enterprise_to_ebitda,
        "revenue_growth": f.revenue_growth, "earnings_growth": f.earnings_growth,
        "gross_margins": f.gross_margins, "profit_margins": f.profit_margins,
        "operating_margins": f.operating_margins, "total_revenue": f.total_revenue,
        "free_cashflow": f.free_cashflow, "operating_cashflow": f.operating_cashflow,
        "debt_to_equity": f.debt_to_equity, "return_on_equity": f.return_on_equity,
        "return_on_assets": f.return_on_assets, "dividend_yield": f.dividend_yield,
        "earnings_timestamp": f.earnings_timestamp,
        "business_summary": f.business_summary,
    }.items() if v is not None}


def _pricesnapshot_to_dict(p: PriceSnapshot) -> dict:
    """把 PriceSnapshot 转成可 JSON 序列化的 dict（排除 None 和空列表）。"""
    return {k: v for k, v in {
        "symbol": p.symbol, "closes": p.closes, "volumes": p.volumes,
        "current_price": p.current_price, "sma20": p.sma20, "sma60": p.sma60,
        "sma120": p.sma120, "high_52w": p.high_52w, "low_52w": p.low_52w,
        "return_6m": p.return_6m, "return_1y": p.return_1y, "last_date": p.last_date,
        "vwap_60": p.vwap_60, "trend_slope": p.trend_slope,
    }.items() if v is not None and v != []}


def _sma(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return round(mean(values[-period:]), 4)


def _window_return(values: list[float], period: int) -> float | None:
    if period <= 0 or len(values) <= period:
        return None
    start = values[-period - 1]
    end = values[-1]
    if start == 0:
        return None
    return (end / start) - 1


def is_network_error(error: Exception) -> bool:
    return isinstance(error, (TimeoutError, ConnectionError, RuntimeError))


def _normalize_yield(value: float | None) -> float | None:
    if value is None:
        return None
    return value / 100


def _vwap(closes: list[float], volumes: list[float], period: int) -> float | None:
    if len(closes) < period or len(volumes) < period:
        return None
    c = closes[-period:]
    v = volumes[-period:]
    total_vol = sum(v)
    if total_vol == 0:
        return None
    return round(sum(price * vol for price, vol in zip(c, v)) / total_vol, 4)


def _trend_slope(closes: list[float], period: int) -> float | None:
    if len(closes) < period:
        return None
    ys = closes[-period:]
    n = len(ys)
    mean_x = (n - 1) / 2
    mean_y = sum(ys) / n
    num = sum((i - mean_x) * (ys[i] - mean_y) for i in range(n))
    den = sum((i - mean_x) ** 2 for i in range(n))
    if den == 0:
        return None
    daily_slope = num / den
    if mean_y == 0:
        return None
    return round((daily_slope * 252) / mean_y, 4)


def _extract_earnings_timestamp(ticker: "yf.Ticker") -> int | None:
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
