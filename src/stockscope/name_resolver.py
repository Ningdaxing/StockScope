from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from urllib.parse import quote
from urllib.request import Request, urlopen


EASTMONEY_TOKEN = "D43BF722C8E33BDC906FB84D85E326E8"
USER_AGENT = "Mozilla/5.0"


class NameResolver:
    """把 ticker 解析成更适合展示的中文名称。

    作用：
    - 优先应用人工覆盖
    - 读取和写入本地缓存，避免重复查询
    - 调用中文财经源获取名称
    - 在查不到中文名时做翻译式回退
    """

    def __init__(self, cache_path: str | Path, overrides: dict[str, str] | None = None) -> None:
        """初始化名称解析器。

        作用：
        - 记录缓存文件路径
        - 加载已有缓存
        - 保存人工覆盖配置
        """
        self.cache_path = Path(cache_path)
        self.overrides = {key.upper(): value for key, value in (overrides or {}).items()}
        self.cache = self._load_cache()

    def resolve(self, symbol: str, english_name: str | None, asset_type: str) -> str:
        """解析单个标的的最终展示名称。

        作用：
        - 按人工覆盖、缓存、中文财经源、翻译回退的顺序解析名称
        - 保证即使查询失败，也会返回可展示的名称
        """
        normalized_symbol = symbol.strip().upper()
        fallback_name = (english_name or normalized_symbol).strip()

        if normalized_symbol in self.overrides:
            return self.overrides[normalized_symbol]

        cached = self.cache.get(normalized_symbol)
        if cached and cached.get("name"):
            if cached.get("source") == "translated":
                refreshed = self._translate_fallback(fallback_name, asset_type)
                if refreshed:
                    if refreshed != str(cached["name"]):
                        self._store_cache(normalized_symbol, refreshed, source="translated")
                    return refreshed
            return str(cached["name"])

        eastmoney_name = self._lookup_eastmoney_name(normalized_symbol)
        if eastmoney_name:
            self._store_cache(normalized_symbol, eastmoney_name, source="eastmoney")
            return eastmoney_name

        eastmoney_by_name = self._lookup_eastmoney_name(fallback_name)
        if eastmoney_by_name:
            self._store_cache(normalized_symbol, eastmoney_by_name, source="eastmoney_by_name")
            return eastmoney_by_name

        translated = self._translate_fallback(fallback_name, asset_type)
        if translated:
            self._store_cache(normalized_symbol, translated, source="translated")
            return translated

        return fallback_name

    def save(self) -> None:
        """把当前缓存写入磁盘。

        作用：
        - 持久化本次运行中解析到的中文名称
        - 让下次运行可以直接复用结果
        """
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"names": self.cache}
        self.cache_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _load_cache(self) -> dict[str, dict[str, str]]:
        """从磁盘加载名称缓存。

        作用：
        - 读取已有 ticker 到中文名映射
        - 在没有缓存文件时返回空映射
        """
        if not self.cache_path.exists():
            return {}
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        names = payload.get("names", {})
        return names if isinstance(names, dict) else {}

    def _store_cache(self, symbol: str, name: str, *, source: str) -> None:
        """把解析出的名称写入内存缓存。

        作用：
        - 统一记录名称来源和更新时间
        - 供本次运行和后续持久化复用
        """
        self.cache[symbol] = {
            "name": name,
            "source": source,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _lookup_eastmoney_name(self, query: str) -> str | None:
        """调用东方财富搜索接口查询中文名称。

        作用：
        - 优先从中文财经源拿到更符合用户习惯的名称
        - 同时支持按 ticker 和按英文名查询
        """
        normalized_query = query.strip()
        if not normalized_query:
            return None
        encoded_query = quote(normalized_query)
        url = (
            "https://searchapi.eastmoney.com/api/suggest/get"
            f"?input={encoded_query}&type=14&token={EASTMONEY_TOKEN}&count=10"
        )
        request = Request(url, headers={"User-Agent": USER_AGENT})
        try:
            payload = json.loads(urlopen(request, timeout=20).read().decode("utf-8"))
        except Exception:
            return None

        rows = payload.get("QuotationCodeTable", {}).get("Data", [])
        if not isinstance(rows, list):
            return None

        normalized_upper = normalized_query.upper()
        matched = None
        for row in rows:
            if not isinstance(row, dict):
                continue
            code = str(row.get("Code", "")).upper()
            unified = str(row.get("UnifiedCode", "")).upper()
            if normalized_upper in {code, unified}:
                matched = row
                break
        if matched is None and rows:
            first = rows[0]
            if isinstance(first, dict):
                matched = first
        if not matched:
            return None

        name = str(matched.get("Name", "")).strip()
        if not name:
            return None
        if self._contains_chinese(name):
            return self._normalize_finance_name(name)
        return None

    def _translate_fallback(self, english_name: str, asset_type: str) -> str | None:
        """在查不到中文名称时，用本地规则做翻译式回退。

        作用：
        - 尽量生成可读性更高的中文展示名
        - 避免完全依赖外部中文源
        """
        cleaned = self._clean_english_name(english_name)
        if not cleaned:
            return None
        if asset_type == "ETF":
            translated = self._translate_etf_name(cleaned)
        else:
            translated = self._translate_company_name(cleaned)
        normalized = self._normalize_finance_name(translated)
        return normalized or None

    def _translate_etf_name(self, name: str) -> str:
        """把 ETF 英文名称按规则转成中文表达。

        作用：
        - 优先保留指数、主题、资产类别这些关键信息
        - 生成比原始英文名更易读的展示名
        """
        text = f" {name} "
        replacements = [
            ("NASDAQ-100", "纳斯达克100"),
            ("NASDAQ 100", "纳斯达克100"),
            ("S&P 500", "标普500"),
            ("MSCI", "MSCI"),
            ("Semiconductor", "半导体"),
            ("Aerospace", "航空航天"),
            ("Defense", "军工"),
            ("Dividend", "股息"),
            ("High Yield", "高收益"),
            ("High Dividend", "高股息"),
            ("Growth", "成长"),
            ("Value", "价值"),
            ("Total Market", "全市场"),
            ("Treasury", "美债"),
            ("Bond", "债券"),
            ("Technology", "科技"),
            ("Energy", "能源"),
            ("Healthcare", "医疗保健"),
            ("Financial", "金融"),
            ("Consumer", "消费"),
            ("Korea", "韩国"),
            ("China", "中国"),
            ("Japan", "日本"),
            ("Europe", "欧洲"),
            ("ETF", "ETF"),
            ("Fund", "基金"),
            ("Index", "指数"),
            ("Trust", ""),
        ]
        for source, target in replacements:
            text = re.sub(rf"\b{re.escape(source)}\b", target, text, flags=re.IGNORECASE)
        text = re.sub(r"\b(iShares|Vanguard|Invesco|SPDR|ProShares|Roundhill)\b", r"-\1", text, flags=re.IGNORECASE)
        text = re.sub(r"\s+", " ", text).strip(" -")
        return text

    def _translate_company_name(self, name: str) -> str:
        """把个股英文名称按本地规则做简化翻译。

        作用：
        - 翻译常见行业和公司后缀词
        - 在没有现成中文名时，生成较易懂的混合名称
        """
        text = f" {name} "
        replacements = [
            ("Platforms", "平台"),
            ("Platform", "平台"),
            ("Technologies", "科技"),
            ("Technology", "科技"),
            ("Semiconductor", "半导体"),
            ("Energy", "能源"),
            ("Pharmaceuticals", "制药"),
            ("Pharmaceutical", "制药"),
            ("Therapeutics", "治疗"),
            ("Holdings", "控股"),
            ("Holding", "控股"),
            ("Industries", "工业"),
            ("Industry", "工业"),
            ("Financial", "金融"),
            ("Bank", "银行"),
            ("Bancorp", "银行控股"),
            ("Group", "集团"),
            ("Medical", "医疗"),
            ("Health", "健康"),
            ("Aerospace", "航空航天"),
            ("Defense", "军工"),
            ("Communications", "通信"),
            ("Communication", "通信"),
        ]
        for source, target in replacements:
            text = re.sub(rf"\b{re.escape(source)}\b", target, text, flags=re.IGNORECASE)
        text = re.sub(
            r"\b(Inc|Inc\.|Corp|Corp\.|Corporation|Company|Co|Co\.|Ltd|Ltd\.|PLC|S\.A\.|N\.V\.)\b",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(r"[.,]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip(" ,-")
        return text

    def _clean_english_name(self, name: str) -> str:
        """清理英文名称里的冗余后缀和杂项字符。

        作用：
        - 让翻译回退面对更干净的输入
        - 减少 `Inc-A`、括号说明等噪音
        """
        text = re.sub(r"\(.*?\)", "", name)
        text = re.sub(r"[\-–—_/]+[A-Z]$", "", text)
        text = text.replace("(The)", "").replace("The ", "")
        text = re.sub(r"[.,]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip(" ,-")
        return text

    def _normalize_finance_name(self, name: str) -> str:
        """规范化输出名称格式。

        作用：
        - 清理多余空格和重复分隔符
        - 让缓存和展示名称保持一致
        """
        text = re.sub(r"\s+", " ", name)
        text = re.sub(r"-{2,}", "-", text)
        return text.strip(" -")

    def _contains_chinese(self, text: str) -> bool:
        """判断文本是否包含中文字符。

        作用：
        - 区分中文财经源返回的中文名称和纯英文名称
        - 避免把英文结果误当作中文名称缓存
        """
        return any("\u4e00" <= char <= "\u9fff" for char in text)
