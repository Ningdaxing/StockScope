from __future__ import annotations

import argparse
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
import sys
import webbrowser
from pathlib import Path
import time

from stockscope.config import (
    get_symbol_to_group_map,
    load_benchmark,
    load_name_overrides,
    load_scoring_config,
    load_watchlist,
)
from stockscope.fetchers.yahoo import YahooClient, is_network_error
from stockscope.models import ScoringConfig
from stockscope.name_resolver import NameResolver
from stockscope.reports import print_terminal_summary, write_csv, write_dashboard
from stockscope.scoring import score_ticker


MAX_FETCH_WORKERS = 6
SYMBOL_TIMEOUT_SECONDS = 15
POLL_INTERVAL_SECONDS = 0.2


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
    run_parser.add_argument("--open", action="store_true", help="Open dashboard in default browser after run")
    return parser


def run_command(config_path: str, output_dir: str, limit: int, open_browser: bool = False) -> int:
    """执行一次完整的分析流程。

    作用：
    - 读取观察池配置
    - 拉取每个标的的价格和基础面数据
    - 调用打分逻辑生成结果
    - 输出 CSV、HTML 和终端摘要
    """
    symbols = load_watchlist(config_path)
    name_overrides = load_name_overrides(config_path)
    symbol_to_group = get_symbol_to_group_map(config_path)
    scoring_config = load_scoring_config()
    client = YahooClient()
    benchmark = load_benchmark(config_path)
    scored_items = []
    skipped: list[str] = []
    outdir = Path(output_dir)
    resolver = NameResolver(outdir.parent / "cache" / "name_cache.json", overrides=name_overrides)
    try:
        benchmark_chart = client.fetch_chart(benchmark)
        worker_count = min(MAX_FETCH_WORKERS, max(1, len(symbols)))
        executor = ThreadPoolExecutor(max_workers=worker_count)
        future_to_symbol: dict[Future, str] = {}
        started_at: dict[Future, float] = {}
        try:
            for symbol in symbols:
                future = executor.submit(_fetch_and_score_symbol, symbol, benchmark_chart, scoring_config)
                future_to_symbol[future] = symbol
                started_at[future] = time.monotonic()

            pending = set(future_to_symbol)
            while pending:
                done, _ = wait(pending, timeout=POLL_INTERVAL_SECONDS, return_when=FIRST_COMPLETED)
                for future in done:
                    symbol = future_to_symbol[future]
                    try:
                        scored = future.result()
                        scored.short_name = resolver.resolve(symbol, scored.short_name, scored.asset_type)
                        scored_items.append(scored)
                    except Exception as item_error:
                        skipped.append(f"{symbol}: {item_error}")
                    pending.discard(future)

                now = time.monotonic()
                overdue = [future for future in pending if now - started_at[future] > SYMBOL_TIMEOUT_SECONDS]
                for future in overdue:
                    symbol = future_to_symbol[future]
                    skipped.append(f"{symbol}: 查询超时")
                    future.cancel()
                    pending.discard(future)
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
    except Exception as error:
        if is_network_error(error):
            print(f"Network request failed: {error}", file=sys.stderr)
            return 2
        raise

    resolver.save()
    scored_items.sort(key=lambda item: (item.entry_score, item.valuation_score, item.trend_score), reverse=True)
    for item in scored_items:
        item.group = symbol_to_group.get(item.symbol)
    write_csv(scored_items, outdir / "signals.csv")
    write_dashboard(scored_items, outdir / "dashboard.html", config_path=config_path)
    print(print_terminal_summary(scored_items, limit=limit))
    print(f"\nWrote {len(scored_items)} rows to {outdir / 'signals.csv'}")
    print(f"Wrote dashboard to {outdir / 'dashboard.html'}")
    if skipped:
        print("\nSkipped symbols:")
        for item in skipped[:10]:
            print(f"- {item}")
    if open_browser:
        dashboard_path = outdir / "dashboard.html"
        dashboard_url = dashboard_path.resolve().as_uri()
        print(f"Opening dashboard in browser...")
        webbrowser.open(dashboard_url)
    return 0


def _fetch_and_score_symbol(symbol: str, benchmark_chart, scoring_config) -> object:
    """抓取单个 ticker 数据并完成评分。

    作用：
    - 作为并发任务的最小执行单元
    - 把单个标的的抓数和评分封装在一起，便于超时和失败隔离
    """
    client = YahooClient()
    fundamentals = client.fetch_summary(symbol)
    chart = client.fetch_chart(symbol)
    return score_ticker(fundamentals, chart, benchmark_chart, config=scoring_config)


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
        return run_command(args.config, args.output_dir, args.limit, open_browser=args.open)
    parser.error(f"Unknown command: {args.command}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
