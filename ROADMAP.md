# StockScope 产品功能改造计划

> 优先级：纯产品功能 > 架构优化 > 稳定性增强

---

## P0 - 报表增强（2 天）

### 任务 1: 运行摘要卡片
**目标**: 在 HTML 看板顶部展示运行元信息

**改动点**:
- `reports.py:write_dashboard()` - 在 header 区域添加运行摘要卡片
- 展示：运行时间、成功数/总数、A/B/C/D 信号分布、失败原因 top3
- `cli.py` - 收集统计信息传给 write_dashboard

**验收标准**:
```html
<!-- 期望效果 -->
<div class="summary-cards">
  <div class="card">运行时间: 2025-04-15 14:30</div>
  <div class="card">成功: 25/30</div>
  <div class="card">信号分布: A(3) B(8) C(10) D(4)</div>
</div>
```

---

### 任务 2: 失败原因汇总面板
**目标**: 在 HTML 底部展示 skipped 明细

**改动点**:
- `reports.py` - 添加 `_render_skipped_panel()` 函数
- 按错误类型分组：网络超时/数据缺失/其他
- 默认折叠，点击展开

---

## P1 - 评分可视化（3 天）

### 任务 3: 评分拆解详情
**目标**: 让用户看懂每个分数是怎么算出来的

**改动点**:
- `models.py:ScoredTicker` - 新增 `score_breakdown: dict` 字段
- `scoring.py` - 每个 score_* 函数返回 `(score, explanation)`
  - 示例: `band_score()` 返回 `"营收增长 12% >= 8%，+12分"`
- `reports.py:_render_row()` - 添加"展开详情"按钮

**数据模型**:
```python
score_breakdown = {
    "quality": {
        "total": 68,
        "items": [
            {"factor": "营收增长", "value": 0.12, "score": 12, "note": "12% >= 8%"},
            {"factor": "负债率", "value": 40, "score": 10, "note": "40 <= 60"},
        ]
    },
    "valuation": {...},
    "trend": {...},
    "adjustments": [...]
}
```

---

### 任务 4: ETF 评分规则差异化展示
**目标**: ETF 和股票在 UI 上明确区分评分逻辑

**改动点**:
- `reports.py:_render_explanation()` - 根据 asset_type 动态显示不同说明
- ETF 不显示质量分相关说明
- 添加提示："ETF 评分侧重估值与趋势，不评估个股基本面"

---

## P2 - 历史追踪（3 天）

### 任务 5: 历史快照归档
**目标**: 每次运行生成独立归档，支持回溯

**改动点**:
- `cli.py:run_command()` - 修改输出目录逻辑
  - 每次运行：`outputs/runs/{timestamp}/`
  - 保持 `outputs/latest/` 软链指向最新
- `reports.py` - 在 HTML footer 添加历史跳转链接

**目录结构**:
```
outputs/
├── latest -> runs/2025-04-15_143000/
└── runs/
    ├── 2025-04-15_143000/
    │   ├── signals.csv
    │   └── dashboard.html
    └── 2025-04-15_103000/
```

---

### 任务 6: 排名变化对比
**目标**: 对比本次与上次运行，显示排名升降

**改动点**:
- 新增 `reports.py:load_previous_run()` - 读取 outputs/latest 软链之前的指向
- 新增 `reports.py:compute_rank_delta()` - 计算排名变化
- `reports.py:_render_row()` - 添加变化箭头

**展示样式**:
```
代码    名称      信号  入场分   排名变化
AAPL    Apple     A     82     ↑ 5
MSFT    Microsoft B     76     ↓ 2
```

---

## P3 - 分组与筛选（4 天）

### 任务 7: 配置分组视图
**目标**: 按 watchlist 中的 groups 渲染分组标签页

**改动点**:
- `config.py` - 新增 `load_groups()` 返回分组结构
- `cli.py` - 将分组信息传递给 reports
- `reports.py:write_dashboard()` - 添加分组标签页
  - 默认 tab: "全部"
  - 动态 tabs: ETF / 核心成长 / 防御航天 / 高股息

