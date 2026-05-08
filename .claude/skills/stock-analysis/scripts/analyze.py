#!/usr/bin/env python
"""StockScope 个股深度分析 — 拉取 yfinance 数据 -> 生成中文 HTML 报告."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import yfinance as yf

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

    # 季度财报
    qf = stock.quarterly_financials
    qf_data = []
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
    eh = stock.earnings_history
    eh_data = []
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

    d = {
        "ticker": ticker,
        "name": info.get("longName") or info.get("shortName") or ticker,
        "summary": _translate_en_to_zh(info.get("longBusinessSummary") or ""),
        "industry": _tr_industry(info.get("industry") or "—"),
        "sector": _tr_sector(info.get("sector") or "—"),
        "market_cap": info.get("marketCap"),
        "current_price": info.get("currentPrice"),
        "target_mean": info.get("targetMeanPrice"),
        "target_high": info.get("targetHighPrice"),
        "target_low": info.get("targetLowPrice"),
        "analyst_count": info.get("numberOfAnalystOpinions"),
        "recommendation": _tr_rec(info.get("recommendationKey") or ""),
        "revenue_growth": (info.get("revenueGrowth") or 0) * 100,
        "earnings_growth": (info.get("earningsGrowth") or 0) * 100,
        "forward_pe": info.get("forwardPE"),
        "trailing_pe": info.get("trailingPE"),
        "peg_ratio": info.get("pegRatio"),
        "price_to_book": info.get("priceToBook"),
        "ev_revenue": info.get("enterpriseToRevenue"),
        "ev_ebitda": info.get("enterpriseToEbitda"),
        "beta": info.get("beta"),
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
    }
    return d


# ══════════════════════════════════════════════════
# HTML 渲染
# ══════════════════════════════════════════════════

def render(data: dict) -> str:
    d = data
    t = d["ticker"]
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

<!-- 2. 核心财务 -->
<section>
  <h2><span class="num">2</span> 核心财务数据</h2>
  <h3>季度趋势（最近 4 季）</h3>
  <div class="data-table-wrapper">
    <table>
      <thead><tr><th>季度</th><th>收入</th><th>毛利率</th><th>营业利润</th><th>净利润</th><th>稀释 EPS</th><th>EBITDA</th></tr></thead>
      <tbody>{q_rows}</tbody>
    </table>
  </div>

  <h3>EPS 超预期记录</h3>
  <div class="data-table-wrapper">
    <table>
      <thead><tr><th>季度</th><th>EPS 实际</th><th>EPS 预期</th><th>超预期幅度</th></tr></thead>
      <tbody>{eps_rows}</tbody>
    </table>
  </div>
</section>

<!-- 3. 估值分析 -->
<section>
  <h2><span class="num">3</span> 估值分析</h2>
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
  <h2><span class="num">4</span> 成长性分析</h2>
  <h3>年度收入趋势</h3>
  <div class="data-table-wrapper">
    <table>
      <thead><tr><th>财年</th><th>收入</th><th>增速</th></tr></thead>
      <tbody>{rev_rows}</tbody>
    </table>
  </div>

  <div class="metric-grid">
    <div class="metric-card good"><div class="label">收入增速（同比）</div><div class="value {'val-up' if rev_g and rev_g > 0 else 'val-down'}">{_pct(rev_g)}</div></div>
    <div class="metric-card good"><div class="label">利润增速（同比）</div><div class="value {'val-up' if earn_g and earn_g > 0 else 'val-down'}">{_pct(earn_g)}</div></div>
  </div>
</section>

<!-- 5. 利润效率 -->
<section>
  <h2><span class="num">5</span> 利润与效率指标</h2>
  <div class="metric-grid">
    <div class="metric-card good"><div class="label">净利润率</div><div class="value">{_pct(d['profit_margins'], signed=False)}</div></div>
    <div class="metric-card good"><div class="label">毛利率</div><div class="value">{_pct(d['gross_margins'], signed=False)}</div></div>
    <div class="metric-card good"><div class="label">EBITDA 利润率</div><div class="value">{_pct(d['ebitda_margins'], signed=False)}</div></div>
    <div class="metric-card good"><div class="label">ROE（净资产收益率）</div><div class="value">{_pct(d['roe'], signed=False)}</div></div>
    <div class="metric-card accent"><div class="label">ROA（总资产收益率）</div><div class="value">{_pct(d['roa'], signed=False)}</div></div>
    <div class="metric-card good"><div class="label">自由现金流</div><div class="value">{_fmt_big(d['fcf'])}</div></div>
    <div class="metric-card good"><div class="label">经营现金流</div><div class="value">{_fmt_big(d['ocf'])}</div></div>
    <div class="metric-card accent"><div class="label">分红率</div><div class="value">{_pct(d['payout_ratio'], signed=False)}</div></div>
    <div class="metric-card accent"><div class="label">股息率</div><div class="value">{_pct(d['dividend_yield'], signed=False)}</div></div>
  </div>
</section>

<!-- 6. 资产负债 -->
<section>
  <h2><span class="num">6</span> 资产负债健康度</h2>
  <div class="metric-grid">
    <div class="metric-card accent"><div class="label">现金</div><div class="value">{_fmt_big(d['total_cash'])}</div></div>
    <div class="metric-card {'warn' if d['total_debt'] and d['total_cash'] and d['total_debt'] > d['total_cash'] else 'accent'}"><div class="label">总负债</div><div class="value">{_fmt_big(d['total_debt'])}</div></div>
    <div class="metric-card {'danger' if de and de > 100 else 'warn' if de and de > 50 else 'good'}"><div class="label">负债权益比（D/E）</div><div class="value">{_val(de)}%</div><div class="sub">{'偏高' if de and de > 100 else '偏高' if de and de > 50 else '健康' if de else ''}</div></div>
    <div class="metric-card {'good' if cr and cr > 1.5 else 'warn' if cr else 'accent'}"><div class="label">流动比率</div><div class="value">{_val(cr, '.2f')}</div></div>
    <div class="metric-card {'good' if bs.get('quick_ratio') and bs['quick_ratio'] > 1 else 'warn' if bs.get('quick_ratio') else 'accent'}"><div class="label">速动比率</div><div class="value">{_val(bs.get('quick_ratio'), '.2f')}</div></div>
    <div class="metric-card {'warn' if gw_pct > 30 else 'accent'}"><div class="label">商誉 + 无形资产</div><div class="value">{_fmt_big(bs.get('gw_intangibles'))}</div><div class="sub">占总资产 {gw_pct:.0f}%</div></div>
  </div>
</section>

<!-- 7. 资本配置 -->
<section>
  <h2><span class="num">7</span> 资本配置策略</h2>
  <div class="info-card">
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;">
      {cf_signals}
    </div>
  </div>
</section>

<!-- 8. 机构与分析师 -->
<section>
  <h2><span class="num">8</span> 机构持仓 & 分析师共识</h2>
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
  <h2><span class="num">9</span> 最终判断</h2>
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

<footer>
  <p>StockScope 个股深度分析 · 数据来源：Yahoo Finance</p>
  <p>数据截止：{today} · 不构成投资建议 · 投资有风险，决策需谨慎</p>
</footer>

</body>
</html>"""
    return html


# ══════════════════════════════════════════════════
# 入口
# ══════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="StockScope 个股深度分析")
    parser.add_argument("ticker", help="股票代码（例如 AAPL、TSM、APH）")
    parser.add_argument("--output-dir", default="outputs/latest", help="输出目录")
    args = parser.parse_args()

    ticker = args.ticker.upper().strip()
    print(f"[StockScope] 正在拉取 {ticker} 数据...")
    try:
        data = fetch_data(ticker)
    except Exception as e:
        print(f"[错误] 数据拉取失败: {e}", file=sys.stderr)
        return 1

    if not data.get("quarterly_financials"):
        print(f"[错误] 未获取到 {ticker} 的财务数据，请确认代码正确", file=sys.stderr)
        return 1

    print(f"[StockScope] 正在生成 HTML 报告...")
    html = render(data)

    outdir = Path(args.output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    outpath = outdir / f"{ticker.lower()}-analysis.html"
    outpath.write_text(html, encoding="utf-8")
    print(f"[StockScope] 报告已生成: {outpath}")

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
