"""美国经济核心指标页面 — 18 个指标，4 大分类，实时数据 + 总信号评分."""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from html import escape
from typing import Any

import pandas as pd

# ============================================================
# 指标定义
# ============================================================

INDICATORS: list[dict[str, Any]] = [
    # ========================
    # 一、消费端 Consumption
    # ========================
    {
        "id": "employment",
        "category": "consumption",
        "category_name": "消费端",
        "title": "就业情况",
        "subtitle": "初次申领失业金 / 连续申领失业金 / 非农就业",
        "timestamp": "[00:39]",
        "data_source": "fred",
        "series": [
            {"name": "初次申领失业金", "fred_id": "ICSA", "unit": "万人/周", "decimals": 1, "divide_by": 10000},
            {"name": "连续申领失业金", "fred_id": "CCSA", "unit": "万人", "decimals": 1, "divide_by": 10000},
            {"name": "非农就业总人数", "fred_id": "PAYEMS", "unit": "亿人", "decimals": 3, "divide_by": 100000},
        ],
        "eval_type": "higher_is_worse",
        "eval_field": "ICSA",
        "guidance": "就业是消费的前提。失业金申领人数上升 → 消费萎缩 → 企业盈利下滑 → 股市下跌。非农就业是每月最重要的宏观数据之一。",
        "threshold_high": "初请失业金 > 30 万/周（恶化信号）",
        "threshold_low": "初请失业金 < 20 万/周（健康信号）",
        "meaning_high": "劳动力市场恶化，经济衰退风险上升，对股市利空",
        "meaning_low": "劳动力市场强劲，消费有支撑，对股市利好",
    },
    {
        "id": "personal_finance",
        "category": "consumption",
        "category_name": "消费端",
        "title": "个人财务",
        "subtitle": "个人收入 / 消费支出 / 储蓄率（均为同比增幅）",
        "timestamp": "[01:12]",
        "data_source": "fred",
        "series": [
            {"name": "个人收入（同比）", "fred_id": "PI", "unit": "%", "decimals": 1, "calc_yoy": True},
            {"name": "个人消费支出（同比）", "fred_id": "PCE", "unit": "%", "decimals": 1, "calc_yoy": True},
            {"name": "个人储蓄率", "fred_id": "PSAVERT", "unit": "%", "decimals": 1},
        ],
        "eval_type": "higher_is_better",
        "eval_field": "PCE_yoy",
        "guidance": "消费支出是最核心的指标。只要民众有钱且敢花钱，美国经济就不会太差。储蓄率过高反而说明消费意愿不足。",
        "threshold_high": "消费支出同比 > 6%（偏热，可能引发通胀担忧）",
        "threshold_low": "消费支出同比 < 2%（偏冷，经济放缓）",
        "meaning_high": "消费旺盛支撑经济，但过高可能引发通胀担忧，美联储不敢轻易降息",
        "meaning_low": "消费疲软预示经济放缓，企业盈利承压，但可能倒逼美联储降息",
    },
    {
        "id": "home_sales",
        "category": "consumption",
        "category_name": "消费端",
        "title": "房屋销售",
        "subtitle": "成屋销售 / 新屋销售 / 房价指数 / 房价中位数",
        "timestamp": "[01:47]",
        "data_source": "fred",
        "series": [
            {"name": "成屋销售（年化万套）", "fred_id": "EXHOSLUSM495S", "unit": "万套", "decimals": 1, "divide_by": 10000},
            {"name": "新屋销售（年化万套）", "fred_id": "HSN1F", "unit": "万套", "decimals": 1, "divide_by": 10},
            {"name": "20城房价指数（同比）", "fred_id": "SPCS20RSA", "unit": "%", "decimals": 1, "calc_yoy": True},
            {"name": "新屋销售中位价", "fred_id": "MSPUS", "unit": "万美元", "decimals": 1, "divide_by": 10000},
        ],
        "eval_type": "higher_is_better",
        "eval_field": "HSN1F",
        "guidance": "房子是最大消费品，牵连建筑、家具、家电、金融等上下游产业链。房价温和上涨利好消费（财富效应），但暴涨有泡沫风险。",
        "threshold_high": "房价指数同比 > 10%（泡沫风险）",
        "threshold_low": "成屋销售同比持续为负（房市冰冻）",
        "meaning_high": "房市过热，财富效应支撑消费，但若泡沫破裂将重创经济",
        "meaning_low": "房市降温拖累经济，房贷利率高企抑制需求，可能倒逼美联储放松",
    },
    {
        "id": "auto_sales",
        "category": "consumption",
        "category_name": "消费端",
        "title": "汽车销售",
        "subtitle": "全美汽车销量（TOTALSA 单位：百万辆）",
        "timestamp": "[02:08]",
        "data_source": "fred",
        "series": [
            {"name": "全美汽车年化销量", "fred_id": "TOTALSA", "unit": "百万辆", "decimals": 1},
        ],
        "eval_type": "higher_is_better",
        "eval_field": "TOTALSA",
        "guidance": "汽车是第二大消费品，对利率高度敏感，是货币政策传导的晴雨表。高利率 → 车贷成本上升 → 销量下降。二手车价格也是通胀的先行指标。",
        "threshold_high": "年化销量 > 17.0 百万辆（消费强劲）",
        "threshold_low": "年化销量 < 14.0 百万辆（消费疲软）",
        "meaning_high": "消费信心强，供应链健康，对利率不敏感 → 经济韧性好",
        "meaning_low": "高利率抑制大额消费，消费者信心不足，汽车股和消费股承压",
    },
    {
        "id": "retail",
        "category": "consumption",
        "category_name": "消费端",
        "title": "零售业态",
        "subtitle": "零售总额 / 电子商务零售额（均为同比增幅）",
        "timestamp": "[02:38]",
        "data_source": "fred",
        "series": [
            {"name": "零售额（同比）", "fred_id": "RSAFS", "unit": "%", "decimals": 1, "calc_yoy": True},
            {"name": "电子商务零售额（同比）", "fred_id": "ECOMSA", "unit": "%", "decimals": 1, "calc_yoy": True},
        ],
        "eval_type": "higher_is_better",
        "eval_field": "RSAFS_yoy",
        "guidance": "零售是消费最直接的体现，反映当月消费热度。红皮书同店销售为商业数据不可得，用零售总额替代。非实体店零售反映线上消费趋势。",
        "threshold_high": "零售额同比 > 8%（消费过热）",
        "threshold_low": "零售额同比 < 2%（消费萎缩）",
        "meaning_high": "消费强劲，经济有韧性，零售股和消费股受益",
        "meaning_low": "消费者收紧支出，经济放缓信号，防御性板块相对占优",
    },
    # ========================
    # 二、供给端 Supply
    # ========================
    {
        "id": "housing_supply",
        "category": "supply",
        "category_name": "供给端",
        "title": "房屋供给",
        "subtitle": "建房许可 / 新屋开工 / 房屋库存",
        "timestamp": "[03:42]",
        "data_source": "fred",
        "series": [
            {"name": "建房许可（年化万套）", "fred_id": "PERMIT", "unit": "万套", "decimals": 1, "divide_by": 10},
            {"name": "新屋开工（年化万套）", "fred_id": "HOUST", "unit": "万套", "decimals": 1, "divide_by": 10},
            {"name": "房屋库存（月供应量）", "fred_id": "MSACSR", "unit": "个月", "decimals": 1},
        ],
        "eval_type": "higher_is_better",
        "eval_field": "PERMIT",
        "guidance": "建房许可是经济的先行指标，领先实际经济活动 6-12 个月。库存是最关键的指标——库存下降意味着供不应求、房价有上涨压力。",
        "threshold_high": "新屋开工 > 160 万套/年（供给扩张）",
        "threshold_low": "新屋开工 < 120 万套/年（供给收缩）",
        "meaning_high": "开发商看好后市，供给扩张带动建筑就业和上下游产业链",
        "meaning_low": "开发商谨慎，未来 6-12 个月建筑业就业和建材消费承压",
    },
    {
        "id": "manufacturing",
        "category": "supply",
        "category_name": "供给端",
        "title": "制造业订单",
        "subtitle": "耐用品订单 / 制造业 PMI（ISM 官网发布，FRED 不直接提供）",
        "timestamp": "[04:29]",
        "data_source": "fred",
        "series": [
            {"name": "耐用品订单（百万美元）", "fred_id": "DGORDER", "unit": "百万美元", "decimals": 0},
            {"name": "ISM 制造业 PMI", "fred_id": None, "unit": "指数", "decimals": 1, "note": "FRED 无此数据，请访问 ismworld.org"},
        ],
        "eval_type": "higher_is_better",
        "eval_field": "DGORDER",
        "guidance": "订单和 PMI 是经济最重要的先行指标。PMI 下行往往领先 GDP 下行 3-6 个月。耐用品订单是最直接的制造业需求指标。PMI < 50 = 制造业收缩，> 50 = 扩张。",
        "threshold_high": "PMI > 55 或耐用品订单连续增长（扩张强劲）",
        "threshold_low": "PMI < 45 或耐用品订单连续 3 个月下滑（深度收缩）",
        "meaning_high": "制造业扩张，企业信心强，经济处于上行周期，工业股和周期股受益",
        "meaning_low": "制造业收缩通常领先整体经济下行，企业盈利预期下调，防御板块占优",
    },
    {
        "id": "wei",
        "category": "supply",
        "category_name": "供给端",
        "title": "WEI 指数",
        "subtitle": "纽约联储每周经济指数（Weekly Economic Index）",
        "timestamp": "[05:33]",
        "data_source": "fred",
        "series": [
            {"name": "WEI 指数", "fred_id": "WEI", "unit": "指数", "decimals": 2},
        ],
        "eval_type": "higher_is_better",
        "eval_field": "WEI",
        "guidance": "WEI 是美国 GDP 的周度先行指标，由纽约联储编制，综合了消费、就业、生产等 10 个高频指标。连续进入负值区 = 衰退概率极高。",
        "threshold_high": "> 3%（经济强劲增长）",
        "threshold_low": "连续 < 0（大概率步入衰退）",
        "meaning_high": "经济增长强劲，企业盈利有望超预期，利好股市",
        "meaning_low": "连续负值是衰退最可靠的信号之一，历史上每次衰退前 WEI 都进入负值区，重大利空",
    },
    {
        "id": "copper_gold",
        "category": "supply",
        "category_name": "供给端",
        "title": "铜金比",
        "subtitle": "铜价 / 金价 — PPI 和 PMI 的先行指标",
        "timestamp": "[06:03]",
        "data_source": "yfinance",
        "series": [
            {"name": "铜金比", "fred_id": None, "unit": "比值", "decimals": 4},
        ],
        "eval_type": "higher_is_better",
        "eval_field": "copper_gold_ratio",
        "guidance": "铜 = 工业需求（经济好不好），金 = 避险需求（市场怕不怕）。比值上升 = 经济上行、通胀预期上升、PPI 和 PMI 即将改善。比值下降 = 避险情绪升温、预期经济放缓。",
        "threshold_high": "比值 > 0.0020（铜强金弱，风险偏好，经济扩张）",
        "threshold_low": "比值 < 0.0012（铜弱金强，避险模式，经济放缓）",
        "meaning_high": "工业活动旺盛，通胀预期上行，经济扩张周期，周期股和价值股占优",
        "meaning_low": "市场避险情绪浓，预期经济放缓或衰退，防御股和黄金股跑赢，成长股承压",
    },
    {
        "id": "oil_gold",
        "category": "supply",
        "category_name": "供给端",
        "title": "油金比",
        "subtitle": "原油价格 / 黄金价格 — CPI 的先行指标",
        "timestamp": "[06:38]",
        "data_source": "yfinance",
        "series": [
            {"name": "油金比", "fred_id": None, "unit": "比值", "decimals": 5},
        ],
        "eval_type": "neutral_range",
        "eval_field": "oil_gold_ratio",
        "guidance": "原油是所有商品的底层成本。油价上涨 → 所有生产成本上升 → CPI 上升。油金比是通胀（CPI）的先行指标。过高 = 通胀压力，过低 = 通缩风险。",
        "threshold_high": "比值 > 0.025（通胀压力上升，美联储偏鹰）",
        "threshold_low": "比值 < 0.015（通缩压力，美联储有降息空间）",
        "meaning_high": "通胀压力上升，美联储可能加息或维持高利率，对高估值成长股利空，能源股受益",
        "meaning_low": "通胀压力低甚至通缩，美联储有降息空间，利好股市整体估值，但能源股承压",
    },
    # ========================
    # 三、利率 Interest Rates
    # ========================
    {
        "id": "interest_rates",
        "category": "interest",
        "category_name": "利率",
        "title": "核心利率",
        "subtitle": "美联储目标利率 / 国债收益率 / 利差（期限结构）",
        "timestamp": "[09:23]",
        "data_source": "fred",
        "series": [
            {"name": "联邦基金利率（上限）", "fred_id": "DFEDTARU", "unit": "%", "decimals": 2},
            {"name": "10年期国债收益率", "fred_id": "DGS10", "unit": "%", "decimals": 2},
            {"name": "2年期国债收益率", "fred_id": "DGS2", "unit": "%", "decimals": 2},
            {"name": "5年期国债收益率", "fred_id": "DGS5", "unit": "%", "decimals": 2},
            {"name": "10Y-2Y 利差", "fred_id": "T10Y2Y", "unit": "%", "decimals": 2},
        ],
        "eval_type": "rate_special",
        "eval_field": "T10Y2Y",
        "guidance": "利率 = 资本成本 + 投资机会成本。短期利率 > 长期利率（利差为负，即「利率倒挂」）= 市场预期未来经济衰退、迫使美联储降息。历史上每次倒挂后 12-18 个月均出现衰退。",
        "threshold_high": "利差 > 0.5%（正常，经济预期健康）",
        "threshold_low": "利差 < 0（利率倒挂 → 衰退预警）",
        "meaning_high": "收益率曲线正常，经济预期改善，银行股受益于陡峭曲线（借短贷长利润高）",
        "meaning_low": "利率倒挂是衰退最经典的先行指标，预示未来 12-18 个月衰退概率极大，对股市是重大利空预警",
    },
    {
        "id": "credit_spread",
        "category": "interest",
        "category_name": "利率",
        "title": "信用利差",
        "subtitle": "高收益企业债利率 - 10 年期美债收益率",
        "timestamp": "[10:44]",
        "data_source": "fred",
        "series": [
            {"name": "CCC 级及以下高收益债利差", "fred_id": "BAMLH0A3HYC", "unit": "%", "decimals": 2},
        ],
        "eval_type": "higher_is_worse",
        "eval_field": "BAMLH0A3HYC",
        "guidance": "信用利差 = 低评级企业债收益率 - 无风险利率。利差快速扩大 = 投资者认为企业违约风险大增、风险偏好急剧下降、信贷市场在冻结。",
        "threshold_high": "利差 > 10%（极度恐慌，信贷危机级别）",
        "threshold_low": "利差 < 4%（正常/乐观，信贷环境宽松）",
        "meaning_high": "信贷市场冻结，高风险企业融资困难，中小盘股暴跌，但极度恐慌往往是股市底部的反向信号",
        "meaning_low": "市场风险偏好正常，企业融资环境宽松，利好股市，尤其是高杠杆行业",
    },
    # ========================
    # 四、市场与情绪 Market & Sentiment
    # ========================
    {
        "id": "aaii_sentiment",
        "category": "sentiment",
        "category_name": "市场情绪",
        "title": "散户情绪（AAII）",
        "subtitle": "AAII 投资者看涨比例 - 看跌比例（每周三发布）",
        "timestamp": "[11:34]",
        "data_source": "website",
        "series": [
            {"name": "AAII 看涨-看跌差值", "fred_id": None, "unit": "%", "decimals": 1, "note": "FRED 无此数据，请访问 aaii.com/sentimentsurvey"},
        ],
        "eval_type": "inverse_extreme",
        "eval_field": "AAII",
        "guidance": "散户是经典的「反向指标」。当散户极度看涨（差值 > 25%），说明散户仓位已满、后续买盘不足，市场阶段性见顶。反之当散户极度恐慌，往往是底部。",
        "threshold_high": "看涨 - 看跌差值 > +25%（极度乐观 → 见顶信号）",
        "threshold_low": "看涨 - 看跌差值 < -20%（极度悲观 → 见底信号）",
        "meaning_high": "散户极度乐观 = 仓位已打满，后续购买力枯竭，市场大概率阶段性见顶，是减仓信号",
        "meaning_low": "散户恐慌割肉、筹码换手到机构手中，市场接近底部，是逆向买入的绝佳时机",
    },
    {
        "id": "naaim_exposure",
        "category": "sentiment",
        "category_name": "市场情绪",
        "title": "机构情绪（NAAIM）",
        "subtitle": "NAAIM 投资经理风险敞口指数",
        "timestamp": "[12:16]",
        "data_source": "website",
        "series": [
            {"name": "NAAIM 敞口指数", "fred_id": None, "unit": "指数", "decimals": 0},
        ],
        "eval_type": "inverse_extreme",
        "eval_field": "NAAIM",
        "guidance": "机构和散户一样追涨杀跌。敞口 > 100 = 机构加杠杆做多、仓位已满 = 后续买盘不足。敞口 < 30 = 机构极度防御、大量现金在场边 = 反弹蓄势待发。",
        "threshold_high": "敞口 > 100（机构加杠杆做多，过于拥挤）",
        "threshold_low": "敞口 < 30（机构极度防御，现金充裕）",
        "meaning_high": "机构集体看多仓位已满，后续购买力枯竭，风险积聚，是见顶预警",
        "meaning_low": "机构仓位极轻、大量现金在场边，一旦情绪反转有巨大买入动力，是抄底机会",
    },
    {
        "id": "put_call_ratio",
        "category": "sentiment",
        "category_name": "市场情绪",
        "title": "Put/Call 成交量比",
        "subtitle": "股指看跌期权 / 看涨期权成交量",
        "timestamp": "[12:52]",
        "data_source": "website",
        "series": [
            {"name": "CBOE Put/Call Ratio", "fred_id": None, "unit": "比值", "decimals": 2, "note": "FRED 无此数据，请访问 cboe.com 或 Yahoo Finance"},
        ],
        "eval_type": "inverse_extreme",
        "eval_field": "PCR",
        "guidance": "Put/Call Ratio 是情绪的极端指标。当看跌期权交易远超看涨期权（> 1.0），说明市场过度恐慌、对冲需求暴增，往往对应阶段性底部。",
        "threshold_high": "> 1.0（恐惧至极 → 底部信号）",
        "threshold_low": "< 0.6（贪婪蔓延 → 顶部信号）",
        "meaning_high": "市场恐慌至极，大量资金买入看跌期权对冲，往往是市场阶段性底部的可靠信号",
        "meaning_low": "市场过度乐观、贪婪情绪蔓延，看涨期权投机盛行，往往对应阶段性顶部",
    },
    {
        "id": "cftc_positions",
        "category": "sentiment",
        "category_name": "市场情绪",
        "title": "CFTC 大机构期货持仓",
        "subtitle": "大型机构在股指期货上的空头仓位",
        "timestamp": "[13:59]",
        "data_source": "website",
        "series": [
            {"name": "CFTC 空头仓位", "fred_id": None, "unit": "需手动获取", "decimals": 0},
        ],
        "eval_type": "inverse_extreme",
        "eval_field": "CFTC",
        "guidance": "当大型机构空头仓位创历史新高、但市场不跌反涨时，会逼迫空头买入平仓止损，引发史诗级「轧空」(Short Squeeze)暴涨行情。这是最强力的短期看涨信号。",
        "threshold_high": "空头仓位创历史新高 + 市场不跌（轧空条件）",
        "threshold_low": "空头仓位处于历史低位（轧空风险解除）",
        "meaning_high": "空头极度拥挤 + 市场不配合下跌 = 轧空的完美条件，一旦触发将是爆炸性上涨",
        "meaning_low": "空头已大部分平仓，轧空风险解除，市场回归正常多空博弈",
    },
    {
        "id": "market_breadth",
        "category": "sentiment",
        "category_name": "市场情绪",
        "title": "市场宽度",
        "subtitle": "标普500 中股价高于 50/200 日均线的股票比例",
        "timestamp": "[15:28]",
        "data_source": "yfinance",
        "series": [
            {"name": "高于 50 日均线比例", "fred_id": None, "unit": "%", "decimals": 0},
            {"name": "高于 200 日均线比例", "fred_id": None, "unit": "%", "decimals": 0},
        ],
        "eval_type": "inverse_extreme",
        "eval_field": "breadth_50",
        "guidance": "测量市场上涨的「参与度」。少数大盘股拉动指数上涨 ≠ 真正的牛市。> 85% = 买盘接近枯竭，< 15% = 市场被全面错杀。极端值 大概率预示中长期趋势反转。",
        "threshold_high": "> 85%（极度狂热，几乎所有股票都在涨 → 见顶）",
        "threshold_low": "< 15%（极度恐慌，几乎所有股票都在跌 → 见底）",
        "meaning_high": "买盘接近枯竭、后续推力不足，大概率中长期见顶，减仓锁定利润",
        "meaning_low": "抛售过度、市场被全面错杀，大概率中长期见底，是难得的全面抄底机会",
    },
    {
        "id": "sector_rotation",
        "category": "sentiment",
        "category_name": "市场情绪",
        "title": "行业轮动",
        "subtitle": "11 大板块 ETF 相对 SPY 的强弱 — Risk On / Risk Off",
        "timestamp": "[16:37]",
        "data_source": "yfinance",
        "series": [
            {"name": "防御板块相对强度", "fred_id": None, "unit": "排名", "decimals": 0},
        ],
        "eval_type": "sector_special",
        "eval_field": "sector_rotation",
        "guidance": "当防御性板块（必须消费 XLP、医疗 XLV、公用事业 XLU）相对 SPY 持续走强时，说明市场风险偏好正在降低（Risk Off），资金在避险。反之科技 XLK、消费周期 XLY 领涨时 = Risk On。",
        "threshold_high": "防御板块排名靠前（Risk Off，避险模式）",
        "threshold_low": "科技/周期板块排名靠前（Risk On，进攻模式）",
        "meaning_high": "防御走强 = 资金撤退到避险资产，通常是市场下跌的前兆，应减仓周期股和科技股",
        "meaning_low": "周期/科技走强 = 市场风险偏好上升，资金追求成长，牛市健康运行，可积极配置",
    },
]

