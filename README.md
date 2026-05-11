# StockScope

美股信号筛选 + 个股深度分析工具。基于 Yahoo Finance 公开数据，提供买入信号扫描、Web 实时看板、个股财报深度研报。覆盖 117 只美股标的，18 个行业分组。

---

## 功能概览

### 信号看板（Web 服务）

- **买入总览**：按信号等级（A/B/C/D）筛选，强烈推荐、可关注、红牌警告三类卡片，每张卡片展示公司介绍 + 趋势方向 + 距60日线 + 回撤
- **信号分组**：按 18 个行业分组（七巨头、半导体与AI、AI基础设施、加密货币等）查看，支持评分排序和因子拆解
- **评分说明**：入场分、估值分、趋势分、质量分 + 时钟模型 + 红牌机制完整说明
- **研报中心**：所有个股深度分析报告自动汇集
- **公司详情**：鼠标悬停公司名查看三段式介绍（公司介绍 / 商业模式 / 盈利模式），展开评分拆解面板也有

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

## 评分体系

### 四大模块

| 模块 | 权重（个股） | 说明 |
|------|-------------|------|
| 质量分 | 30% | 盈利增长、毛利率、净利率、EBIT利润率、ROE、负债、现金流、收入规模 |
| 估值分 | 35% | 静态PE、预期PE、市销率、EV/EBITDA |
| 趋势分 | 35% | SMA均线位置、回撤、相对强弱、**时钟模型方向** |
| 入场分 | — | 综合以上三项 + 60日线位置修正 + 财报临近风险 |

### 时钟模型（趋势方向）

基于 SMA20/60/120 排列和线性回归斜率判断：

| 方向 | 触发条件 | 趋势分影响 | 操作建议 |
|------|---------|-----------|---------|
| **1点钟（强势）** | 均线多头排列 + 价格站上 SMA20 + 斜率>0.05 | +10 | 持有但追高需谨慎 |
| **2点钟（最佳）** | 均线多头排列 + 价格站上 SMA20 | +10 | 最佳买入区域 |
| **3点钟（犹豫）** | 均线缠绕，方向不明 | 0 | 观望为主 |
| **4-6点（下跌）** | 均线空头排列 + 价格在 SMA20 之下 | -15 | 坚决不抄底 |

### 红牌机制（一票否决）

| 红牌标签 | 触发条件 | 后果 |
|---------|---------|------|
| **经营现金流为负** | Operating Cash Flow ≤ 0 | 强制 D 级，入场分上限 30 |
| **故事驱动型** | EBIT 利润率 < 0 且 经营现金流 ≤ 0 | 强制 D 级，入场分上限 30 |
| 自由现金流为负 | FCF < 0 但经营现金流 > 0 | 警告标签，不影响信号 |
| 收入规模过小 | 总收入 < 1 亿美元 | 警告标签，质量分扣分 |

> 金融行业（Financial Services）豁免经营现金流红牌：银行/保险/资管的 OCF 因放贷扩张常为负，属于正常经营行为。

### 信号等级

| 信号 | 入场分范围 | 含义 |
|------|-----------|------|
| A | ≥ 78 | 强烈推荐买入 |
| B | ≥ 64 | 可关注 |
| C | ≥ 50 | 观望 |
| D | < 50 | 回避 |

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
| 分组查看 | 点击分组标签（七巨头、半导体与AI 等 18 个分组） |
| 表格排序 | 点击列头的排序按钮 |
| 评分拆解 | 点击每行 ▶ 按钮展开评分明细 + 公司详情 |
| 公司介绍 | 鼠标悬停公司名查看三段式详情，或展开评分拆解面板 |
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

编辑 `config/watchlist.toml`，当前覆盖 18 个分组、117 只标的：

