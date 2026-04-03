from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from stockscope.name_resolver import NameResolver


class NameResolverTests(unittest.TestCase):
    def test_override_has_highest_priority(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            resolver = NameResolver(Path(tmpdir) / "name_cache.json", overrides={"KO": "手工可口可乐"})
            resolved = resolver.resolve("KO", "The Coca-Cola Company", "STOCK")
            self.assertEqual(resolved, "手工可口可乐")

    def test_cache_hit_skips_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "name_cache.json"
            cache_path.write_text(
                json.dumps(
                    {
                        "names": {
                            "TSM": {
                                "name": "台积电",
                                "source": "eastmoney",
                                "updated_at": "2026-04-03T00:00:00+00:00",
                            }
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            resolver = NameResolver(cache_path)
            resolved = resolver.resolve("TSM", "Taiwan Semiconductor", "STOCK")
            self.assertEqual(resolved, "台积电")

    def test_translation_fallback_and_save(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "name_cache.json"

            class StubResolver(NameResolver):
                def _lookup_eastmoney_name(self, query: str) -> str | None:
                    return None

            resolver = StubResolver(cache_path)
            resolved = resolver.resolve("TEST", "Aerospace Defense ETF", "ETF")
            resolver.save()

            self.assertEqual(resolved, "航空航天 军工 ETF")
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["names"]["TEST"]["source"], "translated")


if __name__ == "__main__":
    unittest.main()