CATEGORIES = [
    {"id": "consumption", "name": "消费端", "icon": "C", "desc": "消费占 GDP 约 70%，有工作→有收入→敢花钱→经济好"},
    {"id": "supply", "name": "供给端", "icon": "S", "desc": "先行指标，领先消费 3-6 个月，反映生产端信心"},
    {"id": "interest", "name": "利率", "icon": "I", "desc": "资金的价格标尺，资本成本 + 投资机会成本 + 汇率价值"},
    {"id": "sentiment", "name": "市场情绪", "icon": "M", "desc": "极端情绪往往预示趋势反转，散户和机构都是情绪驱动的"},
]

SECTOR_ETFS = {
    "XLK": "科技", "XLV": "医疗", "XLF": "金融", "XLE": "能源",
    "XLI": "工业", "XLP": "必须消费", "XLRE": "房地产",
    "XLU": "公用事业", "XLB": "原材料", "XLY": "可选消费", "XLC": "通信",
}


# ============================================================
# 数据获取
# ============================================================

def _get_fred_client():
    api_key = os.environ.get("FRED_API_KEY", "")
    if not api_key:
        return None
    try:
        from fredapi import Fred
        return Fred(api_key=api_key)
    except Exception:
        return None


def fetch_fred_data() -> dict[str, float | None]:
    """拉取所有 FRED 指标的当前值，并对 calc_yoy 系列计算同比."""
    fred = _get_fred_client()
    if fred is None:
        return {}

    # 收集所有需要的 FRED series ID
    series_ids: set[str] = set()
    yoy_series: dict[str, str] = {}  # fred_id → yoy_key (e.g., "PCE_yoy")
    for ind in INDICATORS:
        if ind["data_source"] != "fred":
            continue
        for s in ind["series"]:
            sid = s.get("fred_id")
            if sid:
                series_ids.add(sid)
                if s.get("calc_yoy"):
                    yoy_series[sid] = f"{sid}_yoy"

    result: dict[str, float | None] = {}
    today = datetime.now()
    # 拉 3 年数据以计算同比
    start = today - timedelta(days=365 * 3)

    for sid in series_ids:
        try:
            series = fred.get_series(sid, observation_start=start.strftime("%Y-%m-%d"))
            series = series.dropna()
            if len(series) > 0:
                # 最新值
                result[sid] = float(series.iloc[-1])
                # 计算同比
                if sid in yoy_series:
                    yoy_val = _compute_yoy(series)
                    result[yoy_series[sid]] = yoy_val
        except Exception:
            result[sid] = None
            if sid in yoy_series:
                result[yoy_series[sid]] = None

    return result


