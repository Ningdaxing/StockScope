#!/usr/bin/env python
"""StockScope 个股深度分析 — 拉取 yfinance 数据 -> 生成中文 HTML / PDF 报告."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import yfinance as yf

# StockScope 评分子系统路径
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent  # stock-analysis/
_SKILLS_DIR = _SCRIPTS_DIR.parent                       # skills/
_SRC_DIR = Path(__file__).resolve().parent.parent.parent.parent / "src"  # StockScope/src/
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

# 翻译缓存
_TRANSLATE_CACHE_PATH = Path(__file__).parent / ".translate_cache.json"


def _load_translate_cache() -> dict:
    if _TRANSLATE_CACHE_PATH.exists():
        try:
            return json.loads(_TRANSLATE_CACHE_PATH.read_text())
        except Exception:
            pass
    return {}


def _save_translate_cache(cache: dict) -> None:
    try:
        _TRANSLATE_CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False))
    except Exception:
        pass


def _translate_en_to_zh(text: str) -> str:
    """翻译英文到中文，带缓存."""
    if not text or len(text) < 50:
        return text
    cache = _load_translate_cache()
    # 用前 100 字符做 key
    cache_key = text[:100].strip()
    if cache_key in cache:
        return cache[cache_key]
    try:
        from deep_translator import GoogleTranslator
        result = GoogleTranslator(source="en", target="zh-CN").translate(text)
        # 如果翻译太长，截断
        if len(result) > 600:
            result = result[:600] + "..."
        cache[cache_key] = result
        _save_translate_cache(cache)
        return result
    except Exception:
        return text

# ── 分析师评级中英文映射 ──
_REC_MAP = {
    "strong_buy": "强烈买入",
    "buy": "买入",
    "hold": "持有",
    "sell": "卖出",
    "strong_sell": "强烈卖出",
    "underweight": "减持",
    "overweight": "增持",
}

# ── 行业常见中文翻译 ──
_INDUSTRY_CN = {
    "Electronic Components": "电子元器件",
    "Semiconductors": "半导体",
    "Consumer Electronics": "消费电子",
    "Internet Content & Information": "互联网内容与信息",
    "Internet Retail": "互联网零售",
    "Software—Infrastructure": "软件—基础设施",
    "Software—Application": "软件—应用",
    "Financial—Credit Services": "金融—信贷服务",
    "Banks—Diversified": "银行—多元化",
    "Banks—Regional": "银行—区域性",
    "Insurance—Life": "保险—人寿",
    "Insurance—Property & Casualty": "保险—财产与意外",
    "Asset Management": "资产管理",
    "Capital Markets": "资本市场",
    "Aerospace & Defense": "航空航天与国防",
    "Medical Devices": "医疗器械",
    "Biotechnology": "生物科技",
    "Drug Manufacturers—General": "制药—通用",
    "Healthcare Plans": "医疗保健计划",
    "Oil & Gas Integrated": "石油天然气—综合",
    "Oil & Gas E&P": "石油天然气—勘探与生产",
    "Telecom Services": "电信服务",
    "Auto Manufacturers": "汽车制造",
    "Restaurants": "餐饮",
    "Retail—Defense": "零售—防御型",
    "Grocery Stores": "杂货零售",
    "Household & Personal Products": "家居与个人用品",
    "Beverages—Non-Alcoholic": "饮料—非酒精",
    "Entertainment": "娱乐",
    "Advertising Agencies": "广告代理",
    "Communication Equipment": "通信设备",
    "Computer Hardware": "计算机硬件",
    "Information Technology Services": "信息技术服务",
}
_SECTOR_CN = {
    "Technology": "科技",
    "Communication Services": "通信服务",
    "Consumer Cyclical": "周期性消费",
    "Consumer Defensive": "防御性消费",
    "Financial Services": "金融服务",
    "Healthcare": "医疗健康",
    "Industrials": "工业",
    "Energy": "能源",
    "Utilities": "公用事业",
    "Real Estate": "房地产",
    "Basic Materials": "基础材料",
}

CSS = """<style>
  /* ═══════════ 屏幕：深色主题 ═══════════ */
  :root { --bg:#0d1117;--card-bg:#161b22;--border:#30363d;--text:#c9d1d9;
    --text-secondary:#8b949e;--green:#3fb950;--red:#f85149;--yellow:#d2991d;
    --blue:#58a6ff;--purple:#bc8cff;--orange:#f0883e;--accent:#1f6feb; }
  * { box-sizing:border-box;margin:0;padding:0; }
  body { background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;line-height:1.6;max-width:1100px;margin:0 auto; }
  header { background:linear-gradient(135deg,#1a2332 0%,#0d1b2a 100%);border-bottom:1px solid var(--border);padding:36px 24px;text-align:center; }
  header h1 { font-size:2em;color:#f0f6fc;margin-bottom:2px; }
  header .ticker { font-size:3em;font-weight:900;color:var(--blue);letter-spacing:4px; }
  header .subtitle { color:var(--text-secondary);font-size:.95em;margin-top:4px; }
  header .date { color:var(--blue);font-size:.9em;margin-top:8px; }
  section { padding:24px 24px; }
  section h2 { font-size:1.35em;color:#f0f6fc;margin-bottom:16px;padding-bottom:8px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:10px; }
  section h2 .num { background:var(--accent);color:white;border-radius:50%;width:30px;height:30px;display:flex;align-items:center;justify-content:center;font-size:.82em;flex-shrink:0;font-weight:700; }
  section h3 { color:#f0f6fc;margin-bottom:10px; }
  .data-table-wrapper { overflow-x:auto;margin-bottom:20px;margin-top:8px; }
  table { width:100%;border-collapse:collapse;font-size:.88em; }
  thead th { background:#21262d;color:#f0f6fc;padding:10px 14px;text-align:left;font-weight:600;border:1px solid var(--border);white-space:nowrap; }
  tbody td { padding:8px 14px;border:1px solid var(--border); }
  tbody tr:nth-child(even){background:#0d1117;} tbody tr:hover{background:#1c2128;}
  .highlight { background:rgba(63,185,80,.08)!important; }
  .highlight-red { background:rgba(248,81,73,.08)!important; }
  .val-up{color:var(--green);font-weight:600;} .val-down{color:var(--red);font-weight:600;} .val-best{color:var(--yellow);font-weight:700;}
  .metric-grid { display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-bottom:20px; }
  .metric-card { background:var(--card-bg);border:1px solid var(--border);border-radius:8px;padding:14px 16px; }
  .metric-card .label { font-size:.8em;color:var(--text-secondary);margin-bottom:4px; }
  .metric-card .value { font-size:1.3em;font-weight:700;color:#f0f6fc; }
  .metric-card .sub{font-size:.78em;color:var(--text-secondary);margin-top:2px;}
  .metric-card.good{border-left:3px solid var(--green);} .metric-card.warn{border-left:3px solid var(--yellow);} .metric-card.danger{border-left:3px solid var(--red);} .metric-card.accent{border-left:3px solid var(--blue);}
  .tag { display:inline-block;padding:2px 10px;border-radius:12px;font-size:.78em;margin-right:6px;margin-bottom:6px;font-weight:600; }
  .tag-bull{background:rgba(63,185,80,.15);color:var(--green);border:1px solid rgba(63,185,80,.3);}
  .tag-bear{background:rgba(248,81,73,.15);color:var(--red);border:1px solid rgba(248,81,73,.3);}
  .tag-neutral{background:rgba(210,153,29,.15);color:var(--yellow);border:1px solid rgba(210,153,29,.3);}
  .tag-info{background:rgba(88,166,255,.12);color:var(--blue);border:1px solid rgba(88,166,255,.25);}
  .info-card { background:var(--card-bg);border:1px solid var(--border);border-radius:8px;padding:20px;margin-bottom:20px; }
  .grid-2 { display:grid;grid-template-columns:1fr 1fr;gap:20px; }
  @media(max-width:768px){.grid-2{grid-template-columns:1fr;}}
  .verdict-box { background:linear-gradient(135deg,#1a2a1a 0%,#0d1b0d 100%);border:1px solid rgba(63,185,80,.35);border-radius:10px;padding:28px;margin-top:16px; }
  .verdict-box h3 { color:var(--green);font-size:1.2em;margin-bottom:16px; }
  .verdict-box .big-call { font-size:1.6em;font-weight:900;color:var(--green);text-align:center;margin:16px 0;letter-spacing:2px; }
  .quote{border-left:3px solid var(--blue);padding:12px 16px;margin:16px 0;background:rgba(31,111,235,.06);border-radius:0 6px 6px 0;font-style:italic;color:var(--text-secondary);}
  .suggestion-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin-top:16px;}
  .suggestion-item{background:var(--card-bg);border:1px solid var(--border);border-radius:8px;padding:14px;text-align:center;}
  .suggestion-item .title{font-size:.8em;color:var(--text-secondary);margin-bottom:4px;} .suggestion-item .val{font-size:1.15em;font-weight:700;color:#f0f6fc;}
  footer{text-align:center;padding:24px;color:var(--text-secondary);font-size:.8em;border-top:1px solid var(--border);}
</style>
<style media="print">
  /* ═══════════ 打印 / PDF：白底排版主题 ═══════════ */
  @page { size: A4; margin: 16mm 14mm 18mm 14mm;
    @bottom-center { content: "— " counter(page) " —"; font-size: 9px; color: #999; } }
  @page :first { @bottom-center { content: none; } }

  body { background:#fff;max-width:none;margin:0;font-size:10pt;line-height:1.6;color:#222;
    font-family:"PingFang SC","Hiragino Sans GB","Microsoft YaHei","Noto Sans SC",sans-serif; }
  p, li, td, th, div { color:#222; }
  header { background:#f6f8fa;border-bottom:3px solid #1f6feb;padding:28px 20px;text-align:center; }
  header h1 { color:#111;font-size:1.6em; }
  header .ticker { color:#0969da;font-size:2.4em;letter-spacing:3px; }
  header .subtitle, header .date { color:#555; }
  header .date { color:#0969da; }

  section { padding:14px 0; margin-bottom:6px; }
  section h2 { color:#111;font-size:1.15em;border-bottom:2px solid #d0d7de;padding-bottom:6px;margin-bottom:10px; }
  section h2 .num { font-size:.85em;background:#1f6feb;color:#fff; }
  section h3 { color:#333;margin-bottom:6px;font-size:1.05em; }

  table { font-size:.82em; }
  thead th { background:#e5e7eb;color:#111;border:1px solid #c0c7cf;padding:6px 10px; }
  tbody td { border:1px solid #d0d7de;padding:5px 10px; }
  tbody tr:nth-child(even){background:#f8f9fa;}
  .highlight { background:#e6f7e9!important; }
  .highlight-red { background:#fde8e9!important; }

  .val-up{color:#1a7f37!important;font-weight:600;} .val-down{color:#cf222e!important;font-weight:600;} .val-best{color:#9a6700!important;font-weight:700;}

  .metric-grid { display:flex;flex-wrap:wrap;gap:10px;margin-bottom:16px; }
  .metric-card { flex:1 1 190px;background:#f8f9fa;border:1px solid #d0d7de;border-radius:6px;padding:10px 14px; }
  .metric-card .label { color:#555;font-size:.78em; }
  .metric-card .value { color:#111;font-size:1.2em;font-weight:700; }
  .metric-card .sub{color:#555;font-size:.75em;}
  .metric-card.good{border-left:3px solid #1a7f37;} .metric-card.warn{border-left:3px solid #9a6700;}
  .metric-card.danger{border-left:3px solid #cf222e;} .metric-card.accent{border-left:3px solid #0969da;}

  .tag-bull{background:#e6f7e9;color:#1a7f37!important;border:1px solid #b7dfc2;}
  .tag-bear{background:#fde8e9;color:#cf222e!important;border:1px solid #f5c2c5;}
  .tag-neutral{background:#fef5e4;color:#9a6700!important;border:1px solid #f5d9a0;}
  .tag-info{background:#e6f0fb;color:#0969da!important;border:1px solid #b6d4f5;}

  .info-card { background:#f8f9fa;border:1px solid #d0d7de;border-radius:6px;padding:16px;margin-bottom:14px; }
  .grid-2 { display:flex;gap:16px; }
  .grid-2 > * { flex:1;min-width:0; }

  .verdict-box { background:#f0fdf4;border:2px solid #b7dfc2;padding:24px;margin-top:14px; }
  .verdict-box h3 { color:#1a7f37; }
  .verdict-box .big-call { color:#1a7f37;font-size:1.4em; }

  .quote{background:#f0f7ff;color:#555;border-left:3px solid #0969da;}

  .suggestion-grid{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px;}
  .suggestion-item{flex:1 1 150px;background:#f8f9fa;border:1px solid #d0d7de;border-radius:6px;padding:12px;}
  .suggestion-item .title{color:#555;font-size:.78em;}
  .suggestion-item .val{color:#111;font-size:1.1em;font-weight:700;}

  footer{border-top:1px solid #d0d7de;color:#888;padding:16px;font-size:.8em;}

  section, .info-card, .verdict-box { break-inside:avoid; }
  h2, h3 { break-after:avoid; }
  thead { display:table-header-group; }
</style>"""


# ══════════════════════════════════════════════════
# 格式化工具
# ══════════════════════════════════════════════════

def _fmt_big(n) -> str:
    if n is None:
        return "—"
    if abs(n) >= 1e12:
        return f"{n/1e12:.2f} 万亿"
    if abs(n) >= 1e9:
        return f"{n/1e9:.2f} 亿"
    if abs(n) >= 1e6:
        return f"{n/1e6:.1f} 百万"
    return f"{n:,.0f}"


def _pct(v, signed=True):
    if v is None:
        return "—"
    if signed and v > 0:
        return f"+{v:.1f}%"
    return f"{v:.1f}%"


def _val(v, fmt_spec=".1f"):
    if v is None:
        return "—"
    return f"{v:{fmt_spec}}"


def _tr_rec(key):
    """翻译分析师评级."""
    if not key:
        return "—"
    k = key.lower().replace(" ", "_")
    return _REC_MAP.get(k, key.title())


def _tr_industry(en):
    return _INDUSTRY_CN.get(en, en)


def _tr_sector(en):
    return _SECTOR_CN.get(en, en)


# ══════════════════════════════════════════════════
# 数据拉取
# ══════════════════════════════════════════════════

def _get(df, col_name, col_idx):
    if col_name in df.index:
        v = df.loc[col_name, col_idx]
        return float(v) if v is not None and v == v else None
    return None


def fetch_data(ticker: str) -> dict:
    stock = yf.Ticker(ticker)
    info = stock.info
    quote_type = (info.get("quoteType") or "").upper()
    is_etf = quote_type in ("ETF", "MUTUALFUND")

    # 季度财报
    qf_data = []
    if not is_etf:
        qf = stock.quarterly_financials
        if qf is not None and not qf.empty:
            for col in qf.columns[:4]:
                rev = _get(qf, "Total Revenue", col)
                gp = _get(qf, "Gross Profit", col)
                oi = _get(qf, "Operating Income", col)
                ni = _get(qf, "Net Income", col)
                eps = _get(qf, "Diluted EPS", col)
                ebitda = _get(qf, "EBITDA", col)
                qf_data.append({
                    "date": col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col),
                    "revenue": rev,
                    "gross_margin": (gp / rev * 100) if gp and rev else None,
                    "operating_income": oi,
                    "net_income": ni,
                    "eps": eps,
                    "ebitda": ebitda,
                })

    # 年度收入
    annual_rev = []
    if not is_etf:
        fin = stock.financials
        if fin is not None and not fin.empty and "Total Revenue" in fin.index:
            for col in fin.columns[:5]:
                v = fin.loc["Total Revenue", col]
                if v and v > 0:
                    annual_rev.append({
                        "year": str(col.year) if hasattr(col, "year") else str(col)[:4],
                        "revenue": float(v),
                    })

    # EPS 历史
    eh_data = []
    if not is_etf:
        eh = stock.earnings_history
        if eh is not None and not eh.empty:
            for idx in eh.index[-4:]:
                row = eh.loc[idx]
                eh_data.append({
                    "quarter": str(idx),
                    "eps_actual": float((row.get("epsActual") or 0)),
                    "eps_estimate": float((row.get("epsEstimate") or 0)),
                    "surprise_pct": float((row.get("surprisePercent") or 0)) * 100,
                })

    # 资产负债表
    bs_data = {}
    if not is_etf:
        bs = stock.quarterly_balance_sheet
        if bs is not None and not bs.empty:
            c = bs.columns[0]
            bs_data["cash"] = _get(bs, "Cash And Cash Equivalents", c)
            bs_data["total_debt"] = _get(bs, "Total Debt", c)
            ca = _get(bs, "Current Assets", c)
            cl = _get(bs, "Current Liabilities", c)
            bs_data["current_ratio"] = _get(bs, "Current Ratio", c) or ((ca / cl) if ca and cl else None)
            bs_data["quick_ratio"] = _get(bs, "Quick Ratio", c)
            bs_data["gw_intangibles"] = _get(bs, "Goodwill And Other Intangible Assets", c)
            bs_data["total_assets"] = _get(bs, "Total Assets", c) or 1
            bs_data["equity"] = _get(bs, "Stockholders Equity", c)

    # 现金流
    cf_data = {}
    if not is_etf:
        cf = stock.quarterly_cashflow
        if cf is not None and not cf.empty:
            c = cf.columns[0]
            cf_data["fcf"] = _get(cf, "Free Cash Flow", c)
            cf_data["ocf"] = _get(cf, "Operating Cash Flow", c)
            cf_data["acquisitions"] = _get(cf, "Purchase Of Business", c)
            cf_data["debt_issued"] = _get(cf, "Issuance Of Debt", c)
            cf_data["buyback"] = _get(cf, "Repurchase Of Capital Stock", c)
            cf_data["dividends_paid"] = _get(cf, "Cash Dividends Paid", c)

    # 机构持仓
    inst_holders = []
    try:
        ih = stock.institutional_holders
        if ih is not None and not ih.empty:
            for _, row in ih.head(7).iterrows():
                inst_holders.append({
                    "name": str(row.get("Holder", "")),
                    "pct": float((row.get("pctHeld") or 0)) * 100,
                    "value": float((row.get("Value") or 0)),
                    "change": float((row.get("pctChange") or 0)) * 100,
                })
    except Exception:
        pass

    # 分析师评级
    recs = []
    rec_total = 0
    try:
        r = stock.recommendations
        if r is not None and not r.empty:
            row = r.iloc[0]
            for k in ["strongBuy", "buy", "hold", "sell", "strongSell"]:
                cnt = int((row.get(k) or 0))
                recs.append({"label": k, "count": cnt})
                rec_total += cnt
    except Exception:
        pass

    # ── ETF 特有数据 ──
    etf_data = {}
    if is_etf:
        etf_data["category"] = info.get("category") or "—"
        etf_data["fund_family"] = info.get("fundFamily") or "—"
        etf_data["net_assets"] = info.get("netAssets") or info.get("totalAssets")
        etf_data["expense_ratio"] = (info.get("netExpenseRatio") or 0) * 100 if info.get("netExpenseRatio") is not None else None
        etf_data["inception_date"] = info.get("fundInceptionDate")
        etf_data["nav_price"] = info.get("navPrice")
        etf_data["ytd_return"] = (info.get("ytdReturn") or 0) * 100 if info.get("ytdReturn") is not None else None
        etf_data["return_3m"] = (info.get("trailingThreeMonthReturns") or 0) * 100 if info.get("trailingThreeMonthReturns") is not None else None
        etf_data["return_3y"] = (info.get("threeYearAverageReturn") or 0) * 100 if info.get("threeYearAverageReturn") is not None else None
        etf_data["return_5y"] = (info.get("fiveYearAverageReturn") or 0) * 100 if info.get("fiveYearAverageReturn") is not None else None
        etf_data["beta_3y"] = info.get("beta3Year")
        etf_data["category"] = info.get("category") or "—"

    d = {
        "ticker": ticker,
        "asset_type": "ETF" if is_etf else "STOCK",
        "name": info.get("longName") or info.get("shortName") or ticker,
        "summary": _translate_en_to_zh(info.get("longBusinessSummary") or ""),
        "industry": etf_data.get("category") or _tr_industry(info.get("industry") or "—"),
        "sector": etf_data.get("fund_family") or _tr_sector(info.get("sector") or "—"),
        "market_cap": info.get("marketCap") or etf_data.get("net_assets"),
        "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "target_mean": info.get("targetMeanPrice"),
        "target_high": info.get("targetHighPrice"),
        "target_low": info.get("targetLowPrice"),
        "analyst_count": info.get("numberOfAnalystOpinions"),
        "recommendation": _tr_rec(info.get("recommendationKey") or ""),
        "revenue_growth": (info.get("revenueGrowth") or 0) * 100,
        "earnings_growth": (info.get("earningsGrowth") or 0) * 100,
        "forward_pe": info.get("forwardPE"),
        "trailing_pe": info.get("trailingPE") or info.get("epsTrailingTwelveMonths"),
        "peg_ratio": info.get("pegRatio"),
        "price_to_book": info.get("priceToBook"),
        "ev_revenue": info.get("enterpriseToRevenue"),
        "ev_ebitda": info.get("enterpriseToEbitda"),
        "beta": info.get("beta") or etf_data.get("beta_3y"),
        "total_revenue": info.get("totalRevenue"),
        "ebitda": info.get("ebitda"),
        "profit_margins": (info.get("profitMargins") or 0) * 100 if info.get("profitMargins") is not None else None,
        "gross_margins": (info.get("grossMargins") or 0) * 100 if info.get("grossMargins") is not None else None,
        "ebitda_margins": (info.get("ebitdaMargins") or 0) * 100 if info.get("ebitdaMargins") is not None else None,
        "roe": (info.get("returnOnEquity") or 0) * 100 if info.get("returnOnEquity") is not None else None,
        "roa": (info.get("returnOnAssets") or 0) * 100 if info.get("returnOnAssets") is not None else None,
        "fcf": info.get("freeCashflow"),
        "ocf": info.get("operatingCashflow"),
        "debt_to_equity": info.get("debtToEquity"),
        "total_cash": info.get("totalCash"),
        "total_debt": info.get("totalDebt"),
        "dividend_yield": (info.get("dividendYield") or 0) * 100 if info.get("dividendYield") is not None else None,
        "dividend_rate": info.get("dividendRate"),
        "payout_ratio": (info.get("payoutRatio") or 0) * 100 if info.get("payoutRatio") is not None else None,
        "inst_held_pct": (info.get("heldPercentInstitutions") or 0) * 100 if info.get("heldPercentInstitutions") is not None else None,
        "short_float_pct": (info.get("shortPercentOfFloat") or 0) * 100 if info.get("shortPercentOfFloat") is not None else None,
        "52w_change": (info.get("52WeekChange") or 0) * 100 if info.get("52WeekChange") is not None else None,
        "quarterly_financials": qf_data,
        "annual_revenue": annual_rev,
        "earnings_history": eh_data,
        "balance_sheet": bs_data,
        "cash_flow": cf_data,
        "inst_holders": inst_holders,
        "analyst_recs": recs,
        "rec_total": rec_total,
        "etf_data": etf_data,
    }
    return d


# ══════════════════════════════════════════════════
# StockScope 评分子系统
# ══════════════════════════════════════════════════

def run_stockscope_scoring(ticker: str) -> dict | None:
    """调用 StockScope 评分管线，返回评分结果字典（供 HTML 渲染使用）。"""
    try:
        from stockscope.fetchers.yahoo import YahooClient
        from stockscope.scoring import score_ticker as ss_score_ticker
        from stockscope.config import load_scoring_config

        client = YahooClient(cache_dir=_SRC_DIR.parent / "outputs" / "cache")
        scoring_config = load_scoring_config()
        benchmark_chart = client.fetch_chart("SPY")
        fundamentals = client.fetch_summary(ticker)
        chart = client.fetch_chart(ticker)
        scored = ss_score_ticker(fundamentals, chart, benchmark_chart, config=scoring_config)
        return {
            "entry_score": scored.entry_score,
            "signal": scored.signal,
            "note": scored.note,
            "quality_score": scored.quality_score,
            "valuation_score": scored.valuation_score,
            "trend_score": scored.trend_score,
            "trend_direction": scored.trend_direction,
            "red_flags": scored.red_flags,
            "dividend_type": scored.dividend_type,
            "distance_to_sma60_pct": scored.distance_to_sma60_pct,
            "drawdown_from_high_pct": scored.drawdown_from_high_pct,
            "breakdown": scored.breakdown,
        }
    except Exception as exc:
        print(f"[StockScope 评分] 评分管线异常: {exc}", file=sys.stderr)
        return None


# ══════════════════════════════════════════════════
# HTML 渲染
# ══════════════════════════════════════════════════

def render(data: dict, scored: dict | None = None) -> str:
    d = data
    t = d["ticker"]
    is_etf = d.get("asset_type") == "ETF"
    today = datetime.now().strftime("%Y-%m-%d")

    # ── 季度表格 ──
    q_rows = ""
    for q in d["quarterly_financials"]:
        q_rows += f"""<tr>
            <td><strong>{q['date']}</strong></td>
            <td>{_fmt_big(q['revenue'])}</td>
            <td>{_pct(q['gross_margin'], signed=False)}</td>
            <td>{_fmt_big(q['operating_income'])}</td>
            <td>{_fmt_big(q['net_income'])}</td>
            <td>{_val(q['eps'], '.2f')}</td>
            <td>{_fmt_big(q['ebitda'])}</td>
        </tr>"""

    # ── EPS 历史 ──
    eps_rows = ""
    for e in d["earnings_history"]:
        cls = "highlight" if abs(e["surprise_pct"]) > 10 else ""
        eps_rows += f"""<tr class="{cls}">
            <td>{e['quarter']}</td><td>{e['eps_actual']:.2f}</td>
            <td>{e['eps_estimate']:.2f}</td><td class="val-up"><strong>{_pct(e['surprise_pct'])}</strong></td>
        </tr>"""

    # ── 年度收入 ──
    rev_rows = ""
    prev = None
    for i, ar in enumerate(d["annual_revenue"]):
        g = ""
        if prev:
            gv = (ar["revenue"] - prev) / prev * 100
            g = f'<span class="val-up">+{gv:.1f}%</span>' if gv > 0 else f'<span class="val-down">{gv:.1f}%</span>'
        rev_rows += f'<tr class="{"highlight" if i==0 else ""}"><td>{ar["year"]}</td><td>{_fmt_big(ar["revenue"])}</td><td>{g}</td></tr>'
        prev = ar["revenue"]

    # ── 机构持仓 ──
    inst_rows = ""
    for ih in d["inst_holders"]:
        chg_cls = "val-up" if ih["change"] > 0 else "val-down"
        inst_rows += f"<tr><td>{ih['name']}</td><td>{ih['pct']:.1f}%</td><td>{_fmt_big(ih['value'])}</td><td><span class=\"{chg_cls}\">{ih['change']:+.1f}%</span></td></tr>"

    # ── 分析师分布 ──
    rec_labels_cn = {"strongBuy": "强烈买入", "buy": "买入", "hold": "持有", "sell": "卖出", "strongSell": "强烈卖出"}
    rec_strs = []
    for r in d["analyst_recs"]:
        label = rec_labels_cn.get(r["label"], r["label"])
        rec_strs.append(f"{label}: {r['count']}")
    rec_str = " / ".join(rec_strs) if rec_strs else "暂无数据"

    # ── 资本配置 ──
    cf = d["cash_flow"]
    cf_signals = ""
    if cf.get("acquisitions") and abs(cf["acquisitions"]) > 1e8:
        cf_signals += f"""<div style="background:#0d1117;border-radius:8px;padding:14px;text-align:center;">
            最近季度并购支出:<br><span style="font-size:1.3em;font-weight:700;color:var(--blue);">{_fmt_big(abs(cf['acquisitions']))}</span></div>"""
    if cf.get("debt_issued") and cf["debt_issued"] > 1e8:
        cf_signals += f"""<div style="background:#0d1117;border-radius:8px;padding:14px;text-align:center;">
            最近季度发债:<br><span style="font-size:1.3em;font-weight:700;color:var(--yellow);">{_fmt_big(cf['debt_issued'])}</span></div>"""
    if cf.get("dividends_paid") and abs(cf["dividends_paid"]) > 1e6:
        cf_signals += f"""<div style="background:#0d1117;border-radius:8px;padding:14px;text-align:center;">
            最近季度分红:<br><span style="font-size:1.3em;font-weight:700;color:var(--green);">{_fmt_big(abs(cf['dividends_paid']))}</span></div>"""
    if cf.get("buyback") and abs(cf["buyback"]) > 1e6:
        cf_signals += f"""<div style="background:#0d1117;border-radius:8px;padding:14px;text-align:center;">
            最近季度回购:<br><span style="font-size:1.3em;font-weight:700;color:var(--purple);">{_fmt_big(abs(cf['buyback']))}</span></div>"""
    if not cf_signals:
        cf_signals = '<p style="color:var(--text-secondary);">最近季度未发现大规模并购/发债/分红/回购活动。</p>'

    # ── 一句话定位 ──
    peg = d["peg_ratio"]
    fwd_pe = d["forward_pe"]
    rev_g = d["revenue_growth"]
    earn_g = d["earnings_growth"]

    tagline = ""
    if peg and fwd_pe:
        if peg < 1:
            tagline = f"PEG {peg:.2f}，成长性被市场严重低估，估值与增速严重不匹配。"
        elif peg < 1.5:
            tagline = f"PEG {peg:.2f}，成长性定价合理偏低，兼具进攻与安全边际。"
        elif peg < 2.5:
            tagline = f"PEG {peg:.2f}，估值基本匹配成长性，需跟踪业绩催化剂。"
        else:
            tagline = f"PEG {peg:.2f}，估值偏贵，需确认高增速能否持续。"
    elif fwd_pe:
        if fwd_pe < 15:
            tagline = f"Forward PE {fwd_pe:.1f}x，价值型估值，市场对其成长预期保守。"
        elif fwd_pe < 25:
            tagline = f"Forward PE {fwd_pe:.1f}x，估值合理，处于行业中位水平。"
        else:
            tagline = f"Forward PE {fwd_pe:.1f}x，成长型估值，市场定价了较高的增长预期。"
    else:
        tagline = "数据有限，建议关注后续财报披露。"

    # ── 评级 ──
    verdict_text = "数据不足，无法判断 ⏸"
    if peg and fwd_pe:
        if peg < 0.8:
            verdict_text = "强烈看好 ✅<br>极度低估，重仓配置"
        elif peg < 1.0:
            verdict_text = "看好 ✅<br>性价比突出，偏进攻配置"
        elif peg < 1.5:
            verdict_text = "看好 ✅<br>估值合理偏低，可分批建仓"
        elif peg < 2.0:
            verdict_text = "中性观望 ⏸<br>等待更好买点"
        else:
            verdict_text = "偏贵 ⚠<br>估值充分，追高需谨慎"

    # ── 资产负债 ──
    bs = d["balance_sheet"]
    de = d["debt_to_equity"]
    gw_pct = ((bs.get("gw_intangibles") or 0) / max(bs.get("total_assets", 1) or 1, 1)) * 100
    cr = bs.get("current_ratio")

    # ── 目标价上行 ──
    upside = (d["target_mean"] / d["current_price"] - 1) * 100 if d["target_mean"] and d["current_price"] else None

    # ═══════════════ HTML 模板 ═══════════════
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{t} — {d['name']} 深度分析</title>
{CSS}
</head>
<body>

<header>
  <div class="ticker">{t}</div>
  <h1>{d['name']}</h1>
  <div class="subtitle">{d['industry']} · {d['sector']} · 市值 {_fmt_big(d['market_cap'])}</div>
  <div class="date">报告日期：{today} · 数据来源：Yahoo Finance (yfinance)</div>
</header>

<!-- 1. 公司定位 -->
<section>
  <h2><span class="num">1</span> 公司定位</h2>
  <div class="info-card">
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:8px;">
      <div><strong style="color:var(--text-secondary);">行业</strong><br><span style="font-size:1.05em;">{d['industry']}</span></div>
      <div><strong style="color:var(--text-secondary);">板块</strong><br><span style="font-size:1.05em;">{d['sector']}</span></div>
      <div><strong style="color:var(--text-secondary);">市值</strong><br><span style="font-size:1.05em;">{_fmt_big(d['market_cap'])}</span></div>
      <div><strong style="color:var(--text-secondary);">当前股价</strong><br><span style="font-size:1.05em;">{_val(d['current_price'], '.2f')}</span></div>
    </div>
    <div style="margin-top:14px;">
      <strong style="color:var(--text-secondary);">业务概述</strong>
      <p style="margin-top:4px;">{d['summary']}</p>
    </div>
  </div>
  <div class="quote"><strong>一句话定位：</strong>{tagline}</div>
</section>

<!-- 2. 核心壁垒与竞争优势 -->
{_render_moat_section(d)}

<!-- 3. 核心财务 -->
<section>
  <h2><span class="num">3</span> {"核心数据" if is_etf else "核心财务数据"}</h2>
  {_render_section_2(d, is_etf, q_rows, eps_rows)}
</section>

<!-- 3. 估值分析 -->
<section>
  <h2><span class="num">4</span> 估值分析</h2>
  <div class="metric-grid">
    <div class="metric-card accent"><div class="label">Forward PE（预期市盈率）</div><div class="value">{_val(fwd_pe)}x</div><div class="sub">{'偏低' if fwd_pe and fwd_pe < 15 else '合理' if fwd_pe and fwd_pe < 25 else '偏高' if fwd_pe and fwd_pe >= 25 else ''}</div></div>
    <div class="metric-card good"><div class="label">PEG（市盈率/增长率）</div><div class="value">{_val(peg, '.2f')}</div><div class="sub">{'<1 极度低估' if peg and peg < 1 else '<1.5 合理偏低' if peg and peg < 1.5 else '偏高' if peg and peg >= 2 else ''}</div></div>
    <div class="metric-card {'warn' if d['trailing_pe'] and d['trailing_pe'] > 35 else 'accent'}"><div class="label">Trailing PE（历史市盈率）</div><div class="value">{_val(d['trailing_pe'])}x</div></div>
    <div class="metric-card accent"><div class="label">市净率（P/B）</div><div class="value">{_val(d['price_to_book'])}x</div></div>
    <div class="metric-card accent"><div class="label">EV / 收入</div><div class="value">{_val(d['ev_revenue'], '.2f')}x</div></div>
    <div class="metric-card accent"><div class="label">EV / EBITDA</div><div class="value">{_val(d['ev_ebitda'])}x</div></div>
    <div class="metric-card accent"><div class="label">Beta（波动率）</div><div class="value">{_val(d['beta'], '.2f')}</div></div>
    <div class="metric-card accent"><div class="label">52 周涨跌幅</div><div class="value {'val-up' if d['52w_change'] and d['52w_change'] > 0 else 'val-down'}">{_pct(d['52w_change'])}</div></div>
  </div>
</section>

<!-- 4. 成长性 -->
<section>
  <h2><span class="num">5</span> {"收益表现" if is_etf else "成长性分析"}</h2>
  {_render_section_4(d, is_etf, rev_rows, rev_g, earn_g)}
</section>

<!-- 5. 利润效率 -->
<section>
  <h2><span class="num">6</span> {"费率与收益" if is_etf else "利润与效率指标"}</h2>
  {_render_section_5(d, is_etf)}
</section>

<!-- 6. 资产负债 -->
<section>
  <h2><span class="num">7</span> {"基金概况" if is_etf else "资产负债健康度"}</h2>
  {_render_section_6(d, is_etf)}
</section>

<!-- 7. 资本配置 -->
<section>
  <h2><span class="num">8</span> 资本配置策略</h2>
  {_render_section_7(d, is_etf)}
</section>

<!-- 8. 机构与分析师 -->
<section>
  <h2><span class="num">9</span> 机构持仓 & 分析师共识</h2>
  <div class="grid-2">
    <div>
      <div class="metric-grid" style="grid-template-columns:1fr 1fr;">
        <div class="metric-card good"><div class="label">机构持仓比例</div><div class="value">{_pct(d['inst_held_pct'], signed=False)}</div></div>
        <div class="metric-card good"><div class="label">空头比例</div><div class="value">{_pct(d['short_float_pct'], signed=False)}</div></div>
        <div class="metric-card good"><div class="label">分析师共识</div><div class="value" style="font-size:1.1em;">{d['recommendation']}</div><div class="sub">{d['analyst_count'] or '—'} 位分析师</div></div>
        <div class="metric-card good"><div class="label">平均目标价</div><div class="value val-up">{_val(d['target_mean'], '.2f')}</div><div class="sub val-up">{_pct(upside) if upside else '—'} 上行空间</div></div>
        <div class="metric-card good"><div class="label">最高目标价</div><div class="value">{_val(d['target_high'], '.2f')}</div></div>
        <div class="metric-card warn"><div class="label">最低目标价</div><div class="value">{_val(d['target_low'], '.2f')}</div></div>
        <div class="metric-card accent"><div class="label">分析师分布</div><div class="value" style="font-size:.85em;">{rec_str}</div></div>
      </div>
    </div>
    <div>
      <h3 style="color:#f0f6fc;margin-bottom:10px;">前七大机构持仓</h3>
      <div class="data-table-wrapper">
        <table>
          <thead><tr><th>机构</th><th>比例</th><th>市值</th><th>变动</th></tr></thead>
          <tbody>{inst_rows}</tbody>
        </table>
      </div>
    </div>
  </div>
</section>

<!-- 9. 最终判断 -->
<section>
  <h2><span class="num">10</span> 最终判断</h2>
  <div class="verdict-box">
    <h3>综合评级</h3>
    <div class="big-call">{verdict_text}</div>
    <div style="margin-top:20px;">
      <strong style="color:var(--green);">关键数据摘要：</strong>
      <table style="margin-top:10px;">
        <tr><td style="width:160px;">收入增速</td><td class="val-up"><strong>{_pct(rev_g)}</strong></td></tr>
        <tr><td>利润增速</td><td class="val-up"><strong>{_pct(earn_g)}</strong></td></tr>
        <tr><td>Forward PE / PEG</td><td><strong>{_val(fwd_pe)}x / {_val(peg, '.2f')}</strong></td></tr>
        <tr><td>毛利率 / ROE</td><td><strong>{_pct(d['gross_margins'], signed=False)} / {_pct(d['roe'], signed=False)}</strong></td></tr>
        <tr><td>分析师共识</td><td><strong>{d['recommendation']} · 目标价 {_val(d['target_mean'], '.2f')} ({_pct(upside) if upside else '—'})</strong></td></tr>
        <tr><td>负债权益比</td><td><strong class="{'val-down' if de and de > 100 else ''}">{_val(de)}%</strong></td></tr>
      </table>
    </div>
    <p style="margin-top:16px;font-size:.9em;color:var(--text-secondary);">
      本报告基于 Yahoo Finance (yfinance) 公开数据自动生成，部分指标可能因数据源限制而不完整。不构成投资建议，投资有风险，决策需谨慎。
    </p>
  </div>
</section>

<!-- 10. StockScope 评分框架 -->
{_render_scoring_section(t, scored)}

<footer>
  <p>StockScope 个股深度分析 · 数据来源：Yahoo Finance</p>
  <p>数据截止：{today} · 不构成投资建议 · 投资有风险，决策需谨慎</p>
</footer>

</body>
</html>"""
    return html


def _render_moat_section(d: dict) -> str:
    """渲染第 2 节：商业模式 + 核心壁垒."""
    if d.get("asset_type") == "ETF":
        return """<section>
  <h2><span class="num">2</span> 商业模式与核心壁垒</h2>
  <div class="info-card"><p style="color:var(--text-secondary);">ETF 为被动投资工具，无独立商业模式分析。</p></div>
</section>"""

    name = d["name"]
    industry = d["industry"]
    summary = d.get("summary", "")
    sector = d.get("sector", "")
    gm = d.get("gross_margins")
    pm = d.get("profit_margins")
    roe_val = d.get("roe")
    rev = d.get("total_revenue")
    rev_g = d.get("revenue_growth")
    fcf = d.get("fcf")

    # ── 商业模式拆解 ──
    bm = _analyze_business_model(name, industry, sector, summary, d)

    # ── 量化佐证 ──
    evidence_cards = _build_evidence_cards(d)

    # ── 护城河判断 ──
    moats, strength, moat_desc = _assess_moat(name, industry, sector, summary, d)

    # ── 风险 ──
    risks = _business_risks(name, industry, sector, summary, d)

    # ── 强度标签样式 ──
    strength_css = {"极强": ("var(--green)", "rgba(63,185,80,.15)"),
                    "较强": ("var(--blue)", "rgba(88,166,255,.15)"),
                    "中等": ("var(--yellow)", "rgba(210,153,29,.15)"),
                    "待研判": ("var(--text-secondary)", "rgba(139,148,158,.1)")}
    sc = strength_css.get(strength, strength_css["待研判"])

    return f"""<section>
  <h2><span class="num">2</span> 商业模式与核心壁垒</h2>

  <!-- 商业模式 -->
  <div class="info-card">
    <h3 style="color:#f0f6fc;margin-bottom:10px;">生意怎么做？</h3>
    <p style="line-height:1.9;">{bm}</p>
  </div>

  <!-- 量化信号 -->
  <h3 style="color:#f0f6fc;margin-bottom:8px;">财务数据佐证</h3>
  <div class="metric-grid">
    {evidence_cards}
  </div>

  <!-- 护城河判断 -->
  <div class="info-card" style="margin-top:16px;">
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
      <h3 style="color:#f0f6fc;margin:0;">护城河评估</h3>
      <span style="display:inline-block;padding:4px 14px;border-radius:14px;font-weight:700;font-size:.85em;color:{sc[0]};background:{sc[1]};border:1px solid {sc[0]};">{strength}</span>
    </div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px;">
      {"".join(f'<span class="tag tag-info" style="font-size:.85em;">{m}</span>' for m in moats) if moats else '<span class="tag tag-bear" style="font-size:.85em;">无明显护城河</span>'}
    </div>
    <p style="line-height:1.8;color:var(--text);">{moat_desc}</p>
  </div>

  <!-- 风险 -->
  <div class="info-card" style="margin-top:16px;">
    <h3 style="color:var(--red);margin-bottom:8px;">⚠ 当前面临的风险</h3>
    <ul style="color:var(--text-secondary);padding-left:20px;line-height:1.9;">
      {risks}
    </ul>
  </div>
</section>"""


# ═══════════════════════════════════════
# 商业模式分析引擎
# ═══════════════════════════════════════

# ── 知名公司商业模式知识库 ──
_KNOWN_BUSINESS_MODELS: dict[str, dict] = {
    "GOOGL": {
        "products": ["Google Search（搜索广告）", "YouTube（视频+广告）", "Google Cloud（企业云）",
                     "Android/Chrome（生态入口）", "Gmail/Maps/Drive（用户粘性工具）"],
        "rev_model": "广告收入为核心（~75%），搜索+YouTube双引擎；云服务快速增长；Android/Chrome为免费生态牢笼",
        "moat": "搜索引擎接近全球垄断（90%+份额），用户数据和广告网络的飞轮效应无人能敌。Gmail/YouTube/Android 构成免费工具矩阵，20亿+用户深度依赖，迁移成本极高。云服务虽排第三但增长迅猛。",
        "strength": "极强",
    },
    "GOOG": {
        "products": ["Google Search（搜索广告）", "YouTube（视频+广告）", "Google Cloud（企业云）",
                     "Android/Chrome（生态入口）", "Gmail/Maps/Drive（用户粘性工具）"],
        "rev_model": "广告收入为核心（~75%），搜索+YouTube双引擎；云服务快速增长；Android/Chrome为免费生态牢笼",
        "moat": "搜索引擎接近全球垄断（90%+份额），用户数据和广告网络的飞轮效应无人能敌。Gmail/YouTube/Android 构成免费工具矩阵，20亿+用户深度依赖，迁移成本极高。",
        "strength": "极强",
    },
    "AAPL": {
        "products": ["iPhone（核心现金牛）", "Mac/iPad（生产力工具）", "Services（App Store/Apple Music/iCloud）",
                     "Wearables（AirPods/Apple Watch）"],
        "rev_model": "硬件销售为主（~80%），但服务收入占比持续提升（高毛利订阅）。封闭生态锁定用户，硬件→服务→更强粘性的循环。",
        "moat": "全球最强的消费电子品牌+封闭生态。iOS用户转换到Android的心理和实际成本极高。服务收入（App Store抽成30%、订阅）是印钞机。供应链控制力全球第一。但iPhone收入占比过高是结构性问题。",
        "strength": "极强",
    },
    "MSFT": {
        "products": ["Azure（云基础设施）", "Office 365/Teams（生产力订阅）", "Windows（PC生态）",
                     "LinkedIn（职场社交）", "GitHub/Copilot（开发者生态+AI）"],
        "rev_model": "云+订阅为核心。Azure是第二大云、Office365是全球办公标配、Windows授权+LinkedIn广告+Copilot AI新增长极。",
        "moat": "企业软件最深的护城河：Office→Teams→Azure→Copilot 形成企业工作流闭环，替换任一部分都会破坏整个协作体系。政府和大企业客户粘性极高。OpenAI独家合作加持AI先发优势。",
        "strength": "极强",
    },
    "AMZN": {
        "products": ["AWS（云基础设施全球第一）", "电商零售（自营+第三方）", "Prime会员（订阅+粘性）",
                     "广告（电商搜索广告）"],
        "rev_model": "电商薄利走量+AWS高利润输血。Prime会员锁定消费行为。第三方卖家生态（FBA仓储物流）提供规模壁垒。",
        "moat": "电商+云的独特组合。AWS利润养电商价格战，电商规模养物流基建，形成双轮垄断。Prime会员1.5亿+，续费率极高。仓储物流网络重建成本以千亿计。但零售业务本身利润率极薄（~2-3%），依赖AWS补贴。",
        "strength": "极强",
    },
    "META": {
        "products": ["Facebook/Instagram（社交广告）", "WhatsApp（即时通讯）", "Reels（短视频广告）"],
        "rev_model": "广告收入近乎100%。全球最大的社交注意力池，精准广告投放无可替代。",
        "moat": "全球日活30亿+的社交帝国。广告主无法放弃的用户规模和精准度。Instagram成功卡位TikTok挑战。社交图谱的数据壁垒无法复制。但100%依赖广告收入，商业模式单一且受经济周期影响大。",
        "strength": "极强",
    },
    "NFLX": {
        "products": ["流媒体订阅（核心）", "原创内容制作", "广告层（低价订阅）"],
        "rev_model": "订阅制（月费）。原创内容→吸引订阅→投入更多内容→提升续费率。广告层扩展低价市场。",
        "moat": "全球2.8亿订阅的流媒体先行者。内容推荐算法和制作经验的先发优势。原创内容库规模是最大竞争壁垒。但护城河没有想象中深—用户可根据内容随时切换平台，Disney+/Max/Apple TV+ 竞争白热化，内容成本持续攀升压缩利润。",
        "strength": "较强",
    },
    "NVDA": {
        "products": ["GPU芯片（AI训练/推理）", "CUDA软件生态", "数据中心解决方案", "游戏显卡"],
        "rev_model": "硬件销售。数据中心GPU是绝对核心（AI需求爆炸），CUDA软件生态绑定开发者，形成软硬一体平台。",
        "moat": "AI芯片事实垄断（80%+市场份额）。CUDA生态是最大护城河—开发者已投入十几年学习成本，竞争对手硬件再好也无法替代软件生态。但当前估值已充分定价增长预期，且地缘政治风险日益突出。",
        "strength": "极强",
    },
    "TSLA": {
        "products": ["电动车（Model 3/Y/S/X/Cybertruck）", "FSD自动驾驶软件", "能源存储（Powerwall/Megapack）"],
        "rev_model": "卖车为主，但FSD软件订阅和能源业务是未来利润引擎。直销模式跳过经销商。",
        "moat": "电动车品牌+充电网络+自动驾驶数据的先发壁垒。全球超充网络是竞争对手短期无法复制的基建。但护城河正被快速侵蚀—传统车企和造车新势力全力追赶，中国市场面临激烈价格战，FSD商业化时间表反复推迟。",
        "strength": "较强",
    },
    "TSM": {
        "products": ["先进制程晶圆代工（3nm/5nm/7nm）", "先进封装（CoWoS/3D IC）"],
        "rev_model": "纯代工模式，按晶圆收费。苹果/英伟达/AMD都是客户。技术领先→定价权→高毛利→再投资研发的循环。",
        "moat": "全球唯一的先进芯片代工厂。3nm/5nm制程仅有台积电和三星，台积电良率和产能遥遥领先。建一座先进晶圆厂需200亿+美金和5年+时间，进入门槛极高。但地缘政治风险（台海局势）是其阿喀琉斯之踵。",
        "strength": "极强",
    },
    "APH": {
        "products": ["电气/电子/光纤连接器", "互连系统与传感器", "背板/线束/电缆组件"],
        "rev_model": "B2B 零部件制造。为汽车、航空、通信、军工、工业客户提供关键互连组件。产品单价低但不可或缺，认证壁垒极高（一旦进入客户供应链，替换成本巨大）。",
        "moat": "互连器件市场的隐形冠军。产品深度嵌入客户产品设计（design-in），一旦被采用就会被锁定在整个产品生命周期。覆盖行业极广（汽车+航空+军工+通信+工业），单一行业周期不会致命。全球制造和分销网络是后发者难以复制的竞争壁垒。但本质上仍是零部件代工，产品同质化风险存在，且缺乏品牌溢价能力。",
        "strength": "较强",
        "tags": ["客户锁定", "规模效应", "转换成本"],
    },
}


def _analyze_business_model(name: str, industry: str, sector: str, summary: str, d: dict) -> str:
    """解析商业模式：做什么生意、怎么赚钱、为什么难被替代."""

    # ── 先查知识库 ──
    ticker = d.get("ticker", "")
    kb = _KNOWN_BUSINESS_MODELS.get(ticker, {})

    parts = []

    # 产品矩阵
    if kb.get("products"):
        parts.append(f"<strong>核心产品线：</strong>")
        parts.append(" · ".join(kb["products"]) + "。")
    else:
        products = _extract_products(summary, industry, sector, d)
        if products:
            parts.append(f"<strong>主要业务：</strong>{products}")

    # 收入模式
    parts.append(f"<strong>赚钱方式：</strong>{kb.get('rev_model') or _infer_rev_model(industry, sector, summary, d)}")

    # 规模/地位
    rev = d.get("total_revenue")
    mcap = d.get("market_cap")
    if rev and rev > 100_000_000_000:
        parts.append(f"年收入 {_fmt_big(rev)}、市值 {_fmt_big(mcap)}，属于全球顶级规模企业。")
    elif rev and rev > 10_000_000_000:
        parts.append(f"年收入 {_fmt_big(rev)}，已经跨越规模化门槛。")

    return "".join(f"<span style='display:block;margin-bottom:8px;'>{p}</span>" for p in parts)


def _extract_products(summary: str, industry: str, sector: str, d: dict) -> str:
    """从业务摘要中提取主要产品/服务线（精简版，最多 200 字）."""
    if not summary or len(summary) < 50:
        return ""
    text = summary
    # 尝试取前两个完整句子
    sentences = [s.strip() for s in text.replace("; ", ". ").split(". ") if len(s.strip()) > 30]
    parts = []
    total = 0
    for s in sentences:
        if total + len(s) > 200:
            parts.append(s[:200 - total] + "...")
            break
        parts.append(s)
        total += len(s) + 1
        if len(parts) >= 2:
            break
    if parts:
        return "。".join(parts)
    # 回退：硬截断
    return text[:180] + ("..." if len(text) > 180 else "")


def _infer_rev_model(industry: str, sector: str, summary: str, d: dict) -> str:
    """根据行业推断收入模式."""
    il = industry.lower()
    sl = sector.lower()
    sl_summary = (summary or "").lower()[:300]
    gm = d.get("gross_margins") or 0

    if any(kw in sl_summary for kw in ["subscription", "recurring", "saas", "monthly", "annual fee"]):
        return "订阅/经常性收入模式，客户定期付费，收入可预测性高。"
    if any(kw in il for kw in ["software", "internet", "cloud"]) or any(kw in sl_summary for kw in ["cloud", "platform"]):
        if gm > 60:
            return "软件/平台型收入（高毛利），以订阅或按量付费为主，边际成本极低。"
        return "软件/技术服务收入，以订阅或项目制计费。"
    if any(kw in il for kw in ["advertising", "internet content"]) or "advertising" in sl_summary:
        return "以广告收入为核心，用户免费使用→平台积累注意力→向广告主收费。"
    if any(kw in il for kw in ["bank", "insurance", "capital market", "financial"]):
        return "金融中介模式，赚取息差/佣金/管理费，资产负债表驱动。"
    if any(kw in il for kw in ["semiconductor", "hardware", "electronic", "equipment"]):
        return "硬件/设备销售模式，通过技术领先和规模制造获取溢价。"
    if any(kw in il for kw in ["retail", "e-commerce", "restaurant", "consumer"]):
        return "面向消费者的零售/服务模式，规模效应和品牌是核心。"
    if any(kw in il for kw in ["pharma", "biotech", "drug", "medical"]):
        return "药品/器械销售模式，专利保护和监管批准构成准入壁垒。"
    if any(kw in il for kw in ["oil", "energy", "utility", "mining"]):
        return "资源/能源型模式，资产重、周期性强，资源储量和开采成本决定盈利能力。"
    if any(kw in il for kw in ["aerospace", "defense"]):
        return "政府/大企业合同制，长周期、高门槛，关系和技术并重。"
    if any(kw in il for kw in ["electronic component", "connector", "interconnect", "equipment", "industrial", "machinery", "manufacturing"]):
        return "B2B 制造/销售模式，为下游客户提供关键零部件和子系统，深度绑定客户产品生命周期，替换成本高、认证周期长。"
    if any(kw in il for kw in ["telecom", "communication"]):
        return "通信基础设施销售+服务模式，客户为运营商和大企业，合同周期长、技术认证壁垒高。"
    return "需结合业务概述进一步分析。"


def _build_evidence_cards(d: dict) -> str:
    """构建量化佐证卡片."""
    cards = []
    gm = d.get("gross_margins")
    pm = d.get("profit_margins")
    roe_val = d.get("roe")
    rev_g = d.get("revenue_growth")
    fcf = d.get("fcf")
    rev = d.get("total_revenue")

    if gm is not None:
        level = "good" if gm > 45 else "warn" if gm > 25 else "danger"
        desc = "极强定价权" if gm > 60 else "健康定价能力" if gm > 40 else "行业平均" if gm > 25 else "偏低"
        cards.append(f'<div class="metric-card {level}"><div class="label">毛利率</div><div class="value">{gm:.1f}%</div><div class="sub">{desc}</div></div>')
    if pm is not None:
        level = "good" if pm > 15 else "warn" if pm > 5 else "danger"
        cards.append(f'<div class="metric-card {level}"><div class="label">净利率</div><div class="value">{pm:.1f}%</div><div class="sub">{"印钞机" if pm > 20 else "优秀" if pm > 10 else "一般"}</div></div>')
    if roe_val is not None:
        level = "good" if roe_val > 20 else "warn" if roe_val > 10 else "danger"
        cards.append(f'<div class="metric-card {level}"><div class="label">ROE</div><div class="value">{roe_val:.1f}%</div><div class="sub">{"超额回报" if roe_val > 25 else "良好" if roe_val > 15 else "一般"}</div></div>')
    if rev_g is not None:
        cls = "val-up" if rev_g > 0 else "val-down"
        cards.append(f'<div class="metric-card good"><div class="label">收入增速</div><div class="value {cls}">{rev_g:+.1f}%</div><div class="sub">{"高速增长" if rev_g > 15 else "稳健" if rev_g > 5 else "放缓"}</div></div>')
    if fcf is not None:
        level = "good" if fcf > 0 else "danger"
        cards.append(f'<div class="metric-card {level}"><div class="label">自由现金流</div><div class="value">{_fmt_big(fcf)}</div><div class="sub">{"真金白银" if fcf and fcf > 1e9 else "注意现金流" if fcf and fcf < 0 else ""}</div></div>')
    if rev is not None and rev > 1e9:
        cards.append(f'<div class="metric-card accent"><div class="label">年收入规模</div><div class="value">{_fmt_big(rev)}</div><div class="sub">{"巨头" if rev > 100e9 else "大型" if rev > 10e9 else "中型"}</div></div>')

    return "".join(cards) if cards else '<div class="metric-card accent"><div class="label">数据有限</div><div class="value">—</div></div>'


def _assess_moat(name: str, industry: str, sector: str, summary: str, d: dict) -> tuple[list[str], str, str]:
    """评估护城河：返回 (标签列表, 强度, 详细描述)."""
    ticker = d.get("ticker", "")
    gm = d.get("gross_margins") or 0
    pm = d.get("profit_margins") or 0
    roe_val = d.get("roe") or 0
    rev = d.get("total_revenue") or 0

    # ── 先查知识库 ──
    kb = _KNOWN_BUSINESS_MODELS.get(ticker, {})
    if kb.get("moat"):
        tags = kb.get("tags") or _extract_moat_tags(kb["moat"])
        strength = kb.get("strength") or _infer_strength_from_tags(tags, gm, roe_val, rev)
        desc = kb["moat"]
        return tags, strength, desc

    # ── 没有知识库 → 从行业和财务数据推断 ──
    tags, desc = _infer_moat_from_data(name, industry, summary, d)
    strength = _infer_strength_from_tags(tags, gm, roe_val, rev)
    return tags, strength, desc


def _extract_moat_tags(moat_text: str) -> list[str]:
    """从护城河描述中提取标签."""
    tags = []
    mapping = [
        ("垄断", "市场垄断"), ("份额", "市场份额"), ("生态", "生态锁定"), ("闭环", "生态锁定"),
        ("网络效应", "网络效应"), ("飞轮", "飞轮效应"), ("平台", "平台效应"),
        ("品牌", "品牌壁垒"), ("数据", "数据壁垒"), ("专利", "技术壁垒"),
        ("技术", "技术壁垒"), ("IP", "技术壁垒"), ("规模", "规模效应"),
        ("成本", "成本优势"), ("体量", "规模效应"), ("切换", "转换成本"),
        ("迁移", "转换成本"), ("替换", "转换成本"), ("监管", "监管壁垒"),
        ("牌照", "监管壁垒"), ("合规", "监管壁垒"), ("design-in", "客户锁定"),
    ]
    for keyword, tag in mapping:
        if keyword in moat_text and tag not in tags:
            tags.append(tag)
    return tags[:5] if tags else ["综合壁垒"]


def _infer_strength_from_tags(tags: list[str], gm: float, roe: float, rev: float) -> str:
    """根据标签和财务数据判断护城河强度."""
    strong_tags = {"市场垄断", "网络效应", "生态锁定", "飞轮效应"}
    medium_tags = {"技术壁垒", "品牌壁垒", "转换成本", "监管壁垒", "客户锁定"}
    weak_indicator = (gm < 25 or roe < 8 or rev < 500_000_000)

    strong_count = len([t for t in tags if t in strong_tags])
    medium_count = len([t for t in tags if t in medium_tags])

    if strong_count >= 2 and not weak_indicator:
        return "极强"
    if strong_count >= 1 or medium_count >= 2:
        return "较强" if not weak_indicator else "中等"
    if medium_count >= 1:
        return "中等"
    if gm > 40 and roe > 15:
        return "较强"
    if gm > 25 and roe > 10:
        return "中等"
    return "待研判"


def _infer_moat_from_data(name: str, industry: str, summary: str, d: dict) -> tuple[list[str], str]:
    """没有知识库时，从行业+财务推断护城河."""
    il = industry.lower()
    sl = (summary or "").lower()[:300]
    gm = d.get("gross_margins") or 0
    pm = d.get("profit_margins") or 0
    roe_val = d.get("roe") or 0
    rev = d.get("total_revenue") or 0
    de = d.get("debt_to_equity") or 0

    tags = []
    desc_parts = [f"{name} 属于 {industry} 行业。"]

    # 转换成本判断
    if any(kw in il for kw in ["software", "saas", "cloud", "enterprise", "bank", "payment", "insurance", "broker", "data"]):
        tags.append("转换成本")
        desc_parts.append("产品深度融入客户工作流，替换成本高。")
    elif any(kw in il for kw in ["electronic component", "connector", "interconnect", "equipment", "industrial", "machinery"]):
        tags.append("客户锁定")
        desc_parts.append("产品通过 design-in 嵌入客户供应链，认证周期长、替换意愿低。")

    # 品牌/网络效应
    if any(kw in il for kw in ["internet content", "social", "marketplace", "platform", "e-commerce", "advertising"]):
        tags.append("网络效应")
        desc_parts.append("平台模式具有天然的规模自我强化特性。")
    if any(kw in il for kw in ["beverage", "luxury", "restaurant", "apparel", "cosmetic", "retail"]):
        tags.append("品牌壁垒")
        desc_parts.append("消费者品牌认知度是重要护城河。")

    # 技术/专利
    if any(kw in il for kw in ["semiconductor", "pharma", "biotech", "medical device", "aerospace", "defense", "drug"]):
        tags.append("技术壁垒")
        desc_parts.append("核心技术依赖长期研发和专利保护。")

    # 监管
    if any(kw in il for kw in ["bank", "insurance", "utility", "telecom", "railroad"]):
        tags.append("监管壁垒")
        desc_parts.append("行业准入受严格监管，牌照稀缺。")

    # 规模化
    if rev > 20e9:
        tags.append("规模效应")
        desc_parts.append(f"年收入 {_fmt_big(rev)} 的庞大体量构成结构性成本优势。")
    elif rev > 5e9 and gm > 40:
        tags.append("规模效应")
        desc_parts.append("已跨越规模化门槛，具备一定的成本优势。")

    # 财务验证
    if gm > 50:
        desc_parts.append(f"毛利率 {gm:.1f}% 处于高位，反映出较强的定价权或成本结构优势。")
    else:
        desc_parts.append(f"毛利率 {gm:.1f}%，在所处行业中属于{'较优' if gm > 35 else '一般' if gm > 20 else '偏低'}水平。")
    if roe_val > 20:
        desc_parts.append(f"ROE {roe_val:.1f}% 验证了管理层对股东资本的高效运用。")
    elif roe_val > 10:
        desc_parts.append(f"ROE {roe_val:.1f}%，资本回报尚可但未达到'护城河级'水平。")
    else:
        desc_parts.append(f"ROE {roe_val:.1f}% 偏低，可能表明缺乏显著竞争壁垒或处于重资产行业。")

    # 诚实结论
    if not tags:
        tags.append("无明显护城河")
        desc_parts.append("综合来看，该公司所在行业竞争较为充分，暂未发现显著的、难以复制的结构性优势。但这不意味着公司经营不佳，只是缺乏传统意义上的'护城河'特征。")

    return tags, " ".join(desc_parts)


def _business_risks(name: str, industry: str, sector: str, summary: str, d: dict) -> str:
    """生成具体业务风险."""
    # 知识库中如有特定风险，优先使用
    ticker = d.get("ticker", "")
    kb_risks = {
        "GOOGL": ["<strong>反垄断：</strong>美欧持续施压，可能被迫拆分广告业务或改变默认搜索引擎协议。",
                  "<strong>AI 颠覆搜索：</strong>ChatGPT 等 AI 问答可能分流传统搜索流量，广告模式面临重构。",
                  "<strong>广告周期：</strong>广告收入受宏观经济周期影响大，衰退期客户削减预算。"],
        "GOOG": ["<strong>反垄断：</strong>美欧持续施压，可能被迫拆分广告业务。",
                 "<strong>AI 颠覆搜索：</strong>AI 问答可能分流传统搜索流量。"],
        "AAPL": ["<strong>iPhone 依赖：</strong>过半收入来自 iPhone，智能手机市场饱和是最大风险。",
                 "<strong>中国供应链/市场：</strong>地缘政治风险，生产和销售两端都受影响。",
                 "<strong>监管压力：</strong>App Store 抽成模式被欧盟 DMA 法案挑战。"],
        "MSFT": ["<strong>AI 投入回报不确定：</strong>巨额 AI 基础设施投资，商业化前景尚需验证。",
                 "<strong>云竞争：</strong>AWS 领先、Google Cloud 追赶，价格战可能压缩利润率。"],
        "AMZN": ["<strong>电商利润率薄：</strong>零售业务利润极低（~2-3%），严重依赖 AWS 输血。",
                 "<strong>反垄断：</strong>FTC 已起诉亚马逊，指控其利用垄断地位压制第三方卖家。"],
        "META": ["<strong>广告依赖：</strong>近乎 100% 收入来自广告，经济周期敏感。",
                 "<strong>隐私政策：</strong>Apple ATT 等隐私政策持续削弱广告精准度。",
                 "<strong>TikTok 竞争：</strong>短视频争夺用户时长和广告预算。"],
        "NFLX": ["<strong>流媒体内卷：</strong>Disney+/Max/Prime Video/Apple TV+ 激烈竞争，内容成本持续攀升。",
                 "<strong>订阅天花板：</strong>核心市场渗透率已高，增长越来越依赖新兴市场低价套餐。"],
        "NVDA": ["<strong>AI 投资周期：</strong>如果企业 AI 支出放缓，GPU 需求可能骤降。",
                 "<strong>竞争：</strong>AMD/Intel/自研芯片（Google TPU/AWS Trainium）威胁市场份额。",
                 "<strong>估值泡沫：</strong>市场已定价极高的增长预期，任何不及预期都可能导致剧烈回调。"],
        "TSLA": ["<strong>需求放缓：</strong>电动车市场竞争白热化，降价促销压缩利润率。",
                 "<strong>马斯克风险：</strong>创始人行为和言论可能影响品牌形象和消费者信心。",
                 "<strong>FSD 兑现风险：</strong>完全自动驾驶的商业化时间表反复推迟。"],
        "TSM": ["<strong>地缘政治：</strong>台湾海峡紧张局势是台积电最大风险，一旦冲突将切断全球芯片供应。",
                "<strong>客户集中：</strong>苹果和英伟达占收入过大比例，任一客户流失都影响重大。"],
        "APH": ["<strong>客户订单波动：</strong>作为零部件供应商，客户库存调整和终端需求变化会直接冲击订单量。",
                "<strong>行业竞争：</strong>连接器市场虽然认证门槛高，但并非独家——TE Connectivity、Molex 等对手同样实力强劲。",
                "<strong>汽车电子化依赖：</strong>汽车业务增长的核心逻辑是电动化/智能化，如果进展不及预期，增长引擎会熄火。",
                "<strong>收购整合：</strong>安费诺历史上靠大量收购做大规模，整合失败或商誉减值风险始终存在。"],
    }
    if kb_risks.get(ticker):
        return "\n".join(f"<li>{r}</li>" for r in kb_risks[ticker])

    # 通用风险推断
    risks = []
    il = industry.lower()
    de = d.get("debt_to_equity")

    if any(kw in il for kw in ["tech", "software", "internet", "semiconductor"]):
        risks.append("<strong>技术迭代风险：</strong>技术路线或商业模式变化可能快速侵蚀现有优势。")
    if any(kw in il for kw in ["consumer", "retail", "restaurant", "entertainment"]):
        risks.append("<strong>消费者偏好变化：</strong>品牌或产品可能因代际更替或潮流变迁而失宠。")
    if any(kw in il for kw in ["pharma", "biotech", "drug"]):
        risks.append("<strong>专利悬崖：</strong>核心产品专利到期后仿制药或生物类似药将冲击收入。")
    if any(kw in il for kw in ["financial", "bank", "insurance"]):
        risks.append("<strong>金融周期：</strong>利率变化、信贷周期和系统性风险直接影响盈利能力。")
    if any(kw in il for kw in ["energy", "oil", "mining"]):
        risks.append("<strong>价格波动：</strong>大宗商品价格受全球供需和地缘政治影响，企业无法控制。")
    if de is not None and de > 100:
        risks.append(f"<strong>杠杆风险：</strong>负债权益比 {de:.0f}%，高杠杆在经济下行时风险放大。")

    # 补充财务数据驱动的风险信号
    if len(risks) < 2:
        rev_g = d.get("revenue_growth") or 0
        gm = d.get("gross_margins") or 0
        pm = d.get("profit_margins") or 0
        if rev_g < 3 and rev_g is not None:
            risks.append(f"<strong>增长乏力：</strong>收入增速仅 {rev_g:.1f}%，可能面临市场份额流失或行业天花板。")
        if gm < 20 and gm > 0:
            risks.append(f"<strong>利润微薄：</strong>毛利率仅 {gm:.1f}%，原材料、人工、运费的任何波动都可能严重冲击利润。")
        if pm is not None and pm < 5 and pm > 0:
            risks.append(f"<strong>盈利脆弱：</strong>净利率仅 {pm:.1f}%，容错空间极小。")

    return "\n".join(f"<li>{r}</li>" for r in risks)


def _render_section_2(d: dict, is_etf: bool, q_rows: str, eps_rows: str) -> str:
    """渲染第 2 节：核心财务 / ETF 概览."""
    if not is_etf:
        return f"""<h3>季度趋势（最近 4 季）</h3>
  <div class="data-table-wrapper"><table>
    <thead><tr><th>季度</th><th>收入</th><th>毛利率</th><th>营业利润</th><th>净利润</th><th>稀释 EPS</th><th>EBITDA</th></tr></thead>
    <tbody>{q_rows}</tbody>
  </table></div>
  <h3>EPS 超预期记录</h3>
  <div class="data-table-wrapper"><table>
    <thead><tr><th>季度</th><th>EPS 实际</th><th>EPS 预期</th><th>超预期幅度</th></tr></thead>
    <tbody>{eps_rows}</tbody>
  </table></div>"""
    ed = d.get("etf_data", {})
    items = []
    if ed.get("net_assets"):
        items.append(f'<div class="metric-card good"><div class="label">净资产规模</div><div class="value">{_fmt_big(ed["net_assets"])}</div></div>')
    if ed.get("expense_ratio") is not None:
        items.append(f'<div class="metric-card good"><div class="label">费率</div><div class="value">{ed["expense_ratio"]:.2f}%</div></div>')
    if ed.get("nav_price"):
        items.append(f'<div class="metric-card accent"><div class="label">NAV 净值</div><div class="value">{_val(ed["nav_price"], ".2f")}</div></div>')
    if ed.get("inception_date"):
        import datetime as _dt
        try:
            dt_str = _dt.datetime.fromtimestamp(ed["inception_date"]).strftime("%Y-%m-%d")
            items.append(f'<div class="metric-card accent"><div class="label">成立日期</div><div class="value" style="font-size:1em;">{dt_str}</div></div>')
        except Exception:
            pass
    ytd = ed.get("ytd_return")
    r3m = ed.get("return_3m")
    r3y = ed.get("return_3y")
    r5y = ed.get("return_5y")
    returns_html = ""
    for label, val in [("年初至今", ytd), ("近 3 月", r3m), ("近 3 年（年化）", r3y), ("近 5 年（年化）", r5y)]:
        if val is not None:
            cls = "val-up" if val > 0 else "val-down"
            returns_html += f'<tr><td>{label}</td><td class="{cls}"><strong>{_pct(val)}</strong></td></tr>'
    ret_table = ""
    if returns_html:
        ret_table = f"""<h3>历史收益</h3>
  <div class="data-table-wrapper"><table>
    <thead><tr><th>周期</th><th>收益</th></tr></thead>
    <tbody>{returns_html}</tbody>
  </table></div>"""
    return f"""<div class="metric-grid">{''.join(items)}</div>
  {ret_table}"""


def _render_section_4(d: dict, is_etf: bool, rev_rows: str, rev_g, earn_g) -> str:
    """渲染第 4 节：成长性分析."""
    if is_etf:
        ed = d.get("etf_data", {})
        cards = []
        for label, val in [("年初至今", ed.get("ytd_return")), ("近 3 月", ed.get("return_3m")),
                           ("近 3 年（年化）", ed.get("return_3y")), ("近 5 年（年化）", ed.get("return_5y"))]:
            if val is not None:
                cls = "val-up" if val > 0 else "val-down"
                cards.append(f'<div class="metric-card good"><div class="label">{label}</div><div class="value {cls}">{_pct(val)}</div></div>')
        return f"""<div class="info-card"><p style="color:var(--text-secondary);">ETF 无独立营收数据，以下为历史收益表现。</p></div>
  <div class="metric-grid">{''.join(cards) if cards else '<div class="metric-card accent"><div class="label">暂无数据</div><div class="value">—</div></div>'}</div>"""
    return f"""<h3>年度收入趋势</h3>
  <div class="data-table-wrapper"><table>
    <thead><tr><th>财年</th><th>收入</th><th>增速</th></tr></thead>
    <tbody>{rev_rows}</tbody>
  </table></div>
  <div class="metric-grid">
    <div class="metric-card good"><div class="label">收入增速（同比）</div><div class="value {'val-up' if rev_g and rev_g > 0 else 'val-down'}">{_pct(rev_g)}</div></div>
    <div class="metric-card good"><div class="label">利润增速（同比）</div><div class="value {'val-up' if earn_g and earn_g > 0 else 'val-down'}">{_pct(earn_g)}</div></div>
  </div>"""


def _render_section_5(d: dict, is_etf: bool) -> str:
    """渲染第 5 节：利润与效率指标."""
    if is_etf:
        ed = d.get("etf_data", {})
        cards = []
        for label, val in [("费率", ed.get("expense_ratio")), ("股息率", d.get("dividend_yield")),
                           ("Beta (3Y)", ed.get("beta_3y")), ("净资产", ed.get("net_assets"))]:
            if val is not None:
                if label == "净资产":
                    cards.append(f'<div class="metric-card accent"><div class="label">{label}</div><div class="value" style="font-size:1em;">{_fmt_big(val)}</div></div>')
                elif label == "费率":
                    cards.append(f'<div class="metric-card good"><div class="label">{label}</div><div class="value">{val:.2f}%</div><div class="sub">越低越好</div></div>')
                elif label == "Beta (3Y)":
                    cards.append(f'<div class="metric-card accent"><div class="label">{label}</div><div class="value">{val:.2f}</div></div>')
                else:
                    cards.append(f'<div class="metric-card good"><div class="label">{label}</div><div class="value">{_pct(val, signed=False)}</div></div>')
        if not cards:
            return '<div class="info-card"><p style="color:var(--text-secondary);">暂无 ETF 专项数据。</p></div>'
        return f'<div class="metric-grid">{"".join(cards)}</div>'
    return f"""<div class="metric-grid">
    <div class="metric-card good"><div class="label">净利润率</div><div class="value">{_pct(d['profit_margins'], signed=False)}</div></div>
    <div class="metric-card good"><div class="label">毛利率</div><div class="value">{_pct(d['gross_margins'], signed=False)}</div></div>
    <div class="metric-card good"><div class="label">EBITDA 利润率</div><div class="value">{_pct(d['ebitda_margins'], signed=False)}</div></div>
    <div class="metric-card good"><div class="label">ROE（净资产收益率）</div><div class="value">{_pct(d['roe'], signed=False)}</div></div>
    <div class="metric-card accent"><div class="label">ROA（总资产收益率）</div><div class="value">{_pct(d['roa'], signed=False)}</div></div>
    <div class="metric-card good"><div class="label">自由现金流</div><div class="value">{_fmt_big(d['fcf'])}</div></div>
    <div class="metric-card good"><div class="label">经营现金流</div><div class="value">{_fmt_big(d['ocf'])}</div></div>
    <div class="metric-card accent"><div class="label">分红率</div><div class="value">{_pct(d['payout_ratio'], signed=False)}</div></div>
    <div class="metric-card accent"><div class="label">股息率</div><div class="value">{_pct(d['dividend_yield'], signed=False)}</div></div>
  </div>"""


def _render_section_6(d: dict, is_etf: bool) -> str:
    """渲染第 6 节：资产负债健康度."""
    if is_etf:
        ed = d.get("etf_data", {})
        cards = []
        if ed.get("net_assets"):
            cards.append(f'<div class="metric-card accent"><div class="label">净资产规模</div><div class="value">{_fmt_big(ed["net_assets"])}</div></div>')
        if ed.get("fund_family"):
            cards.append(f'<div class="metric-card accent"><div class="label">基金家族</div><div class="value" style="font-size:1em;">{ed["fund_family"]}</div></div>')
        if ed.get("category"):
            cards.append(f'<div class="metric-card accent"><div class="label">投资类别</div><div class="value" style="font-size:1em;">{ed["category"]}</div></div>')
        if not cards:
            return '<div class="info-card"><p style="color:var(--text-secondary);">暂无 ETF 资产负债数据。</p></div>'
        return f'<div class="metric-grid">{"".join(cards)}</div>'
    bs = d["balance_sheet"]
    de = d["debt_to_equity"]
    gw_pct = ((bs.get("gw_intangibles") or 0) / max(bs.get("total_assets", 1) or 1, 1)) * 100
    cr = bs.get("current_ratio")
    return f"""<div class="metric-grid">
    <div class="metric-card accent"><div class="label">现金</div><div class="value">{_fmt_big(d['total_cash'])}</div></div>
    <div class="metric-card {'warn' if d['total_debt'] and d['total_cash'] and d['total_debt'] > d['total_cash'] else 'accent'}"><div class="label">总负债</div><div class="value">{_fmt_big(d['total_debt'])}</div></div>
    <div class="metric-card {'danger' if de and de > 100 else 'warn' if de and de > 50 else 'good'}"><div class="label">负债权益比（D/E）</div><div class="value">{_val(de)}%</div><div class="sub">{'偏高' if de and de > 100 else '偏高' if de and de > 50 else '健康' if de else ''}</div></div>
    <div class="metric-card {'good' if cr and cr > 1.5 else 'warn' if cr else 'accent'}"><div class="label">流动比率</div><div class="value">{_val(cr, '.2f')}</div></div>
    <div class="metric-card {'good' if bs.get('quick_ratio') and bs['quick_ratio'] > 1 else 'warn' if bs.get('quick_ratio') else 'accent'}"><div class="label">速动比率</div><div class="value">{_val(bs.get('quick_ratio'), '.2f')}</div></div>
    <div class="metric-card {'warn' if gw_pct > 30 else 'accent'}"><div class="label">商誉 + 无形资产</div><div class="value">{_fmt_big(bs.get('gw_intangibles'))}</div><div class="sub">占总资产 {gw_pct:.0f}%</div></div>
  </div>"""


def _render_section_7(d: dict, is_etf: bool) -> str:
    """渲染第 7 节：资本配置策略."""
    if is_etf:
        return '<div class="info-card"><p style="color:var(--text-secondary);">ETF 由基金管理人统一配置，无独立资本配置数据。</p></div>'
    cf = d["cash_flow"]
    cf_signals = ""
    if cf.get("acquisitions") and abs(cf["acquisitions"]) > 1e8:
        cf_signals += f"""<div style="background:#0d1117;border-radius:8px;padding:14px;text-align:center;">
            最近季度并购支出:<br><span style="font-size:1.3em;font-weight:700;color:var(--blue);">{_fmt_big(abs(cf['acquisitions']))}</span></div>"""
    if cf.get("debt_issued") and cf["debt_issued"] > 1e8:
        cf_signals += f"""<div style="background:#0d1117;border-radius:8px;padding:14px;text-align:center;">
            最近季度发债:<br><span style="font-size:1.3em;font-weight:700;color:var(--yellow);">{_fmt_big(cf['debt_issued'])}</span></div>"""
    if cf.get("dividends_paid") and abs(cf["dividends_paid"]) > 1e6:
        cf_signals += f"""<div style="background:#0d1117;border-radius:8px;padding:14px;text-align:center;">
            最近季度分红:<br><span style="font-size:1.3em;font-weight:700;color:var(--green);">{_fmt_big(abs(cf['dividends_paid']))}</span></div>"""
    if cf.get("buyback") and abs(cf["buyback"]) > 1e6:
        cf_signals += f"""<div style="background:#0d1117;border-radius:8px;padding:14px;text-align:center;">
            最近季度回购:<br><span style="font-size:1.3em;font-weight:700;color:var(--purple);">{_fmt_big(abs(cf['buyback']))}</span></div>"""
    if not cf_signals:
        cf_signals = '<p style="color:var(--text-secondary);">最近季度未发现大规模并购/发债/分红/回购活动。</p>'
    return f"""<div class="info-card">
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;">{cf_signals}</div>
  </div>"""


def _render_scoring_section(ticker: str, scored: dict | None) -> str:
    """渲染 StockScope 评分框架 HTML 片段。"""
    if not scored:
        return """<section>
  <h2><span class="num">11</span> StockScope 评分框架（如何选股）</h2>
  <div class="info-card" style="text-align:center;color:var(--text-secondary);padding:40px;">
    评分数据获取失败，请检查网络后重试。
  </div>
</section>"""

    # ── 时钟方向中文 ──
    clock_map = {
        "strong_uptrend": "1点钟（强势多头）",
        "confirmed_uptrend": "2点钟（最佳买入）",
        "mixed": "3点钟（犹豫）",
        "downtrend": "4-6点钟（下跌）",
    }
    clock_label = clock_map.get(scored.get("trend_direction", ""), "未知")

    # ── 信号颜色 ──
    sig = scored["signal"]
    sig_color = {"A": "#3fb950", "B": "#58a6ff", "C": "#d2991d", "D": "#f85149"}.get(sig, "#8b949e")

    # ── 红牌标签 ──
    red_flag_labels = {
        "negative_ocf": "经营现金流为负",
        "story_driven": "故事驱动型（EBIT < 0 且 OCF ≤ 0）",
        "negative_fcf": "自由现金流为负",
        "small_revenue": "收入规模过小",
    }
    red_flags_raw = scored.get("red_flags", "")
    red_flags_list = [f.strip() for f in red_flags_raw.split(",") if f.strip()] if red_flags_raw else []

    # ── 拆解明细渲染 ──
    bd = scored.get("breakdown")
    if bd is None:
        quality_rows = valuation_rows = trend_rows = adjust_rows = "<tr><td colspan='4' style='color:var(--text-secondary);'>无拆解数据</td></tr>"
        q_total = v_total = t_total = 0
    else:
        q_items = bd.quality_items if hasattr(bd, "quality_items") else []
        q_total = sum(item.score for item in q_items) + (bd.quality_base if hasattr(bd, "quality_base") else 50)
        quality_rows = ""
        for item in q_items:
            cls = "val-up" if item.score > 0 else "val-down" if item.score < 0 else ""
            quality_rows += f"<tr><td>{item.factor}</td><td>{item.value}</td><td class=\"{cls}\">{item.score:+d}</td><td style=\"font-size:.8em;color:var(--text-secondary);\">{item.detail}</td></tr>"

        v_items = bd.valuation_items if hasattr(bd, "valuation_items") else []
        v_total = sum(item.score for item in v_items) + (bd.valuation_base if hasattr(bd, "valuation_base") else 50)
        valuation_rows = ""
        for item in v_items:
            cls = "val-up" if item.score > 0 else "val-down" if item.score < 0 else ""
            valuation_rows += f"<tr><td>{item.factor}</td><td>{item.value}</td><td class=\"{cls}\">{item.score:+d}</td><td style=\"font-size:.8em;color:var(--text-secondary);\">{item.detail}</td></tr>"

        t_items = bd.trend_items if hasattr(bd, "trend_items") else []
        t_total = sum(item.score for item in t_items) + (bd.trend_base if hasattr(bd, "trend_base") else 50)
        trend_rows = ""
        for item in t_items:
            cls = "val-up" if item.score > 0 else "val-down" if item.score < 0 else ""
            trend_rows += f"<tr><td>{item.factor}</td><td>{item.value}</td><td class=\"{cls}\">{item.score:+d}</td><td style=\"font-size:.8em;color:var(--text-secondary);\">{item.detail}</td></tr>"

        adjust_items = bd.adjustments if hasattr(bd, "adjustments") else []
        adjust_rows = ""
        for item in adjust_items:
            cls = "val-up" if item.score > 0 else "val-down" if item.score < 0 else ""
            adjust_rows += f"<tr><td>{item.factor}</td><td>{item.value}</td><td class=\"{cls}\">{item.score:+d}</td><td style=\"font-size:.8em;color:var(--text-secondary);\">{item.detail}</td></tr>"
        if not adjust_items:
            adjust_rows = '<tr><td colspan="4" style="color:var(--text-secondary);">无需修正</td></tr>'

    # ── 入场分公式 ──
    formula = getattr(bd, "entry_formula", "") if bd else ""

    # ── 距离 60 日线 ──
    dist_60 = scored.get("distance_to_sma60_pct")
    dist_60_str = f"{dist_60:+.1%}" if dist_60 is not None else "—"

    # ── 回撤 ──
    dd = scored.get("drawdown_from_high_pct")
    dd_str = f"{dd:+.1%}" if dd is not None else "—"

    return f"""<section>
  <h2><span class="num">11</span> StockScope 评分框架（如何选股）</h2>

  <!-- 综合信号 -->
  <div style="background:var(--card-bg);border:1px solid var(--border);border-radius:10px;padding:24px;margin-bottom:20px;display:flex;align-items:center;gap:24px;flex-wrap:wrap;">
    <div style="text-align:center;min-width:120px;">
      <div style="font-size:.85em;color:var(--text-secondary);margin-bottom:6px;">信号等级</div>
      <div style="font-size:4em;font-weight:900;color:{sig_color};line-height:1;">{sig}</div>
    </div>
    <div style="flex:1;min-width:200px;">
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(100px,1fr));gap:12px;">
        <div style="text-align:center;">
          <div style="font-size:.8em;color:var(--text-secondary);">入场分</div>
          <div style="font-size:2em;font-weight:700;color:#f0f6fc;">{scored['entry_score']}</div>
        </div>
        <div style="text-align:center;">
          <div style="font-size:.8em;color:var(--text-secondary);">质量分</div>
          <div style="font-size:1.5em;font-weight:700;color:#f0f6fc;">{scored['quality_score'] or '—'}</div>
        </div>
        <div style="text-align:center;">
          <div style="font-size:.8em;color:var(--text-secondary);">估值分</div>
          <div style="font-size:1.5em;font-weight:700;color:#f0f6fc;">{scored['valuation_score']}</div>
        </div>
        <div style="text-align:center;">
          <div style="font-size:.8em;color:var(--text-secondary);">趋势分</div>
          <div style="font-size:1.5em;font-weight:700;color:#f0f6fc;">{scored['trend_score']}</div>
        </div>
        <div style="text-align:center;">
          <div style="font-size:.8em;color:var(--text-secondary);">趋势方向</div>
          <div style="font-size:1.1em;font-weight:700;color:var(--blue);">{clock_label}</div>
        </div>
        <div style="text-align:center;">
          <div style="font-size:.8em;color:var(--text-secondary);">分红类型</div>
          <div style="font-size:1.1em;font-weight:700;color:var(--purple);">{scored.get('dividend_type', '—')}</div>
        </div>
      </div>
      <div style="margin-top:10px;font-size:.85em;color:var(--text-secondary);">
        距60日线 <span style="color:{'var(--green)' if dist_60 and abs(dist_60) < 0.03 else 'var(--yellow)' if dist_60 and abs(dist_60) < 0.10 else 'var(--red)'};font-weight:600;">{dist_60_str}</span>
        · 52周回撤 <span style="color:{'var(--green)' if dd and dd > -0.10 else 'var(--yellow)' if dd and dd > -0.25 else 'var(--red)'};font-weight:600;">{dd_str}</span>
      </div>
    </div>
  </div>

  <!-- 评分基准参考 -->
  <div class="info-card" style="margin-bottom:20px;">
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px;cursor:pointer;" onclick="document.getElementById('ref-table').style.display=document.getElementById('ref-table').style.display==='none'?'block':'none'">
      <span style="font-size:1.1em;">📊</span><strong style="color:#f0f6fc;">评分基准参考（点击展开/收起）</strong>
      <span style="font-size:.8em;color:var(--text-secondary);">— 各分数段含义 & 关键因子及格线</span>
    </div>
    <div id="ref-table">
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px;">
        <!-- 信号等级 -->
        <div>
          <table style="font-size:.85em;">
            <thead><tr><th colspan="2" style="text-align:center;">信号等级</th></tr></thead>
            <tbody>
              <tr><td style="color:var(--green);font-weight:700;">A ≥ 78</td><td>强烈买入 — 质量/估值/趋势三重共振</td></tr>
              <tr><td style="color:var(--blue);font-weight:700;">B ≥ 64</td><td>偏多 — 可分批建仓，等待趋势确认</td></tr>
              <tr><td style="color:var(--yellow);font-weight:700;">C ≥ 50</td><td>中性 — 有亮点但存在明显短板</td></tr>
              <tr><td style="color:var(--red);font-weight:700;">D &lt; 50</td><td>回避 — 估值/趋势/质量至少一项严重恶化</td></tr>
            </tbody>
          </table>
        </div>
        <!-- 子分数档位 -->
        <div>
          <table style="font-size:.85em;">
            <thead><tr><th colspan="2" style="text-align:center;">质量/估值/趋势 子分档位</th></tr></thead>
            <tbody>
              <tr><td style="color:var(--green);font-weight:700;">≥ 75</td><td>优秀 — 因子全面占优，显著加分</td></tr>
              <tr><td style="color:var(--blue);font-weight:700;">60–74</td><td>良好 — 多数因子达标，少数偏弱</td></tr>
              <tr><td style="color:var(--yellow);font-weight:700;">45–59</td><td>及格线附近 — 基础分 50 + 少量加减分</td></tr>
              <tr><td style="color:var(--red);font-weight:700;">&lt; 45</td><td>偏弱 — 触发惩罚项，需关注短板</td></tr>
            </tbody>
          </table>
        </div>
        <!-- 质量因子及格线 -->
        <div>
          <table style="font-size:.85em;">
            <thead><tr><th>质量因子</th><th style="text-align:center;">优秀</th><th style="text-align:center;">及格</th><th style="text-align:center;">警戒</th></tr></thead>
            <tbody>
              <tr><td>营收增速</td><td class="val-up">≥ 8%</td><td>≥ 3%</td><td class="val-down">≤ -5%</td></tr>
              <tr><td>利润增速</td><td class="val-up">≥ 10%</td><td>≥ 3%</td><td class="val-down">≤ -8%</td></tr>
              <tr><td>毛利率</td><td class="val-up">≥ 45%</td><td>≥ 30%</td><td class="val-down">≤ 15%</td></tr>
              <tr><td>净利率</td><td class="val-up">≥ 18%</td><td>≥ 10%</td><td class="val-down">≤ 3%</td></tr>
              <tr><td>ROE</td><td class="val-up">≥ 15%</td><td>≥ 10%</td><td class="val-down">≤ 5%</td></tr>
              <tr><td>D/E</td><td class="val-up">≤ 60</td><td>≤ 120</td><td class="val-down">≥ 220</td></tr>
            </tbody>
          </table>
        </div>
        <!-- 估值因子及格线 -->
        <div>
          <table style="font-size:.85em;">
            <thead><tr><th>估值因子</th><th style="text-align:center;">便宜</th><th style="text-align:center;">合理</th><th style="text-align:center;">偏贵</th></tr></thead>
            <tbody>
              <tr><td>Trailing PE</td><td class="val-up">≤ 18</td><td>≤ 28</td><td class="val-down">≥ 45</td></tr>
              <tr><td>Forward PE</td><td class="val-up">≤ 17</td><td>≤ 24</td><td class="val-down">≥ 35</td></tr>
              <tr><td>P/S</td><td class="val-up">≤ 3</td><td>≤ 6</td><td class="val-down">≥ 12</td></tr>
              <tr><td>EV/EBITDA</td><td class="val-up">≤ 12</td><td>≤ 18</td><td class="val-down">≥ 30</td></tr>
            </tbody>
          </table>
        </div>
        <!-- 时钟模型 -->
        <div>
          <table style="font-size:.85em;">
            <thead><tr><th colspan="2" style="text-align:center;">趋势时钟模型</th></tr></thead>
            <tbody>
              <tr><td style="color:var(--green);font-weight:700;">🕐 1点钟</td><td>强势多头 · SMA20&gt;SMA60 且价格站上 SMA20</td></tr>
              <tr><td style="color:var(--green);font-weight:700;">🕑 2点钟</td><td>最佳买入 · 均线完美多头排列 + 价格确认</td></tr>
              <tr><td style="color:var(--yellow);font-weight:700;">🕒 3点钟</td><td>犹豫观望 · 均线缠绕，方向不明</td></tr>
              <tr><td style="color:var(--red);font-weight:700;">🕓 4–6点</td><td>悲观下跌 · 均线空头排列，只做右侧确认</td></tr>
            </tbody>
          </table>
        </div>
        <!-- 入场分公式 -->
        <div>
          <table style="font-size:.85em;">
            <thead><tr><th colspan="2" style="text-align:center;">入场分权重</th></tr></thead>
            <tbody>
              <tr><td>估值分 × 35%</td><td style="color:var(--text-secondary);">便宜才是硬道理</td></tr>
              <tr><td>趋势分 × 35%</td><td style="color:var(--text-secondary);">只做2点钟方向</td></tr>
              <tr><td>质量分 × 30%</td><td style="color:var(--text-secondary);">好公司 + 好价格</td></tr>
              <tr><td colspan="2" style="font-size:.8em;color:var(--text-secondary);">+ 位置修正（距60日线 ±3% 加分）</td></tr>
              <tr><td colspan="2" style="font-size:.8em;color:var(--text-secondary);">− 质量偏弱/估值偏贵/财报临近 惩罚</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>

  <!-- 红牌检查 -->
  <div style="margin-bottom:20px;">
    <h3 style="color:#f0f6fc;margin-bottom:8px;">红牌检查（一票否决）</h3>
    <div style="display:flex;gap:8px;flex-wrap:wrap;">
      {"".join(f'<span class="tag tag-bear">{red_flag_labels.get(f, f)}</span>' for f in red_flags_list) if red_flags_list else '<span class="tag tag-bull">无红牌 ✓</span>'}
    </div>
  </div>

  <!-- 评分拆解 -->
  <div class="grid-2">
    <!-- 质量分拆解 -->
    <div>
      <h3 style="color:#f0f6fc;margin-bottom:8px;">质量分拆解（合计 {q_total}）</h3>
      <div class="data-table-wrapper">
        <table>
          <thead><tr><th>因子</th><th>实际值</th><th>得分</th><th>规则说明</th></tr></thead>
          <tbody>{quality_rows}</tbody>
        </table>
      </div>
    </div>

    <!-- 估值分拆解 -->
    <div>
      <h3 style="color:#f0f6fc;margin-bottom:8px;">估值分拆解（合计 {v_total}）</h3>
      <div class="data-table-wrapper">
        <table>
          <thead><tr><th>因子</th><th>实际值</th><th>得分</th><th>规则说明</th></tr></thead>
          <tbody>{valuation_rows}</tbody>
        </table>
      </div>
    </div>
  </div>

  <div class="grid-2" style="margin-top:20px;">
    <!-- 趋势分拆解 -->
    <div>
      <h3 style="color:#f0f6fc;margin-bottom:8px;">趋势分拆解（合计 {t_total}）</h3>
      <div class="data-table-wrapper">
        <table>
          <thead><tr><th>因子</th><th>实际值</th><th>得分</th><th>规则说明</th></tr></thead>
          <tbody>{trend_rows}</tbody>
        </table>
      </div>
    </div>

    <!-- 修正项 -->
    <div>
      <h3 style="color:#f0f6fc;margin-bottom:8px;">入场修正项</h3>
      <div class="data-table-wrapper">
        <table>
          <thead><tr><th>因子</th><th>实际值</th><th>得分</th><th>规则说明</th></tr></thead>
          <tbody>{adjust_rows}</tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- 入场分公式 -->
  <div class="info-card" style="margin-top:20px;font-family:monospace;font-size:.9em;color:var(--text-secondary);">
    <strong style="color:var(--blue);">入场分公式：</strong>{formula}
  </div>
</section>"""


# ══════════════════════════════════════════════════
# 入口
# ══════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="StockScope 个股深度分析")
    parser.add_argument("ticker", help="股票代码（例如 AAPL、TSM、APH）")
    parser.add_argument("--output-dir", default="outputs/latest", help="输出目录")
    parser.add_argument("--format", default="html", choices=["html", "pdf", "both"],
                        help="输出格式：html / pdf / both（默认 html）")
    args = parser.parse_args()

    ticker = args.ticker.upper().strip()
    print(f"[StockScope] 正在拉取 {ticker} 数据...")
    try:
        data = fetch_data(ticker)
    except Exception as e:
        print(f"[错误] 数据拉取失败: {e}", file=sys.stderr)
        return 1

    if data.get("asset_type") != "ETF" and not data.get("quarterly_financials"):
        print(f"[错误] 未获取到 {ticker} 的财务数据，请确认代码正确", file=sys.stderr)
        return 1

    print(f"[StockScope] 正在运行评分管线...", flush=True)
    scored = run_stockscope_scoring(ticker)
    print(f"[StockScope] 正在生成报告...")
    html = render(data, scored)

    outdir = Path(args.output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    base = outdir / f"{ticker.lower()}-analysis"

    # ── HTML 输出 ──
    if args.format in ("html", "both"):
        html_path = base.with_suffix(".html")
        html_path.write_text(html, encoding="utf-8")
        print(f"[StockScope] HTML 报告已生成: {html_path}")

    # ── PDF 输出 ──
    if args.format in ("pdf", "both"):
        try:
            from weasyprint import HTML
            pdf_path = base.with_suffix(".pdf")
            HTML(string=html).write_pdf(pdf_path)
            print(f"[StockScope] PDF 报告已生成: {pdf_path}")
        except Exception as e:
            print(f"[警告] PDF 生成失败: {e}", file=sys.stderr)

    # 刷新研报索引
    try:
        from src.stockscope.research_index import generate_index
        generate_index(outdir)
        print(f"[StockScope] 研报索引已更新")
    except Exception:
        pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