```toml
[defaults]
benchmark = "SPY"

[groups]
"七巨头" = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA"]
"半导体与AI" = ["AVGO", "AMD", "TSM", "MU", "SNDK", "QCOM", "AMAT", "ARM", "TXN", "INTC", "LRCX", "KLAC"]
"云计算与软件" = ["CRM", "ADBE", "NOW", "SNOW", "ORCL", "WDAY", "PANW", "CRWD", "DDOG", "MDB", "ESTC", "CFLT"]
"金融" = ["JPM", "BAC", "GS", "V", "MA", "BX", "BRK-B", "SPGI", "BLK", "AXP"]
"医疗健康" = ["JNJ", "UNH", "LLY", "ABBV", "ISRG", "MRK", "TMO", "SYK", "DHR"]
"消费服务" = ["COST", "WMT", "KO", "PG", "PEP", "HD", "MCD", "NKE", "SBUX", "DIS"]
"工业与运输" = ["CAT", "GE", "HON", "UNP", "DE", "APH"]
"能源" = ["XOM", "CVX", "COP"]
"通信与电信" = ["T", "VZ", "TMUS"]
"国防与航天" = ["LMT", "NOC", "RTX", "PLTR", "ASTS", "RKLB", "LUNR", "RDW"]
"AI电力与能源" = ["VST", "CEG", "GEV", "BWXT", "TLN"]
"AI基础设施" = ["VRT", "ANET", "SMCI", "DELL", "PSTG", "NTAP", "CDNS", "SNPS", "NBIS"]
"加密货币" = ["COIN", "MSTR", "MARA", "RIOT", "HUT", "CIFR"]
"前沿科技" = ["IONQ", "RGTI"]
"基础设施REITs" = ["PLD", "AMT", "O"]
"宽基ETF" = ["SPY", "VOO", "QQQM", "IWM", "DIA"]
"行业ETF" = ["SMH", "SOXX", "XLE", "XLF", "ITA"]
"策略ETF" = ["SCHD", "VYM"]

[descriptions]
# 每只标的三段式中文介绍：公司介绍 | 商业模式 | 盈利模式
AAPL = "全球最大消费电子公司... | 硬件+软件+服务一体化闭环... | iPhone 硬件占收入 50%+..."
NVDA = "全球 AI 算力芯片霸主 | 设计 GPU 芯片由台积电代工... | 数据中心 GPU 卖给云厂商，毛利率 70%+..."
```

### 评分阈值配置

编辑 `config/scoring.toml` 调整质量因子阈值、估值区间、趋势加减分等，无需改源码。新增配置项：

```toml
[quality.operating_margins]      # EBIT 利润率因子
[quality.revenue]                 # 收入规模门槛（默认 1 亿美元）
[trend.direction]                 # 时钟模型加减分
```

---

## 项目结构

```text
config/
├── watchlist.toml                观察池、分组和公司介绍配置
└── scoring.toml                  评分阈值配置
src/stockscope/
├── cli.py                        CLI 入口（run / serve），并发控制 + 缓存共享
├── server.py                     FastAPI Web 服务
├── reports.py                    HTML 看板生成（含 JS 交互、时钟模型、红牌展示）
├── research_index.py             研报索引自动生成
├── scoring.py                    打分逻辑（时钟模型 / 红牌机制 / 质量 / 估值 / 趋势 / 入场）
├── fetchers/yahoo.py             Yahoo Finance 抓取器（本地缓存 + 请求节流 + 指数退避重试）
├── models.py                     数据模型
├── config.py                     配置加载
└── name_resolver.py              名称解析（缓存 + 自定义）

.claude/skills/stock-analysis/
├── SKILL.md                      Skill 定义
└── scripts/analyze.py            个股深度分析脚本

outputs/
├── latest/                       生成的报告文件（不提交 git）
└── cache/                        Yahoo 数据本地缓存
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

## 数据缓存策略

- 基本面数据（Summary）：2 小时 TTL，缓存到 `outputs/cache/yahoo_cache.json`
- 行情数据（Chart）：1 小时 TTL
- 请求节流：每次请求最小间隔 1.2 秒
- 重试机制：网络错误/限流时指数退避重试，最多 3 次（base 2s / 4s / 8s）
- 并发控制：3 worker + 0.3s 提交间隔

---

## 说明

- 当前版本覆盖**美股个股和 ETF**，A 股需新增抓取器。
- Yahoo Finance 公开接口可能变化；如需生产级稳定性建议迁移到 Polygon + SEC。
- 所有评级和信号仅用于研究分析，**不构成投资建议**。
- `outputs/` 目录已在 `.gitignore` 中，不会提交到仓库。
