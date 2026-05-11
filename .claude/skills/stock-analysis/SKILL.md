---
name: stock-analysis
description: 美股个股深度分析。给定任意美股 ticker（如 AAPL、TSM、APH），自动拉取 yfinance 实时数据并生成完整中文深度分析报告（HTML），包含 10 大章节：公司定位、核心财务、估值、成长性、利润效率、资产负债、资本配置、机构持仓与分析师共识、最终判断、StockScope 评分框架。输出到 outputs/latest/{ticker}-analysis.html 并自动打开浏览器。当用户对某个美股代码要深度分析、财报解读、估值判断时触发。
---

# Stock Analysis — 美股个股深度分析

## Quick start

```
python scripts/analyze.py <TICKER>
```

生成报告后使用 `open` 命令在浏览器中打开。

## Workflow

1. 接收用户提供的股票代码（如 AAPL、APH、TSM）
2. 运行 `python .claude/skills/stock-analysis/scripts/analyze.py {ticker}`
3. 确认脚本执行成功（退出码 0，输出文件存在）
4. 执行 `open outputs/latest/{ticker_lower}-analysis.html` 打开报告
5. 向用户简要说明报告已生成 + 关键数据亮点（PE、PEG、增速、评级）

## 脚本功能

`scripts/analyze.py` 负责：

- 通过 yfinance 拉取：季度财报、年度收入、EPS 历史、资产负债表、现金流、机构持仓、分析师评级
- 自动生成深色主题 HTML 报告（10 个章节，带数据表格、指标卡片、颜色高亮）
- 集成 StockScope 评分管线：调用入场分/质量分/估值分/趋势分/时钟模型/红牌机制，含完整因子拆解
- 根据 PEG/Fwd PE 自动判断估值档位并生成一句话定位

## 报告章节

1. 公司定位与分类
2. 核心财务数据（季度趋势 + EPS 超预期记录）
3. 估值分析（PE / PEG / EV / PB / Beta）
4. 成长性分析（年度收入趋势 + 增速指标）
5. 利润与效率指标（ROE / ROA / 利润率 / FCF）
6. 资产负债健康度（D/E / 流动比率 / 商誉占比）
7. 资本配置策略（并购 / 发债 / 分红 / 回购）
8. 机构持仓 & 分析师共识
9. 最终判断（自动评级 + 关键数据摘要）
10. StockScope 评分框架 — 信号等级(A/B/C/D) + 入场分 + 质量/估值/趋势分拆解 + 时钟模型 + 红牌检查 + 评分基准参考（含因子及格线对照表）

## 依赖

- Python 3.11+（使用 pyenv 中的 `python`）
- yfinance（已安装）
- deep-translator（用于业务概述中文化）
