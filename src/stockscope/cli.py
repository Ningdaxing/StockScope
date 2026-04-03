from __future__ import annotations

import argparse
import sys
from pathlib import Path

from stockscope.config import load_name_overrides, load_watchlist
from stockscope.fetchers.yahoo import YahooClient, is_network_error
from stockscope.name_resolver import NameResolver
from stockscope.reports import print_terminal_summary, write_csv, write_dashboard
from stockscope.scoring import score_ticker


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。

    作用：
    - 定义当前支持的命令
    - 定义运行时可传入的配置、输出目录和展示条数
    """
    parser = argparse.ArgumentParser(description="StockScope signal screener")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Fetch data, score watchlist, and generate reports")
    run_parser.add_argument("--config", default="config/watchlist.toml", help="Watchlist TOML path")
    run_parser.add_argument("--output-dir", default="outputs/latest", help="Report output directory")
    run_parser.add_argument("--limit", type=int, default=15, help="Rows to print in terminal")
    return parser


def run_command(config_path: str, output_dir: str, limit: int) -> int:
    """执行一次完整的分析流程。

    作用：
    - 读取观察池配置
    - 拉取每个标的的价格和基础面数据
    - 调用打分逻辑生成结果
    - 输出 CSV、HTML 和终端摘要
    """
    symbols = load_watchlist(config_path)
    name_overrides = load_name_overrides(config_path)
    client = YahooClient()
    benchmark = "SPY"
    scored_items = []
    skipped: list[str] = []
    outdir = Path(output_dir)
    resolver = NameResolver(outdir.parent / "cache" / "name_cache.json", overrides=name_overrides)
    try:
        benchmark_chart = client.fetch_chart(benchmark)
        for symbol in symbols:
            try:
                fundamentals = client.fetch_summary(symbol)
                chart = client.fetch_chart(symbol)
                scored = score_ticker(fundamentals, chart, benchmark_chart)
                scored.short_name = resolver.resolve(symbol, scored.short_name, scored.asset_type)
                scored_items.append(scored)
            except Exception as item_error:
                skipped.append(f"{symbol}: {item_error}")
    except Exception as error:
        if is_network_error(error):
            print(f"Network request failed: {error}", file=sys.stderr)
            return 2
        raise

    resolver.save()
    scored_items.sort(key=lambda item: (item.entry_score, item.valuation_score, item.trend_score), reverse=True)
    write_csv(scored_items, outdir / "signals.csv")
    write_dashboard(scored_items, outdir / "dashboard.html")
    print(print_terminal_summary(scored_items, limit=limit))
    print(f"\nWrote {len(scored_items)} rows to {outdir / 'signals.csv'}")
    print(f"Wrote dashboard to {outdir / 'dashboard.html'}")
    if skipped:
        print("\nSkipped symbols:")
        for item in skipped[:10]:
            print(f"- {item}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """作为程序总入口，解析参数并分发到具体命令。

    作用：
    - 接收命令行参数
    - 根据不同子命令调用对应执行函数
    - 返回适合命令行使用的退出码
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return run_command(args.config, args.output_dir, args.limit)
    parser.error(f"Unknown command: {args.command}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