def _compute_yoy(series: pd.Series) -> float | None:
    """计算同比增幅：(最新值 - 12个月前值) / 12个月前值 * 100."""
    if len(series) < 13:
        return None
    idx = series.index
    latest_date = idx[-1]
    # 找大约 12 个月前的日期
    year_ago = latest_date - pd.DateOffset(months=12)
    # 找最近的观测值
    before_mask = idx <= year_ago
    if before_mask.sum() == 0:
        return None
    past_val = float(series[before_mask].iloc[-1])
    current_val = float(series.iloc[-1])
    if past_val == 0:
        return None
    return round((current_val - past_val) / past_val * 100, 1)


def fetch_yfinance_data() -> dict[str, Any]:
    """拉取 yfinance 市场数据：铜金比、油金比、市场宽度、行业轮动."""
    import yfinance as yf

    result: dict[str, Any] = {}

    # 铜金比
    try:
        copper = yf.Ticker("HG=F")
        gold = yf.Ticker("GC=F")
        cp = copper.history(period="5d")
        gp = gold.history(period="5d")
        if not cp.empty and not gp.empty:
            copper_price = float(cp["Close"].iloc[-1])
            gold_price = float(gp["Close"].iloc[-1])
            result["copper_gold_ratio"] = round(copper_price / gold_price, 4) if gold_price else None
        else:
            result["copper_gold_ratio"] = None
    except Exception:
        result["copper_gold_ratio"] = None

    # 油金比
    try:
        oil = yf.Ticker("CL=F")
        op = oil.history(period="5d")
        if not op.empty and not gp.empty:
            oil_price = float(op["Close"].iloc[-1])
            gold_price2 = float(gp["Close"].iloc[-1]) if gp is not None and not gp.empty else None
            if gold_price2 is None:
                gold2 = yf.Ticker("GC=F")
                gp2 = gold2.history(period="5d")
                gold_price2 = float(gp2["Close"].iloc[-1]) if not gp2.empty else None
            result["oil_gold_ratio"] = round(oil_price / gold_price2, 5) if (oil_price and gold_price2) else None
        else:
            result["oil_gold_ratio"] = None
    except Exception:
        result["oil_gold_ratio"] = None

    # 市场宽度（S&P 500 成分股高于 SMA50 / SMA200 的比例）
    result.update(_fetch_market_breadth())

    # 行业轮动
    result.update(_fetch_sector_rotation())

    return result


