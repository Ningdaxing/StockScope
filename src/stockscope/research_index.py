"""扫描 outputs 目录中的 *-analysis.html 文件，生成索引页."""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

CSS = """<style>
  :root { --bg:#0d1117;--card-bg:#161b22;--border:#30363d;--text:#c9d1d9;
    --text-secondary:#8b949e;--green:#3fb950;--blue:#58a6ff;--accent:#1f6feb; }
  * { box-sizing:border-box;margin:0;padding:0; }
  body { background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;line-height:1.6;max-width:900px;margin:0 auto; }
  header { background:linear-gradient(135deg,#1a2332 0%,#0d1b2a 100%);border-bottom:1px solid var(--border);padding:32px 24px;text-align:center; }
  header h1 { font-size:1.8em;color:#f0f6fc; }
  header .subtitle { color:var(--text-secondary);font-size:.9em;margin-top:4px; }
  .report-list { padding:24px; display:flex;flex-direction:column;gap:12px; }
  .report-card { background:var(--card-bg);border:1px solid var(--border);border-radius:8px;padding:16px 20px;display:flex;align-items:center;gap:16px;text-decoration:none;color:var(--text);transition:border-color .2s,background .2s; }
  .report-card:hover { border-color:var(--blue);background:#1c2128; }
  .report-card .ticker-badge { font-size:1.4em;font-weight:900;color:var(--blue);min-width:80px;letter-spacing:2px; }
  .report-card .info { flex:1; }
  .report-card .info .name { font-size:1em;color:#f0f6fc;font-weight:600; }
  .report-card .info .meta { font-size:.82em;color:var(--text-secondary);margin-top:2px; }
  .report-card .arrow { color:var(--text-secondary);font-size:1.2em; }
  .empty { text-align:center;padding:60px 24px;color:var(--text-secondary); }
  .empty .icon { font-size:3em;margin-bottom:12px; }
  footer { text-align:center;padding:24px;color:var(--text-secondary);font-size:.8em;border-top:1px solid var(--border); }
</style>"""


def _extract_title(html_path: Path) -> str:
    try:
        text = html_path.read_text(encoding="utf-8")
        m = re.search(r"<title>(.+?)</title>", text)
        if m:
            return m.group(1).strip()
    except Exception:
        pass
    return html_path.stem.replace("-analysis", "").upper()


def _extract_date(html_path: Path) -> str:
    try:
        text = html_path.read_text(encoding="utf-8")
        m = re.search(r"报告日期：(\d{4}-\d{2}-\d{2})", text)
        if m:
            return m.group(1)
    except Exception:
        pass
    return ""


def generate_index(output_dir: str | Path) -> Path:
    outdir = Path(output_dir)
    reports = sorted(outdir.glob("*analysis.html"), key=lambda p: p.stat().st_mtime, reverse=True)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    rows = ""
    for rp in reports:
        ticker = rp.stem.replace("-analysis", "").upper()
        title = _extract_title(rp)
        date_str = _extract_date(rp) or "—"
        rows += f"""
    <a class="report-card" href="/research/{rp.name}" target="_blank">
      <div class="ticker-badge">{ticker}</div>
      <div class="info">
        <div class="name">{title}</div>
        <div class="meta">分析日期：{date_str} · 文件大小：{rp.stat().st_size / 1024:.0f} KB</div>
      </div>
      <div class="arrow">&rarr;</div>
    </a>"""

    if not rows:
        rows = '<div class="empty"><div class="icon">📭</div><p>暂无分析报告，去 /stock-analysis 生成一份吧</p></div>'

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>StockScope 研报中心</title>
{CSS}
</head>
<body>

<header>
  <h1>StockScope 研报中心</h1>
  <div class="subtitle">共 {len(reports)} 份深度分析报告 · 更新于 {now}</div>
</header>

<div class="report-list">{rows}
</div>

<footer>
  <p>StockScope Research Center · 报告由 stock-analysis skill 自动生成</p>
</footer>

</body>
</html>"""

    index_path = outdir / "research-center.html"
    index_path.write_text(html, encoding="utf-8")
    return index_path
