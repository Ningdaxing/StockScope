from __future__ import annotations

import threading
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse


def run_analysis(config_path: str, output_dir: str) -> None:
    from stockscope.cli import run_command

    print(f"[{_now()}] 开始拉取数据...")
    code = run_command(config_path=config_path, output_dir=output_dir, limit=0)
    if code == 0:
        print(f"[{_now()}] 分析完成")
    else:
        print(f"[{_now()}] 分析出错，退出码 {code}")


def _run_in_background(config_path: str, output_dir: str) -> None:
    t = threading.Thread(target=run_analysis, args=(config_path, output_dir), daemon=True)
    t.start()


def start_scheduler(
    *,
    config_path: str,
    output_dir: str,
    run_immediately: bool = True,
) -> None:
    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_analysis,
        trigger="interval",
        hours=1,
        kwargs={"config_path": config_path, "output_dir": output_dir},
        id="stockscope_hourly",
    )
    scheduler.start()
    print(f"[{_now()}] 定时任务已就绪（每 1 小时）")

    if run_immediately:
        _run_in_background(config_path, output_dir)


def create_app(*, output_dir: str) -> FastAPI:
    from stockscope.research_index import generate_index

    app = FastAPI(title="StockScope")

    html_path = Path(output_dir) / "dashboard.html"

    @app.get("/", response_class=HTMLResponse)
    def index():
        if html_path.exists():
            return html_path.read_text(encoding="utf-8")
        return (
            "<html><body><h1>StockScope</h1>"
            "<p>数据尚未生成，请稍后刷新页面。</p>"
            "</body></html>"
        )

    @app.get("/research", response_class=HTMLResponse)
    def research_center():
        index_path = generate_index(output_dir)
        return index_path.read_text(encoding="utf-8")

    @app.get("/research/{filename}", response_class=HTMLResponse)
    def research_report(filename: str):
        filepath = Path(output_dir) / filename
        if filepath.exists() and filepath.suffix == ".html":
            return filepath.read_text(encoding="utf-8")
        return HTMLResponse(content="<h1>404</h1>", status_code=404)

    @app.get("/us-indicators", response_class=HTMLResponse)
    def us_indicators():
        from stockscope.us_indicators import get_us_indicators_page

        return get_us_indicators_page()

    return app


def serve(*, host: str, port: int, config_path: str, output_dir: str) -> None:
    import uvicorn

    start_scheduler(config_path=config_path, output_dir=output_dir)
    print(f"[{_now()}] Web 服务启动 → http://{host}:{port}")
    uvicorn.run(create_app(output_dir=output_dir), host=host, port=port, log_level="warning")


def _now() -> str:
    import datetime

    return datetime.datetime.now().strftime("%H:%M:%S")