def _fetch_market_breadth() -> dict[str, Any]:
    """计算 S&P 500 市场宽度."""
    import yfinance as yf

    result: dict[str, Any] = {"breadth_50": None, "breadth_200": None}
    try:
        sp500 = yf.Ticker("^GSPC")
        # 使用 SPY 代理 S&P 500
        spy = yf.Ticker("SPY")
        # 用常见的大盘股代表市场宽度（S&P 500 top holdings + sector leaders）
        proxy_tickers = [
            "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "BRK-B",
            "JPM", "V", "JNJ", "WMT", "PG", "MA", "UNH", "HD", "BAC", "XOM",
            "DIS", "NFLX", "ADBE", "CRM", "AMD", "INTC", "CSCO", "PEP", "KO",
            "TMO", "ABT", "MCD", "WFC", "QCOM", "TXN", "AMGN", "IBM", "CAT",
            "GS", "BLK", "AXP", "SPGI", "MS", "PLTR", "UBER", "PANW",
            "XLK", "XLV", "XLF", "XLE", "XLI", "XLP", "XLRE", "XLU", "XLB", "XLY", "XLC",
        ]

        above_50 = 0
        above_200 = 0
        valid = 0
        for ticker in proxy_tickers:
            try:
                t = yf.Ticker(ticker)
                hist = t.history(period="1y")
                if len(hist) < 200:
                    continue
                close = float(hist["Close"].iloc[-1])
                sma50 = float(hist["Close"].rolling(window=50).mean().iloc[-1])
                sma200 = float(hist["Close"].rolling(window=200).mean().iloc[-1])
                if close > sma50:
                    above_50 += 1
                if close > sma200:
                    above_200 += 1
                valid += 1
            except Exception:
                continue

        if valid > 0:
            result["breadth_50"] = round(above_50 / valid * 100, 0)
            result["breadth_200"] = round(above_200 / valid * 100, 0)
    except Exception:
        pass

    return result