**交互**:
```html
<div class="tabs">
  <button class="tab-button active" data-group="all">全部(30)</button>
  <button class="tab-button" data-group="etfs">ETF(9)</button>
  <button class="tab-button" data-group="core_growth">核心成长(11)</button>
  ...
</div>
```

---

### 任务 8: 前端筛选器
**目标**: 在 HTML 中添加实时筛选功能

**改动点**:
- `reports.py` - 在 signals table 上方添加筛选栏
  - 信号等级: 多选 [A] [B] [C] [D]
  - 资产类型: [股票] [ETF]
  - 入场分范围: 滑块 0-100
  - 搜索: 代码/名称模糊搜索
- 纯前端实现，不依赖后端

---

### 任务 9: 可交互排序
**目标**: 点击表头排序

**改动点**:
- `reports.py` - 为 th 添加 `data-sort` 属性和点击事件
- 支持：入场分/估值分/趋势分/质量分/距60日线 升降序
- 当前排序状态高亮显示

---

## P4 - 评分策略配置化（4 天）

### 任务 10: 权重配置迁移
**目标**: 把评分权重从代码移到配置文件

**改动点**:
- `config/watchlist.toml` - 新增 `[scoring.weights]`
```toml
[scoring.weights.stock]
valuation = 0.35
trend = 0.35
quality = 0.30

[scoring.weights.etf]
valuation = 0.45
trend = 0.55
```
- `scoring.py` - `score_stock_entry()` / `score_etf_entry()` 从配置读取权重
- `config.py` - 新增 `load_scoring_weights()`

---

### 任务 11: 阈值配置迁移
**目标**: 把评分阈值配置化

**改动点**:
- `config/watchlist.toml` - 新增 `[scoring.thresholds]`
```toml
[scoring.thresholds.stock.quality]
revenue_growth = { good = 0.08, ok = 0.03, bad = -0.05 }
profit_margins = { good = 0.18, ok = 0.10, bad = 0.03 }
# ...

[scoring.thresholds.stock.valuation]
trailing_pe = { good = 18, ok = 28, bad = 45 }
# ...

[scoring.thresholds.etf]
trailing_pe = { good = 18, ok = 24, bad = 32 }
# ...
```
- `scoring.py` - 所有评分函数支持传入阈值配置，无配置则用默认值

---

### 任务 12: 信号等级阈值配置
**目标**: A/B/C/D 分界点可配置

**改动点**:
- `config/watchlist.toml`:
```toml
[scoring.signals]
A = 78
B = 64
C = 50
```
- `scoring.py:finalize_signal()` - 从配置读取阈值

---

## 优先级建议（产品价值排序）

| 推荐顺序 | 任务 | 产品价值 | 预计时间 |
|---------|------|---------|---------|
| 1 | 任务 7（分组视图） | ⭐⭐⭐ 一眼看清各板块机会 | 1 天 |
| 2 | 任务 5（历史快照）+ 6（排名变化） | ⭐⭐⭐ 追踪信号变化 | 2 天 |
| 3 | 任务 8（筛选器）+ 9（排序） | ⭐⭐⭐ 快速定位标的 | 2 天 |
| 4 | 任务 3（评分拆解） | ⭐⭐ 理解分数由来 | 2 天 |
| 5 | 任务 10-12（策略配置化） | ⭐⭐ 支持 A/B 测试不同策略 | 3 天 |
| 6 | 任务 1-2（报表摘要） | ⭐ 运行概览 | 1 天 |

**如果想一周内交付最大价值**：7 → 5+6 → 8+9（分组+历史+筛选）

---

## 暂不排期的任务（非产品功能）

- [ ] benchmark 配置闭环（数据稳定性）
- [ ] ETF 数据口径修正（数据稳定性）
- [ ] AppService/Runner 拆分（架构整理）
- [ ] MarketDataProvider 抽象（架构整理）
- [ ] 本地缓存层（数据稳定性）
- [ ] 重试与退避（数据稳定性）
- [ ] 测试覆盖补充（交付质量）
- [ ] CI 接入（交付质量）
