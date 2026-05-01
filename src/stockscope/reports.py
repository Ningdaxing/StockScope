from __future__ import annotations

import csv
from dataclasses import asdict
from datetime import datetime
from html import escape
from pathlib import Path

from stockscope.models import ScoredTicker


def write_csv(items: list[ScoredTicker], output_path: str | Path) -> None:
    """把打分结果写成 CSV 文件。

    作用：
    - 生成结构化结果供 Excel 或其他工具继续分析
    - 保留每个标的的完整评分结果
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [f.name for f in ScoredTicker.__dataclass_fields__.values()]
    rows = [asdict(item) for item in items]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_dashboard(
    items: list[ScoredTicker],
    output_path: str | Path,
    config_path: str | Path | None = None,
) -> None:
    """生成静态 HTML 看板。

    作用：
    - 把结果整理成更直观的网页表格
    - 支持按分组筛选查看
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 生成分组标签和数据
    from stockscope.config import load_groups

    group_tabs = [{"id": "all", "name": f"全部({len(items)})"}]
    group_data = {"all": items}

    if config_path:
        groups = load_groups(config_path)
        for group_name, symbols in groups.items():
            group_items = [item for item in items if item.symbol in symbols]
            display_name = group_name.replace("_", " ").title()
            group_tabs.append({
                "id": group_name,
                "name": f"{display_name}({len(group_items)})",
            })
            group_data[group_name] = group_items

    # 生成各分组表格
    group_panels = []
    row_counter = 0
    for tab in group_tabs:
        group_id = tab["id"]
        group_items = group_data.get(group_id, [])
        rows_parts = []
        for item in group_items:
            rows_parts.append(_render_row(item, row_counter))
            row_counter += 1
        rows = "\n".join(rows_parts)
        panel_html = _render_group_panel(group_id, rows, group_items)
        group_panels.append(panel_html)

    group_tabs_html = _render_group_tabs(group_tabs)
    group_panels_html = "\n".join(group_panels)
    explanation = _render_explanation()
    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>StockScope 看板</title>
  <style>
    :root {{
      --bg: #f6f2e8;
      --panel: #fffaf0;
      --ink: #1d2a2a;
      --muted: #5b6a6a;
      --line: #d7cfbe;
      --accent: #17494d;
      --good: #1c6b39;
      --warn: #9d6b14;
      --bad: #8f2d2d;
    }}
    body {{ margin: 0; background: radial-gradient(circle at top, #fdf7ea, var(--bg)); color: var(--ink); font-family: Georgia, "Times New Roman", serif; }}
    .wrap {{ max-width: 1200px; margin: 0 auto; padding: 32px 20px 48px; }}
    h1 {{ margin: 0 0 8px; font-size: 44px; }}
    p {{ color: var(--muted); }}
    h2 {{ margin: 0 0 14px; font-size: 22px; }}
    .panel {{ background: rgba(255,250,240,0.92); border: 1px solid var(--line); border-radius: 18px; padding: 20px; box-shadow: 0 16px 40px rgba(23,73,77,0.08); }}
    .tabs {{ display: flex; gap: 10px; margin: 20px 0 18px; }}
    .tab-button {{
      border: 1px solid var(--line);
      background: rgba(255,250,240,0.92);
      color: var(--ink);
      border-radius: 999px;
      padding: 10px 16px;
      cursor: pointer;
      font-size: 14px;
    }}
    .tab-button.active {{ background: var(--accent); color: #fffaf0; border-color: var(--accent); }}
    .tab-panel {{ display: none; }}
    .tab-panel.active {{ display: block; }}
    .group-tabs {{ display: flex; gap: 10px; margin: 10px 0 16px; flex-wrap: wrap; }}
    .group-tab {{
      border: 1px solid var(--line);
      background: rgba(255,250,240,0.92);
      color: var(--ink);
      border-radius: 999px;
      padding: 8px 14px;
      cursor: pointer;
      font-size: 13px;
    }}
    .group-tab.active {{ background: var(--accent); color: #fffaf0; border-color: var(--accent); }}
    .group-panel {{ display: none; }}
    .group-panel.active {{ display: block; }}
    .group-header {{ margin-bottom: 10px; font-size: 13px; color: var(--muted); }}
    .stack {{ display: grid; gap: 18px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ padding: 10px 8px; border-bottom: 1px solid var(--line); text-align: left; }}
    th {{ color: var(--muted); font-size: 12px; letter-spacing: 0.04em; }}
    .signal-A {{ color: var(--good); font-weight: bold; }}
    .signal-B {{ color: var(--accent); font-weight: bold; }}
    .signal-C {{ color: var(--warn); font-weight: bold; }}
    .signal-D {{ color: var(--bad); font-weight: bold; }}
    .mono {{ font-family: "SFMono-Regular", Menlo, monospace; }}
    .muted {{ color: var(--muted); }}
    .toggle-btn {{
      cursor: pointer; background: none; border: 1px solid var(--line);
      color: var(--ink); font-size: 0.8rem; padding: 0 4px; border-radius: 3px;
      transition: transform 0.2s;
    }}
    .toggle-btn.open {{ transform: rotate(90deg); }}
    .breakdown-panel {{
      background: var(--panel); border: 1px solid var(--line);
      padding: 12px 16px; margin: 4px 0; border-radius: 6px;
      font-size: 0.85rem;
    }}
    .breakdown-panel h4 {{
      margin: 8px 0 4px; color: var(--accent); font-size: 0.85rem;
    }}
    .bd-section {{ margin-bottom: 8px; }}
    .bd-formula {{
      display: block; background: #f0ede4; padding: 6px 10px;
      border-radius: 4px; white-space: pre-wrap; font-size: 0.8rem;
    }}
    .breakdown-table {{ width: 100%; font-size: 0.8rem; }}
    .breakdown-table td {{ padding: 2px 8px; border-bottom: 1px solid #f0ede4; }}
    .positive {{ color: var(--good); font-weight: bold; }}
    .negative {{ color: var(--bad); font-weight: bold; }}
    .neutral {{ color: var(--muted); }}
    .metric-excellent {{ color: var(--good); font-weight: bold; }}
    .metric-ideal {{ color: var(--good); font-weight: bold; }}
    .metric-weak {{ color: var(--bad); font-weight: bold; }}
    .metric-warn {{ color: var(--warn); font-weight: bold; }}
    .note-good {{ color: var(--good); font-weight: bold; }}
    .note-warn {{ color: var(--warn); font-weight: bold; }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>StockScope</h1>
    <p>生成时间：{escape(generated_at)}。当前信号仅用于研究分析，不构成自动交易建议。</p>
    <div class="tabs">
      <button class="tab-button active" data-tab="signals">信号分组</button>
      <button class="tab-button" data-tab="guide">评分说明</button>
    </div>
    <section id="signals" class="tab-panel active">
      {group_tabs_html}
      {group_panels_html}
    </section>
    <section id="guide" class="tab-panel">
      {explanation}
    </section>
  </div>
  <script>
    // 顶部标签切换
    const buttons = document.querySelectorAll('.tab-button');
    const panels = document.querySelectorAll('.tab-panel');
    buttons.forEach((button) => {{
      button.addEventListener('click', () => {{
        const target = button.getAttribute('data-tab');
        buttons.forEach((item) => item.classList.toggle('active', item === button));
        panels.forEach((panel) => panel.classList.toggle('active', panel.id === target));
      }});
    }});

    // 分组标签切换
    const groupButtons = document.querySelectorAll('.group-tab');
    const groupPanels = document.querySelectorAll('.group-panel');
    groupButtons.forEach((button) => {{
      button.addEventListener('click', () => {{
        const target = button.getAttribute('data-group');
        groupButtons.forEach((item) => item.classList.toggle('active', item === button));
        groupPanels.forEach((panel) => panel.classList.toggle('active', panel.getAttribute('data-group') === target));
      }});
    }});
    // 评分拆解展开/折叠
    function toggleBreakdown(index) {{
      const row = document.getElementById('bd-' + index);
      const btn = event.target;
      if (row.style.display === 'none') {{
        row.style.display = '';
        btn.classList.add('open');
        btn.textContent = '▾';
      }} else {{
        row.style.display = 'none';
        btn.classList.remove('open');
        btn.textContent = '▸';
      }}
    }}
  </script>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")


def print_terminal_summary(items: list[ScoredTicker], *, limit: int = 12) -> str:
    """生成终端摘要文本。

    作用：
    - 在命令行里快速展示前几条核心结果
    - 让你不打开文件也能先看买点信号
    """
    header = (
        f"{'代码':<8} {'名称':<18} {'类型':<6} {'信号':<4} {'入场分':>6} "
        f"{'估值分':>6} {'趋势分':>6} {'质量分':>6} {'说明'}"
    )
    lines = [header, "-" * len(header)]
    for item in items[:limit]:
        quality = "-" if item.quality_score is None else str(item.quality_score)
        short_name = item.short_name[:18]
        lines.append(
            f"{item.symbol:<8} {short_name:<18} {item.asset_type:<6} {item.signal:<4} {item.entry_score:>6} "
            f"{item.valuation_score:>6} {item.trend_score:>6} {quality:>6} {_translate_note(item.note)}"
        )
    return "\n".join(lines)


def _score_class(score: int | None, *, excellent: int = 78, weak: int = 45) -> str:
    """分数高亮：高分绿色加粗，低分红色警告。"""
    if score is None:
        return ""
    if score >= excellent:
        return "metric-excellent"
    if score < weak:
        return "metric-weak"
    return ""


def _valuation_class(score: int | None) -> str:
    """估值分专用：>=75 便宜，<40 偏贵。"""
    return _score_class(score, excellent=75, weak=40)


def _note_class(note: str) -> str:
    """说明标签高亮：好信号绿色，警告橙色。"""
    if "near_60d_ma" in note:
        return "note-good"
    if any(tag in note for tag in ("weak_quality", "rich_valuation", "earnings_soon", "extended_above", "below_60d")):
        return "note-warn"
    return ""


def _dist_class(dist: float | None) -> str:
    """距60日线高亮：贴近绿色，过远橙色。"""
    if dist is None:
        return ""
    if abs(dist) <= 0.03:
        return "metric-ideal"
    if dist > 0.12 or dist < -0.10:
        return "metric-warn"
    return ""


def _dd_class(dd: float | None) -> str:
    """回撤高亮：温和回撤绿色，严重回撤红色。"""
    if dd is None:
        return ""
    if -0.18 <= dd <= -0.03:
        return "metric-ideal"
    if dd < -0.35:
        return "metric-weak"
    return ""


def _render_row(item: ScoredTicker, row_index: int) -> str:
    """渲染单条评分结果 + 展开按钮 + 隐藏拆解子行。"""
    quality = "-" if item.quality_score is None else str(item.quality_score)
    price = _fmt_number(item.current_price)
    dist = _fmt_pct(item.distance_to_sma60_pct)
    drawdown = _fmt_pct(item.drawdown_from_high_pct)
    has_breakdown = item.breakdown is not None
    toggle_html = ""
    breakdown_html = ""
    note_display = _translate_note(item.note)
    if has_breakdown:
        toggle_html = f"<button class='toggle-btn' onclick='toggleBreakdown({row_index})' title='评分拆解'>▸</button>"
        breakdown_html = _render_breakdown_row(item, row_index)
    main_row = (
        "<tr>"
        f"<td class='mono'>{escape(item.symbol)}</td>"
        f"<td>{escape(item.short_name)}</td>"
        f"<td>{escape(item.asset_type)}</td>"
        f"<td class='signal-{escape(item.signal)}'>{escape(item.signal)}</td>"
        f"<td class='{_score_class(item.entry_score)}'>{item.entry_score}</td>"
        f"<td class='{_valuation_class(item.valuation_score)}'>{item.valuation_score}</td>"
        f"<td class='{_score_class(item.trend_score, excellent=75, weak=45)}'>{item.trend_score}</td>"
        f"<td class='{_score_class(item.quality_score, excellent=75, weak=45)}'>{quality}</td>"
        f"<td>{price}</td>"
        f"<td class='{_dist_class(item.distance_to_sma60_pct)}'>{dist}</td>"
        f"<td class='{_dd_class(item.drawdown_from_high_pct)}'>{drawdown}</td>"
        f"<td class='{_note_class(item.note)}'>{escape(note_display)} {toggle_html}</td>"
        "</tr>"
    )
    return main_row + breakdown_html


def _render_breakdown_row(item: ScoredTicker, row_index: int) -> str:
    """渲染评分拆解的可展开子行。"""
    bd = item.breakdown
    if bd is None:
        return ""
    sections: list[str] = []

    # 入场公式
    if bd.entry_formula:
        sections.append(
            "<div class='bd-section'>"
            f"<h4>入场分计算</h4>"
            f"<code class='bd-formula'>{escape(bd.entry_formula)}</code>"
            "</div>"
        )

    # 质量分拆解
    if bd.quality_items and item.quality_score is not None:
        sections.append(_render_breakdown_section(
            f"质量分({item.quality_score}) = {bd.quality_base} 基准",
            bd.quality_items,
        ))

    # 估值分拆解
    if bd.valuation_items:
        sections.append(_render_breakdown_section(
            f"估值分({item.valuation_score}) = {bd.valuation_base} 基准",
            bd.valuation_items,
        ))

    # 趋势分拆解
    if bd.trend_items:
        sections.append(_render_breakdown_section(
            f"趋势分({item.trend_score}) = {bd.trend_base} 基准",
            bd.trend_items,
        ))

    # 入场修正
    if bd.adjustments:
        sections.append(_render_breakdown_section("入场修正", bd.adjustments))

    inner = "\n".join(sections)
    return (
        f'<tr class="breakdown-row" id="bd-{row_index}" style="display:none">'
        f'<td colspan="13"><div class="breakdown-panel">{inner}</div></td>'
        f"</tr>"
    )


def _render_breakdown_section(title: str, items: list) -> str:
    """渲染单个拆解区块（标题 + 明细小表）。"""
    rows = []
    for it in items:
        css_class = "positive" if it.score > 0 else ("negative" if it.score < 0 else "neutral")
        rows.append(
            "<tr>"
            f"<td>{escape(it.factor)}</td>"
            f"<td class='mono'>{escape(it.value)}</td>"
            f"<td class='{css_class}'>{( '+' if it.score > 0 else '' )}{it.score}</td>"
            f"<td class='muted'>{escape(it.detail)}</td>"
            "</tr>"
        )
    return (
        f'<div class="bd-section"><h4>{escape(title)}</h4>'
        '<table class="breakdown-table"><tbody>'
        f'{"".join(rows)}'
        '</tbody></table></div>'
    )


def _render_explanation() -> str:
    """渲染 HTML 顶部的评分说明区块。

    作用：
    - 直接在看板里解释信号等级和评分逻辑
    - 让使用者不需要翻代码也能理解结果
    """
    return """
<div class="stack">
  <div class="panel">
    <h2>评分说明</h2>
    <table>
      <thead>
        <tr>
          <th>字段</th>
          <th>怎么看</th>
          <th>大致及格线</th>
          <th>算法说明</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>信号</td>
          <td>A 最强，D 最弱</td>
          <td>A: 78分以上，B: 64-77，C: 50-63，D: 50以下</td>
          <td>由入场分映射而来，主要用于快速判断当前是否值得重点关注。</td>
        </tr>
        <tr>
          <td>入场分</td>
          <td>最终总分，最重要</td>
          <td>64分以上可进入观察，78分以上可重点关注</td>
          <td>按估值分 40% + 趋势分 40% + 质量分 20% 计算，再根据是否贴近60日线、是否财报临近、是否过贵或质量偏弱做加减分。</td>
        </tr>
        <tr>
          <td>估值分</td>
          <td>越高越便宜或越合理</td>
          <td>60分以上较合理，75分以上偏便宜，40分以下偏贵</td>
          <td>个股主要看 PE、Forward PE、PS、EV/EBITDA；ETF 当前用简化估值逻辑，主要参考 PE、Forward PE 和股息率。</td>
        </tr>
        <tr>
          <td>趋势分</td>
          <td>越高说明走势越健康</td>
          <td>60分以上趋势尚可，75分以上较强，45分以下偏弱</td>
          <td>主要看价格是否站上20/60/120日线、距52周高点回撤位置，以及相对 SPY 的强弱。</td>
        </tr>
        <tr>
          <td>质量分</td>
          <td>只对个股有效，ETF 通常为空</td>
          <td>60分以上及格，75分以上较好，45分以下偏弱</td>
          <td>主要看营收增长、利润增长、毛利率、净利率、ROE、负债和现金流。</td>
        </tr>
      </tbody>
    </table>
  </div>
  <div class="panel">
    <h2>说明标签</h2>
    <table>
      <thead>
        <tr>
          <th>标签</th>
          <th>含义</th>
        </tr>
      </thead>
      <tbody>
        <tr><td>接近60日线</td><td>价格靠近60日均线，属于你偏好的观察位置之一。</td></tr>
        <tr><td>高于60日线过远</td><td>价格离60日线太远，可能有追高风险。</td></tr>
        <tr><td>低于60日线过远</td><td>价格跌破60日线过多，趋势可能已经转弱。</td></tr>
        <tr><td>质量偏弱</td><td>公司基本面质量偏弱，不适合轻易参与。</td></tr>
        <tr><td>估值偏贵</td><td>当前估值不便宜，需要更谨慎。</td></tr>
        <tr><td>财报临近</td><td>临近财报披露，短期波动和不确定性更高。</td></tr>
        <tr><td>整体均衡</td><td>没有明显额外加分或减分项。</td></tr>
      </tbody>
    </table>
  </div>
</div>
"""


def _render_group_tabs(tabs: list[dict]) -> str:
    """渲染分组标签按钮。

    作用：
    - 为每个分组生成一个可点击的标签按钮
    """
    buttons = []
    for i, tab in enumerate(tabs):
        active_class = "active" if i == 0 else ""
        buttons.append(
            f'<button class="group-tab {active_class}" data-group="{tab["id"]}">{escape(tab["name"])}</button>'
        )
    return f'<div class="group-tabs">' + "".join(buttons) + '</div>'


def _render_group_panel(group_id: str, rows_html: str, items: list[ScoredTicker]) -> str:
    """渲染单个分组的表格面板。

    作用：
    - 每个分组对应一个可切换显示的面板
    """
    active_class = "active" if group_id == "all" else ""
    signal_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    for item in items:
        if item.signal in signal_counts:
            signal_counts[item.signal] += 1

    summary = f"A({signal_counts['A']}) B({signal_counts['B']}) C({signal_counts['C']}) D({signal_counts['D']})"

    if not items:
        rows_html = '<tr><td colspan="12" class="muted" style="text-align:center;">该分组暂无数据</td></tr>'

    return f"""<div class="group-panel {active_class}" data-group="{group_id}">
      <div class="panel">
        <div class="group-header">
          <span class="signal-summary">{summary}</span>
        </div>
        <table>
          <thead>
            <tr>
              <th>代码</th>
              <th>名称</th>
              <th>类型</th>
              <th>信号</th>
              <th>入场分</th>
              <th>估值分</th>
              <th>趋势分</th>
              <th>质量分</th>
              <th>现价</th>
              <th>距60日线</th>
              <th>距52周高点回撤</th>
              <th>说明</th>
            </tr>
          </thead>
          <tbody>{rows_html}</tbody>
        </table>
      </div>
    </div>"""


def _translate_note(note: str) -> str:
    """把内部说明标签翻译成更易读的中文。

    作用：
    - 让终端和 HTML 输出更贴近使用者视角
    - 避免直接暴露内部英文标签
    """
    mapping = {
        "near_60d_ma": "接近60日线",
        "extended_above_60d": "高于60日线过远",
        "below_60d_too_far": "低于60日线过远",
        "weak_quality": "质量偏弱",
        "rich_valuation": "估值偏贵",
        "earnings_soon": "财报临近",
        "balanced": "整体均衡",
    }
    parts = [mapping.get(part, part) for part in note.split(",") if part]
    return "，".join(parts) if parts else note


def _fmt_pct(value: float | None) -> str:
    """把比例值格式化成百分比字符串。

    作用：
    - 统一看板里的百分比展示格式
    - 对空值做兜底显示
    """
    if value is None:
        return "-"
    return f"{value * 100:.1f}%"


def _fmt_number(value: float | None) -> str:
    """把数值格式化成两位小数字符串。

    作用：
    - 统一价格等字段的展示格式
    - 对空值做兜底显示
    """
    if value is None:
        return "-"
    return f"{value:.2f}"