def _fetch_sector_rotation() -> dict[str, Any]:
    """行业轮动：计算 11 个板块 ETF 相对 SPY 的相对强度."""
    import yfinance as yf

    result: dict[str, Any] = {"sector_rotation": None, "sector_details": []}
    try:
        spy = yf.Ticker("SPY")
        spy_hist = spy.history(period="1mo")
        if spy_hist.empty:
            return result
        spy_ret = (float(spy_hist["Close"].iloc[-1]) / float(spy_hist["Close"].iloc[0]) - 1) * 100

        sectors = []
        for ticker, name in SECTOR_ETFS.items():
            try:
                t = yf.Ticker(ticker)
                hist = t.history(period="1mo")
                if hist.empty:
                    continue
                ret = (float(hist["Close"].iloc[-1]) / float(hist["Close"].iloc[0]) - 1) * 100
                rs = ret - spy_ret  # 相对强度
                sectors.append({"ticker": ticker, "name": name, "return": round(ret, 2), "rs": round(rs, 2)})
            except Exception:
                continue

        sectors.sort(key=lambda x: x["rs"], reverse=True)
        result["sector_details"] = sectors

        # 判断 Risk On/Off
        if sectors:
            # 防御性：XLP(必须消费), XLV(医疗), XLU(公用事业)
            defensive = [s for s in sectors if s["ticker"] in ("XLP", "XLV", "XLU")]
            cyclical = [s for s in sectors if s["ticker"] in ("XLK", "XLY", "XLI", "XLF")]
            def_avg = sum(s["rs"] for s in defensive) / len(defensive) if defensive else 0
            cyc_avg = sum(s["rs"] for s in cyclical) / len(cyclical) if cyclical else 0
            result["sector_rotation"] = "risk_off" if def_avg > cyc_avg else "risk_on"
    except Exception:
        pass

    return result


# ============================================================
# 信号评估
# ============================================================

def _safe_float(value, default=None):
    """安全转换，NaN 返回 None."""
    if value is None:
        return default
    try:
        v = float(value)
        if pd.isna(v):
            return default
        return v
    except (ValueError, TypeError):
        return default


def _calc_pct_change(series_id: str, fred_data: dict) -> float | None:
    """从 FRED 数据计算同比变化."""
    # FRED 数据只有最新值，同比需要拉历史数据对比
    # 简化处理：返回 raw value，在页面展示时注明
    return fred_data.get(series_id)


def evaluate_single_indicator(ind: dict, fred_data: dict, market_data: dict) -> tuple[int, dict]:
    """评估单个指标，返回 (方向, 详情字典)。
    方向：+1 利好，0 中性，-1 利空
    """
    details: dict[str, Any] = {
        "indicator_id": ind["id"],
        "title": ind["title"],
        "direction": 0,
        "direction_text": "中性",
        "dir_class": "neutral",
        "current_values": [],
        "summary": "",
    }
    direction = 0

    eval_type = ind.get("eval_type", "higher_is_better")
    eval_field = ind.get("eval_field", "")

    # 收集当前值
    for s in ind["series"]:
        sid = s.get("fred_id")
        val = None
        raw_val = None
        if ind["data_source"] == "fred" and sid:
            if s.get("calc_yoy"):
                # 同比系列使用 _yoy 键
                raw_val = fred_data.get(f"{sid}_yoy")
            else:
                raw_val = fred_data.get(sid)
        elif ind["data_source"] == "yfinance":
            raw_val = market_data.get(eval_field)

        if raw_val is not None:
            raw_val = _safe_float(raw_val)
            div = s.get("divide_by", 1)
            if div != 1 and raw_val is not None:
                val = raw_val / div
            else:
                val = raw_val

            details["current_values"].append({
                "name": s["name"],
                "value": round(val, s.get("decimals", 1)) if val is not None else None,
                "unit": s.get("unit", ""),
                "fred_id": sid,
            })

    # 特殊评估逻辑
    actual_val = None
    if eval_field and market_data.get(eval_field) is not None:
        actual_val = _safe_float(market_data.get(eval_field))
    elif eval_field:
        actual_val = _safe_float(fred_data.get(eval_field))
    if actual_val is None and details["current_values"]:
        actual_val = details["current_values"][0].get("value")

    details["_raw_eval"] = actual_val

    if eval_type == "higher_is_better":
        if actual_val is None:
            direction = 0
            details["summary"] = "数据暂不可用，无法判断"
        elif ind["id"] == "personal_finance" and actual_val is not None:
            # 消费支出同比判断
            if actual_val > 6:
                direction = 0  # 偏热，中性偏警惕
                details["summary"] = f"消费支出同比 {actual_val:.1f}%，偏热，通胀担忧仍在"
            elif actual_val >= 2:
                direction = 1
                details["summary"] = f"消费支出同比 {actual_val:.1f}%，健康区间"
            else:
                direction = -1
                details["summary"] = f"消费支出同比 {actual_val:.1f}%，消费疲软"
        elif ind["id"] == "home_sales":
            # HSN1F raw = thousands; show 万套
            hsn_wan = actual_val / 10 if actual_val is not None else 0
            direction = 1  # default bullish if data available
            details["summary"] = f"新屋销售年化 {hsn_wan:.1f} 万套"
        elif ind["id"] == "auto_sales":
            if actual_val > 17:
                direction = 1
                details["summary"] = f"汽车年化销量 {actual_val:.1f} 百万辆，消费强劲"
            elif actual_val >= 14:
                direction = 0
                details["summary"] = f"汽车年化销量 {actual_val:.1f} 百万辆，正常区间"
            else:
                direction = -1
                details["summary"] = f"汽车年化销量 {actual_val:.1f} 百万辆，消费疲软"
        elif ind["id"] == "retail":
            if actual_val > 8:
                direction = 0
                details["summary"] = f"零售同比 {actual_val:.1f}%，消费过热"
            elif actual_val >= 2:
                direction = 1
                details["summary"] = f"零售同比 {actual_val:.1f}%，消费健康"
            else:
                direction = -1
                details["summary"] = f"零售同比 {actual_val:.1f}%，消费萎缩"
        elif ind["id"] == "housing_supply":
            # PERMIT raw = thousands of units; 160万套 = 1600 thousand
            permit_wan = actual_val / 10  # convert to 万套
            if actual_val > 1600:
                direction = 1
                details["summary"] = f"建房许可 {permit_wan:.1f} 万套，供给扩张"
            elif actual_val >= 1200:
                direction = 0
                details["summary"] = f"建房许可 {permit_wan:.1f} 万套，正常区间"
            else:
                direction = -1
                details["summary"] = f"建房许可 {permit_wan:.1f} 万套，供给收缩"
        elif ind["id"] == "manufacturing":
            # DGORDER = durable goods orders in millions USD
            # 无法简单用绝对值判断，默认中性，等待 PMI 数据补充
            direction = 0
            details["summary"] = f"耐用品订单 {actual_val:.0f} 百万美元，ISM PMI 数据需从 ismworld.org 获取"
        elif ind["id"] == "wei":
            if actual_val > 3:
                direction = 1
                details["summary"] = f"WEI {actual_val:.2f}，经济增长强劲"
            elif actual_val >= 0:
                direction = 0
                details["summary"] = f"WEI {actual_val:.2f}，经济温和增长"
            else:
                direction = -1
                details["summary"] = f"WEI {actual_val:.2f}，经济可能步入衰退"
        elif ind["id"] == "copper_gold":
            if actual_val > 0.0020:
                direction = 1
                details["summary"] = f"铜金比 {actual_val:.4f}，风险偏好，经济扩张"
            elif actual_val >= 0.0012:
                direction = 0
                details["summary"] = f"铜金比 {actual_val:.4f}，正常区间"
            else:
                direction = -1
                details["summary"] = f"铜金比 {actual_val:.4f}，避险模式，经济放缓信号"
        else:
            # 通用 higher_is_better 逻辑
            if actual_val is None:
                pass
            else:
                direction = 1  # 默认有数据就中性偏多
                details["summary"] = f"当前值 {actual_val}"

    elif eval_type == "higher_is_worse":
        if actual_val is None:
            direction = 0
            details["summary"] = "数据暂不可用，无法判断"
        elif ind["id"] == "employment":
            if actual_val > 300000:
                direction = -1
                details["summary"] = f"初请失业金 {actual_val/10000:.1f} 万，劳动力市场恶化"
            elif actual_val >= 200000:
                direction = 0
                details["summary"] = f"初请失业金 {actual_val/10000:.1f} 万，正常水平"
            else:
                direction = 1
                details["summary"] = f"初请失业金 {actual_val/10000:.1f} 万，劳动力市场强劲"
        elif ind["id"] == "credit_spread":
            if actual_val > 10:
                direction = 1  # 极度恐慌 = 反向买入信号
                details["summary"] = f"信用利差 {actual_val:.2f}%，极度恐慌，反向看多信号"
            elif actual_val >= 4:
                direction = 0
                details["summary"] = f"信用利差 {actual_val:.2f}%，正常偏紧"
            else:
                direction = 1
                details["summary"] = f"信用利差 {actual_val:.2f}%，信贷环境宽松"
        else:
            if actual_val is not None:
                direction = -1
                details["summary"] = f"当前值 {actual_val}"

    elif eval_type == "inverse_extreme":
        if actual_val is None:
            direction = 0
            details["summary"] = "数据暂不可用，无法判断"
        elif ind["id"] == "aaii_sentiment":
            if actual_val > 25:
                direction = -1  # 极度乐观 → 见顶，利空
                details["summary"] = f"看涨-看跌差值 {actual_val:.1f}%，散户极度乐观，见顶预警"
            elif actual_val < -20:
                direction = 1  # 极度悲观 → 见底，利好
                details["summary"] = f"看涨-看跌差值 {actual_val:.1f}%，散户极度悲观，抄底信号"
            else:
                direction = 0
                details["summary"] = f"看涨-看跌差值 {actual_val:.1f}%，正常区间"
        elif ind["id"] == "market_breadth":
            if actual_val > 85:
                direction = -1  # 极度狂热 → 见顶
                details["summary"] = f"SMA50 以上占比 {actual_val:.0f}%，极度狂热，见顶预警"
            elif actual_val < 15:
                direction = 1  # 极度恐慌 → 见底
                details["summary"] = f"SMA50 以上占比 {actual_val:.0f}%，极度恐慌，抄底信号"
            else:
                direction = 0
                details["summary"] = f"SMA50 以上占比 {actual_val:.0f}%，正常区间"
        else:
            direction = 0
            details["summary"] = "数据暂不可用"

    elif eval_type == "rate_special":
        spread_val = _safe_float(fred_data.get("T10Y2Y"))
        fed_rate = _safe_float(fred_data.get("DFEDTARU"))
        if spread_val is not None:
            details["_raw_eval"] = spread_val
            if spread_val < 0:
                direction = -1
                details["summary"] = f"10Y-2Y 利差 {spread_val:.2f}%，利率倒挂，衰退预警"
            elif spread_val < 0.5:
                direction = 0
                details["summary"] = f"10Y-2Y 利差 {spread_val:.2f}%，曲线平坦，中性偏谨慎"
            else:
                direction = 1
                details["summary"] = f"10Y-2Y 利差 {spread_val:.2f}%，曲线正常，经济预期健康"

    elif eval_type == "sector_special":
        rotation = market_data.get("sector_rotation")
        sector_details = market_data.get("sector_details", [])
        if rotation == "risk_on":
            direction = 1
            details["summary"] = "科技/周期板块领涨，Risk On，市场风险偏好上升"
        elif rotation == "risk_off":
            direction = -1
            details["summary"] = "防御板块走强，Risk Off，资金在避险"
        else:
            direction = 0
            details["summary"] = "行业轮动方向不明确"
        details["_sector_details"] = sector_details[:5]  # Top 5

    elif eval_type == "neutral_range":
        if actual_val is None:
            direction = 0
            details["summary"] = "数据暂不可用，无法判断"
        elif ind["id"] == "oil_gold":
            if actual_val > 0.025:
                direction = -1  # 通胀压力 → 对成长股利空
                details["summary"] = f"油金比 {actual_val:.5f}，通胀压力上升，对成长股利空"
            elif actual_val >= 0.015:
                direction = 0
                details["summary"] = f"油金比 {actual_val:.5f}，正常区间"
            else:
                direction = 1  # 通缩 → 降息空间
                details["summary"] = f"油金比 {actual_val:.5f}，通胀压力低，降息空间充裕"
        else:
            direction = 0
            details["summary"] = f"当前值 {actual_val}"

    # 统一映射方向和展示
    if direction > 0:
        details["direction"] = 1
        details["direction_text"] = "利好"
        details["dir_class"] = "bullish"
    elif direction < 0:
        details["direction"] = -1
        details["direction_text"] = "利空"
        details["dir_class"] = "bearish"
    else:
        details["direction"] = 0
        details["direction_text"] = "中性"
        details["dir_class"] = "neutral"

    return direction, details


