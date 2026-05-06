from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from stockscope.server import create_app


HTML_SAMPLE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="120">
  <title>StockScope</title>
</head>
<body><h1>Test Dashboard</h1></body>
</html>"""


class ServerRouteTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.html_path = Path(self.tmpdir.name) / "dashboard.html"
        self.html_path.write_text(HTML_SAMPLE, encoding="utf-8")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_index_returns_html_with_refresh_meta(self):
        app = create_app(output_dir=self.tmpdir.name)
        with _test_client(app) as client:
            resp = client.get("/")
            assert resp.status_code == 200
            html = resp.text
            assert "<!doctype html>" in html
            assert 'http-equiv="refresh"' in html
            assert "Test Dashboard" in html

    def test_index_returns_full_dashboard(self):
        app = create_app(output_dir=self.tmpdir.name)
        with _test_client(app) as client:
            resp = client.get("/")
            assert resp.headers["content-type"] == "text/html; charset=utf-8"
            assert len(resp.text) > 0


def _test_client(app):
    try:
        from fastapi.testclient import TestClient
    except ImportError:
        raise unittest.SkipTest("fastapi not installed")
    return TestClient(app)


class ServerStartupTests(unittest.TestCase):
    @patch("stockscope.cli.run_command")
    @patch("apscheduler.schedulers.background.BackgroundScheduler")
    def test_start_scheduler_adds_hourly_job(self, mock_scheduler_cls, mock_run):
        from stockscope.server import start_scheduler

        mock_scheduler = mock_scheduler_cls.return_value
        start_scheduler(
            config_path="config/fake.toml",
            output_dir="/tmp/fake",
            run_immediately=False,
        )
        mock_scheduler.add_job.assert_called_once()
        call_kwargs = mock_scheduler.add_job.call_args.kwargs
        assert call_kwargs["trigger"] == "interval"
        assert call_kwargs["hours"] == 1


if __name__ == "__main__":
    unittest.main()
