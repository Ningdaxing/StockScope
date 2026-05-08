# StockScope

美股信号筛选 + 个股深度分析工具。基于 Yahoo Finance 公开数据，提供买入信号扫描、Web 实时看板、个股财报深度研报。

---

## 功能概览

### 信号看板（Web 服务）

- **买入总览**：按信号等级（A/B/C/D）筛选，展示强烈推荐和可关注标的卡片
- **信号分组**：按自定义分组（七巨头、半导体与AI、国防航天等）查看，支持评分排序和因子拆解
- **评分说明**：入场分、估值分、趋势分、质量分的计算逻辑
- **研报中心**：所有个股深度分析报告自动汇集

### 个股深度分析（Skill）

`/stock-analysis <代码>` 自动拉取 yfinance 数据，生成完整中文 HTML 报告：

1. 公司定位与分类
2. 核心财务数据（季度趋势 + EPS 超预期记录）
3. 估值分析（PE / PEG / EV / PB / Beta）
4. 成长性分析（年度收入趋势 + 增速指标）
5. 利润与效率指标（ROE / ROA / FCF）
6. 资产负债健康度（D/E / 流动比率 / 商誉占比）
7. 资本配置策略
8. 机构持仓与分析师共识
9. 最终判断（自动评级 + 关键数据摘要）

### CLI 命令行

```bash
# 单次分析，输出 CSV + HTML + 终端摘要
python run_stockscope.py run --limit 15 --open

# 启动 Web 看板服务（1 小时自动刷新）
python run_stockscope.py serve
```

---

## 快速开始

```bash
# 1. 安装依赖
pip install yfinance fastapi uvicorn apscheduler deep-translator

# 2. 单次分析
python run_stockscope.py run --open

# 3. 启动 Web 看板
python run_stockscope.py serve
# 浏览器访问 http://localhost:8081
```

> `--open` 参数会在分析完成后自动打开浏览器。

---

## 使用方式

### Web 看板

| 操作 | 方式 |
|------|------|
| 切换 Tab | 点击「买入总览 / 信号分组 / 评分说明 / 研报中心」 |
| 筛选信号 | 点击 A/B/C/D 统计数字 |
| 分组查看 | 点击「七巨头」「半导体与AI」等分组标签 |
| 表格排序 | 点击列头的排序按钮 |
| 查看研报 | 研报中心 → 点击报告卡片（新标签页打开） |

### 个股深度分析

在 Claude Code 中直接说人话或使用命令：

```
分析下 TSLA
/stock-analysis AAPL
帮我看看 NVDA
```

报告生成到 `outputs/latest/<代码>-analysis.html`，自动打开浏览器。报告列表自动汇入看板的「研报中心」Tab。

### 观察池配置

编辑 `config/watchlist.toml`：

```toml
[defaults]
benchmark = "SPY"

[groups]
"七巨头" = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA"]
"半导体与AI" = ["AVGO", "AMD", "TSM", "MU", "SNDK", "QCOM", "AMAT", "ARM"]

[tickers]
manual = ["APH", "SOFI"]

[name_overrides]
# 可选：覆盖 Yahoo Finance 返回的名称
```

---

## 项目结构

```text
config/watchlist.toml             观察池和分组配置
src/stockscope/
├── cli.py                        命令行入口（run / serve）
├── server.py                     FastAPI Web 服务
├── reports.py                    HTML 看板生成（含 JS 交互）
├── research_index.py             研报索引自动生成
├── scoring.py                    打分逻辑（质量/估值/趋势/入场）
├── fetchers/yahoo.py             Yahoo Finance 抓取器
├── models.py                     数据模型
├── config.py                     配置加载
└── name_resolver.py              名称解析（缓存 + 自定义）

.claude/skills/stock-analysis/
├── SKILL.md                      Skill 定义
└── scripts/analyze.py            个股深度分析脚本

outputs/latest/                   生成的报告文件（不提交 git）
tests/                            单元测试
```

---

## 依赖

| 包 | 用途 |
|----|------|
| `yfinance` | 美股行情与财务数据 |
| `fastapi` + `uvicorn` | Web 看板服务 |
| `apscheduler` | 定时自动刷新 |
| `deep-translator` | 研报业务概述中文化 |

```bash
pip install yfinance fastapi uvicorn apscheduler deep-translator
```

---

## 说明

- 当前版本覆盖**美股个股和 ETF**，A 股需新增抓取器。
- Yahoo Finance 公开接口可能变化；如需生产级稳定性建议迁移到 Polygon + SEC。
- 所有评级和信号仅用于研究分析，**不构成投资建议**。
- `outputs/` 目录已在 `.gitignore` 中，不会提交到仓库。