def evaluate_all() -> dict[str, Any]:
    """拉取全部数据并评估所有指标，返回汇总结果."""
    fred_data = fetch_fred_data()
    market_data = fetch_yfinance_data()

    category_signals: dict[str, dict] = {
        "consumption": {"total": 0, "count": 0, "score": 0},
        "supply": {"total": 0, "count": 0, "score": 0},
        "interest": {"total": 0, "count": 0, "score": 0},
        "sentiment": {"total": 0, "count": 0, "score": 0},
    }

    indicator_results = []
    total_score_raw = 0
    total_count = 0

    for ind in INDICATORS:
        direction, details = evaluate_single_indicator(ind, fred_data, market_data)
        indicator_results.append(details)
        cat = ind["category"]
        if details["_raw_eval"] is not None or details["summary"] != "数据暂不可用，无法判断":
            category_signals[cat]["total"] += direction
            category_signals[cat]["count"] += 1
            total_score_raw += direction
            total_count += 1

    # 计算分类得分率
    for cat_id, cat_data in category_signals.items():
        if cat_data["count"] > 0:
            cat_data["score"] = round((cat_data["total"] + cat_data["count"]) / (2 * cat_data["count"]) * 100)
        else:
            cat_data["score"] = 50  # 默认中性

    # 综合得分
    if total_count > 0:
        overall_score = round((total_score_raw + total_count) / (2 * total_count) * 100)
    else:
        overall_score = 50

    # 映射到 A/B/C/D
    if overall_score >= 80:
        overall_signal = "A"
        overall_text = "强烈看多"
    elif overall_score >= 60:
        overall_signal = "B"
        overall_text = "偏多"
    elif overall_score >= 40:
        overall_signal = "C"
        overall_text = "偏谨慎"
    else:
        overall_signal = "D"
        overall_text = "危险"

    # 生成一句话总结
    summary_parts = []
    for cat_id in ("consumption", "supply", "interest", "sentiment"):
        cat_name = {"consumption": "消费端", "supply": "供给端", "interest": "利率端", "sentiment": "情绪端"}
        cs = category_signals[cat_id]["score"]
        if cs >= 80:
            tag = "强劲"
        elif cs >= 60:
            tag = "健康"
        elif cs >= 40:
            tag = "偏弱"
        else:
            tag = "恶化"
        if category_signals[cat_id]["count"] > 0:
            summary_parts.append(f"{cat_name[cat_id]}{tag}")

    overall_summary = "，".join(summary_parts) + f"。综合信号：{overall_signal} 级（{overall_text}，{overall_score} 分）"

    # 对每个分类也计算信号等级
    def _cat_signal(score):
        if score >= 80: return "A"
        elif score >= 60: return "B"
        elif score >= 40: return "C"
        return "D"

    return {
        "overall_signal": overall_signal,
        "overall_score": overall_score,
        "overall_text": overall_text,
        "overall_summary": overall_summary,
        "category_signals": {
            cat_id: {
                **cat_data,
                "signal": _cat_signal(cat_data["score"]),
            }
            for cat_id, cat_data in category_signals.items()
        },
        "indicators": indicator_results,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "fred_available": bool(fred_data),
        "market_data_available": bool(market_data),
    }


