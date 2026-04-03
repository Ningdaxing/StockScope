from __future__ import annotations

from pathlib import Path
import tomllib


def load_raw_config(path: str | Path) -> dict:
    """读取并返回原始 TOML 配置。

    作用：
    - 统一处理配置文件读取
    - 给观察池、名称覆盖等不同读取逻辑复用
    """
    return tomllib.loads(Path(path).read_text())


def load_watchlist(path: str | Path) -> list[str]:
    """读取观察池配置并返回去重后的 ticker 列表。

    作用：
    - 从 TOML 文件中收集分组里的标的
    - 合并手动补充的标的
    - 统一转成大写并做去重
    """
    raw = load_raw_config(path)
    symbols: list[str] = []
    groups = raw.get("groups", {})
    for values in groups.values():
        symbols.extend(values)
    symbols.extend(raw.get("tickers", {}).get("manual", []))
    deduped: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        normalized = symbol.strip().upper()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def load_name_overrides(path: str | Path) -> dict[str, str]:
    """读取 ticker 到名称覆盖值的映射表。

    作用：
    - 从配置文件里加载少量人工名称覆盖
    - 兼容旧版 `aliases` 字段，避免升级时直接报错
    """
    raw = load_raw_config(path)
    overrides = raw.get("name_overrides", {}) or raw.get("aliases", {})
    normalized: dict[str, str] = {}
    for symbol, name in overrides.items():
        key = str(symbol).strip().upper()
        value = str(name).strip()
        if key and value:
            normalized[key] = value
    return normalized