# ============================================================
# HTML 渲染
# ============================================================

CSS = """
:root {
  --bg: #0d1117;
  --panel: #161b22;
  --ink: #c9d1d9;
  --muted: #8b949e;
  --line: #30363d;
  --accent: #58a6ff;
  --good: #3fb950;
  --warn: #d2991d;
  --bad: #f85149;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg); color: var(--ink); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; line-height: 1.6; }
.wrap { max-width: 1200px; margin: 0 auto; padding: 32px 20px 48px; }
h1 { margin: 0 0 4px; font-size: 36px; color: #f0f6fc; }
.subtitle { color: var(--muted); margin-bottom: 28px; font-size: 14px; }

/* 总信号面板 */
.signal-hero {
  background: var(--panel); border: 2px solid var(--line); border-radius: 16px;
  padding: 28px 32px; margin-bottom: 28px;
  display: flex; align-items: center; gap: 28px; flex-wrap: wrap;
}
.signal-badge {
  width: 90px; height: 90px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 44px; font-weight: 900; flex-shrink: 0;
}
.signal-badge.signal-A { background: var(--good); color: #0d1117; }
.signal-badge.signal-B { background: var(--accent); color: #0d1117; }
.signal-badge.signal-C { background: var(--warn); color: #0d1117; }
.signal-badge.signal-D { background: var(--bad); color: #fff; }
.signal-hero-info { flex: 1; min-width: 200px; }
.signal-hero-info h2 { font-size: 24px; color: #f0f6fc; margin-bottom: 4px; }
.signal-hero-info .score { font-size: 18px; color: var(--muted); margin-bottom: 8px; }
.signal-hero-info .summary { font-size: 15px; color: var(--ink); line-height: 1.5; }
.signal-hero-cats { display: flex; gap: 12px; flex-wrap: wrap; }
.cat-mini {
  background: var(--bg); border: 1px solid var(--line); border-radius: 10px;
  padding: 10px 14px; text-align: center; min-width: 75px;
}
.cat-mini .cat-icon { font-size: 11px; color: var(--muted); margin-bottom: 2px; }
.cat-mini .cat-badge {
  display: inline-block; width: 28px; height: 28px; border-radius: 50%;
  line-height: 28px; font-weight: 900; font-size: 14px;
}
.cat-mini .cat-score { font-size: 11px; color: var(--muted); margin-top: 2px; }

/* 分类区块 */
.category-section { margin-bottom: 24px; }
.category-header {
  display: flex; align-items: center; gap: 12px; margin-bottom: 14px;
  cursor: pointer; user-select: none;
}
.category-header h2 { font-size: 20px; color: #f0f6fc; }
.category-header .cat-desc { font-size: 13px; color: var(--muted); }
.category-header .toggle-icon { color: var(--muted); font-size: 14px; transition: transform 0.2s; }
.category-header .toggle-icon.open { transform: rotate(90deg); }
.category-header .cat-signal-mini {
  width: 32px; height: 32px; border-radius: 50%;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 14px; font-weight: 900;
}

/* 指标卡片 */
.indicators-grid { display: grid; gap: 16px; }
.indicators-grid.collapsed { display: none; }
.indicator-card {
  background: var(--panel); border: 1px solid var(--line); border-radius: 12px;
  padding: 20px 24px; transition: border-color 0.2s;
}
.indicator-card:hover { border-color: var(--accent); }
.indicator-card .ind-header {
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: 12px; margin-bottom: 8px;
}
.ind-header .ind-name { font-size: 17px; color: #f0f6fc; font-weight: 600; }
.ind-header .ind-sub { font-size: 13px; color: var(--muted); margin-top: 2px; }
.ind-header .ind-dir {
  font-size: 13px; font-weight: 700; padding: 3px 10px; border-radius: 999px;
  white-space: nowrap; flex-shrink: 0;
}
.ind-dir.bullish { background: rgba(63,185,80,0.15); color: var(--good); }
.ind-dir.bearish { background: rgba(248,81,73,0.15); color: var(--bad); }
.ind-dir.neutral { background: rgba(139,148,158,0.15); color: var(--muted); }

.ind-values { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 8px; }
.ind-value-item {
  background: var(--bg); border: 1px solid var(--line); border-radius: 8px;
  padding: 8px 12px;
}
.ind-value-item .val-label { font-size: 11px; color: var(--muted); }
.ind-value-item .val-num { font-size: 18px; font-weight: 700; color: var(--accent); }
.ind-value-item .val-unit { font-size: 12px; color: var(--muted); }

.ind-summary { font-size: 14px; color: var(--ink); margin-bottom: 8px; }
.ind-summary .bullet-bullish { color: var(--good); }
.ind-summary .bullet-bearish { color: var(--bad); }

.ind-detail-toggle {
  font-size: 12px; color: var(--accent); cursor: pointer; background: none; border: none;
  padding: 0; margin-top: 4px;
}
.ind-detail { display: none; margin-top: 10px; padding-top: 12px; border-top: 1px solid var(--line); }
.ind-detail.open { display: block; }
.ind-detail .detail-row { display: flex; gap: 8px; margin-bottom: 6px; font-size: 13px; }
.detail-label { color: var(--accent); min-width: 70px; flex-shrink: 0; font-weight: 600; }
.detail-label.warn { color: var(--warn); }
.detail-label.good { color: var(--good); }
.detail-label.bad { color: var(--bad); }

/* 行业轮动表 */
.sector-table { width: 100%; font-size: 13px; border-collapse: collapse; margin-top: 8px; }
.sector-table th, .sector-table td { padding: 4px 8px; border-bottom: 1px solid var(--line); text-align: left; }
.sector-table th { color: var(--muted); font-size: 11px; }
.sector-table .rs-positive { color: var(--good); }
.sector-table .rs-negative { color: var(--bad); }

/* 免责 */
.disclaimer { font-size: 12px; color: var(--muted); margin-top: 32px; padding: 16px; border-top: 1px solid var(--line); }

/* 响应式 */
@media (max-width: 768px) {
  .wrap { padding: 16px; }
  .signal-hero { flex-direction: column; align-items: center; text-align: center; }
  .signal-hero-cats { justify-content: center; }
  .ind-values { gap: 8px; }
}
"""


def render_us_page(evaluation: dict | None = None) -> str:
    """渲染完整的美国经济指标页面 HTML."""
    if evaluation is None:
        evaluation = evaluate_all()

    generated_at = evaluation["generated_at"]

    # 总信号
    ov = evaluation["overall_signal"]
    ov_score = evaluation["overall_score"]
    ov_text = evaluation["overall_text"]
    ov_summary = evaluation["overall_summary"]

    # 分类信号
    cat_signals = evaluation["category_signals"]
    cat_pills = ""
    for cat in CATEGORIES:
        cs = cat_signals.get(cat["id"], {"score": 50, "signal": "C"})
        cat_pills += f"""<div class="cat-mini">
          <div class="cat-icon">{cat['icon']}</div>
          <div class="cat-badge signal-{cs['signal']}">{cs['signal']}</div>
          <div class="cat-score">{cs['score']}分</div>
        </div>"""

    signal_hero = f"""<div class="signal-hero">
      <div class="signal-badge signal-{ov}">{ov}</div>
      <div class="signal-hero-info">
        <h2>美股综合信号 — {ov_text}</h2>
        <div class="score">综合得分 {ov_score} / 100 · 评估时间 {generated_at}</div>
        <div class="summary">{escape(ov_summary)}</div>
      </div>
      <div class="signal-hero-cats">{cat_pills}</div>
    </div>"""

    # 各分类区块
    category_sections = ""
    for cat in CATEGORIES:
        cat_id = cat["id"]
        cat_indicators = [ind for ind in evaluation["indicators"] if ind["indicator_id"] in [i["id"] for i in INDICATORS if i["category"] == cat_id]]

        cs = cat_signals.get(cat_id, {"score": 50, "signal": "C"})
        cat_signal_html = f'<span class="cat-signal-mini signal-{cs["signal"]}">{cs["signal"]}</span>'

        cards_html = ""
        for ind_detail in cat_indicators:
            # 找到原始指标定义
            ind_def = next((i for i in INDICATORS if i["id"] == ind_detail["indicator_id"]), None)
            if ind_def is None:
                continue

            # 数值展示
            values_html = ""
            for v in ind_detail.get("current_values", []):
                if v.get("value") is not None:
                    values_html += f"""<div class="ind-value-item">
              <div class="val-label">{escape(v['name'])}</div>
              <div class="val-num">{v['value']}{'' if v.get('is_pct') else ''} <span class="val-unit">{v.get('unit', '')}</span></div>
            </div>"""
                else:
                    values_html += f"""<div class="ind-value-item">
              <div class="val-label">{escape(v['name'])}</div>
              <div class="val-num" style="color:var(--muted)">N/A</div>
            </div>"""

            if not values_html:
                values_html = '<div class="ind-value-item"><div class="val-label">数据</div><div class="val-num" style="color:var(--muted)">暂不可用</div></div>'

            # 方向标签
            dir_class = ind_detail.get("dir_class", "neutral")
            dir_text = ind_detail.get("direction_text", "中性")
            summary = ind_detail.get("summary", "")

            # 行业轮动特殊渲染
            extra_html = ""
            sector_details = ind_detail.get("_sector_details", [])
            if sector_details:
                rows = ""
                for sd in sector_details:
                    rs_class = "rs-positive" if sd["rs"] > 0 else "rs-negative"
                    rows += f"""<tr>
              <td>{escape(sd['ticker'])}</td>
              <td>{escape(sd['name'])}</td>
              <td>{sd['return']}%</td>
              <td class="{rs_class}">{sd['rs']:+.1f}%</td>
            </tr>"""
                extra_html = f"""<div class="ind-detail open">
              <table class="sector-table">
                <thead><tr><th>ETF</th><th>板块</th><th>月收益</th><th>相对SPY</th></tr></thead>
                <tbody>{rows}</tbody>
              </table>
            </div>"""

            # 阈值解释（可展开）
            detail_html = f"""<div class="ind-detail" id="detail-{ind_detail['indicator_id']}">
              <div class="detail-row"><span class="detail-label">数据源</span><span>{ind_def.get('data_source', '').upper()}</span></div>
              <div class="detail-row"><span class="detail-label">视频位置</span><span>{ind_def.get('timestamp', '')}</span></div>
              <div class="detail-row"><span class="detail-label">指导意义</span><span>{escape(ind_def.get('guidance', ''))}</span></div>
              <div class="detail-row"><span class="detail-label warn">偏高阈值</span><span>{escape(ind_def.get('threshold_high', ''))}</span></div>
              <div class="detail-row"><span class="detail-label good">偏低阈值</span><span>{escape(ind_def.get('threshold_low', ''))}</span></div>
              <div class="detail-row"><span class="detail-label bad">偏高含义</span><span>{escape(ind_def.get('meaning_high', ''))}</span></div>
              <div class="detail-row"><span class="detail-label good">偏低含义</span><span>{escape(ind_def.get('meaning_low', ''))}</span></div>
            </div>
            <button class="ind-detail-toggle" onclick="toggleDetail('detail-{ind_detail['indicator_id']}', this)">展开详情 ▸</button>"""

            cards_html += f"""<div class="indicator-card">
            <div class="ind-header">
              <div>
                <div class="ind-name">{escape(ind_detail['title'])}</div>
                <div class="ind-sub">{escape(ind_def.get('subtitle', ''))} · {ind_def.get('timestamp', '')}</div>
              </div>
              <div class="ind-dir {dir_class}">{dir_text}</div>
            </div>
            <div class="ind-values">{values_html}</div>
            <div class="ind-summary">{escape(summary)}</div>
            {detail_html if not sector_details else extra_html}
          </div>"""

        category_sections += f"""<div class="category-section">
        <div class="category-header" onclick="toggleCategory('cat-{cat_id}', this.querySelector('.toggle-icon'))">
          {cat_signal_html}
          <h2>{cat['name']}</h2>
          <span class="cat-desc">{cat['desc']} — 得分 {cs['score']}（{cs['signal']}级）</span>
          <span class="toggle-icon">▸</span>
        </div>
        <div class="indicators-grid" id="cat-{cat_id}">{cards_html}</div>
      </div>"""

    # 免责
    fred_ok = "正常" if evaluation["fred_available"] else "不可用（需设置 FRED_API_KEY 环境变量）"
    market_ok = "正常" if evaluation["market_data_available"] else "部分不可用"
    disclaimer = f"""<div class="disclaimer">
      <p><strong>免责声明</strong>：本页面仅用于研究分析参考，不构成任何投资建议。指标信号基于当前公开数据和预设阈值自动计算，可能存在滞后或偏差。投资决策请您自行判断。</p>
      <p style="margin-top:8px;">数据源状态 — FRED: {fred_ok} | 市场数据: {market_ok} | 报告生成时间: {generated_at}</p>
      <p style="margin-top:4px;">数据来源：FRED (Federal Reserve Economic Data) + Yahoo Finance。视频参考：YouTube《投资美股最核心的20张图表》by LEI。</p>
    </div>"""

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>美股宏观经济指标 — StockScope</title>
  <style>{CSS}</style>
</head>
<body>
  <div class="wrap">
    <h1>美股宏观经济指标</h1>
    <p class="subtitle">基于《投资美股最核心的20张图表》整理 · 18 项核心指标 · 四大分类 · 实时数据 · 综合信号评分</p>
    {signal_hero}
    {category_sections}
    {disclaimer}
  </div>
  <script>
    function toggleDetail(id, btn) {{
      const el = document.getElementById(id);
      if (el.classList.contains('open')) {{
        el.classList.remove('open');
        btn.textContent = '展开详情 ▸';
      }} else {{
        el.classList.add('open');
        btn.textContent = '收起详情 ▾';
      }}
    }}
    function toggleCategory(id, icon) {{
      const el = document.getElementById(id);
      if (el.classList.contains('collapsed')) {{
        el.classList.remove('collapsed');
        icon.classList.remove('open');
      }} else {{
        el.classList.add('collapsed');
        icon.classList.add('open');
      }}
    }}
  </script>
</body>
</html>"""
    return html


def get_us_indicators_page() -> str:
    """获取美国经济指标页面的 HTML 字符串（供 server.py 路由调用）."""
    try:
        evaluation = evaluate_all()
    except Exception:
        evaluation = None
    return render_us_page(evaluation)
