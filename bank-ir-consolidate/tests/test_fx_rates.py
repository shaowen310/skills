"""Tests for fx_rates.py — mocked provider, cache behavior, fallback, backoff."""
from __future__ import annotations

import email.message
import json
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, override
from unittest import mock

# Make the scripts package importable when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from fx_rates import (  # noqa: E402  # pyright: ignore[reportMissingImports]
    FrankfurterProvider,
    collect_currencies,
    get_fx_rates,
)
from render_model import DEFAULT_FX_RATES  # noqa: E402  # pyright: ignore[reportMissingImports]


def _fake_response(payload: dict[str, Any]) -> mock.MagicMock:
    resp = mock.MagicMock()
    resp.read.return_value = json.dumps(payload).encode("utf-8")
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    return resp


class _FakeStmt:
    """Minimal stand-in for a ParsedStatement with account currencies."""

    accounts: list[Any]

    def __init__(self, currencies: list[str]) -> None:
        self.accounts = [type("A", (), {"currency": c})() for c in currencies]


class FXRatesTest(unittest.TestCase):
    tmp: tempfile.TemporaryDirectory[str]
    cache_dir: str

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.tmp = tempfile.TemporaryDirectory()
        self.cache_dir = self.tmp.name

    @override
    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_frankfurter_inverts_to_sgd_per_unit(self) -> None:
        prov = FrankfurterProvider()
        payload = {"base": "SGD", "date": "2026-07-17",
                   "rates": {"USD": 0.7745, "JPY": 125.82, "CNY": 5.2473}}
        with mock.patch.object(urllib.request, "urlopen",
                                return_value=_fake_response(payload)):
            rates = prov.fetch("2026-07-17", ["USD", "JPY", "CNY"])
        self.assertAlmostEqual(rates["USD"], 1 / 0.7745, places=6)
        self.assertAlmostEqual(rates["JPY"], 1 / 125.82, places=8)
        self.assertAlmostEqual(rates["CNY"], 1 / 5.2473, places=6)

    def test_live_then_cache_hit(self) -> None:
        payload = {"base": "SGD", "date": "2026-07-17",
                   "rates": {"USD": 0.7745, "JPY": 125.82, "CNY": 5.2473}}
        with mock.patch.object(urllib.request, "urlopen",
                                return_value=_fake_response(payload)) as m:
            r1 = get_fx_rates(as_of="2026-07-17", cache_dir=self.cache_dir,
                              symbols=["USD", "JPY", "CNY"])
            self.assertEqual(r1.source, "live")
            self.assertEqual(m.call_count, 1)
            # Second call with same date/symbols must hit the cache, not the network.
            r2 = get_fx_rates(as_of="2026-07-17", cache_dir=self.cache_dir,
                              symbols=["USD", "JPY", "CNY"])
            self.assertEqual(r2.source, "cached")
            self.assertEqual(m.call_count, 1)

    def test_offline_without_cache_falls_back(self) -> None:
        r = get_fx_rates(as_of="2026-07-17", cache_dir=self.cache_dir,
                         symbols=["USD", "JPY", "CNY"], offline=True)
        self.assertEqual(r.source, "fallback")
        self.assertEqual(r.rates["USD"], DEFAULT_FX_RATES["USD"])
        self.assertIn("USD", r.rates)

    def test_offline_uses_cache(self) -> None:
        payload = {"base": "SGD", "date": "2026-07-17",
                   "rates": {"USD": 0.7745, "JPY": 125.82, "CNY": 5.2473}}
        with mock.patch.object(urllib.request, "urlopen",
                                return_value=_fake_response(payload)):
            _ = get_fx_rates(as_of="2026-07-17", cache_dir=self.cache_dir,
                             symbols=["USD", "JPY", "CNY"])
        # Now offline; must reuse the written cache rather than fall back.
        with mock.patch.object(urllib.request, "urlopen",
                               side_effect=AssertionError("should not fetch offline")):
            r = get_fx_rates(as_of="2026-07-17", cache_dir=self.cache_dir,
                             symbols=["USD", "JPY", "CNY"], offline=True)
        self.assertEqual(r.source, "cached")
        self.assertAlmostEqual(r.rates["USD"], 1 / 0.7745, places=6)

    def test_trading_day_backoff(self) -> None:
        payload = {"base": "SGD", "date": "2026-07-17",
                   "rates": {"USD": 0.7745, "JPY": 125.82, "CNY": 5.2473}}

        def _side_effect(url: Any, *_args: Any, **_kwargs: Any) -> Any:
            if "2026-07-18" in url.full_url:
                hdrs = email.message.Message()
                raise urllib.error.HTTPError(url, 404, "nf", hdrs, None)
            return _fake_response(payload)

        with mock.patch.object(urllib.request, "urlopen",
                               side_effect=_side_effect):
            r = get_fx_rates(as_of="2026-07-18", cache_dir=self.cache_dir,
                             symbols=["USD", "JPY", "CNY"])
        self.assertEqual(r.source, "live")
        self.assertEqual(r.as_of, "2026-07-17")  # stepped back from Sat to Fri

    def test_collect_currencies(self) -> None:
        stmt = _FakeStmt(["SGD", "USD", "JPY", "USD", "EUR"])
        self.assertEqual(collect_currencies(stmt), ["EUR", "JPY", "USD"])

    def test_no_foreign_currencies(self) -> None:
        r = get_fx_rates(as_of="2026-07-17", cache_dir=self.cache_dir, symbols=[])
        self.assertEqual(r.rates, {"SGD": 1.0})
        self.assertIn(r.source, {"none", "cached", "fallback"})

    def test_network_failure_falls_back(self) -> None:
        with mock.patch.object(urllib.request, "urlopen",
                               side_effect=urllib.error.URLError("boom")):
            r = get_fx_rates(as_of="2026-07-17", cache_dir=self.cache_dir,
                             symbols=["USD", "JPY", "CNY"])
        self.assertIn(r.source, {"fallback", "cached"})
        self.assertEqual(r.rates["USD"], DEFAULT_FX_RATES["USD"])


if __name__ == "__main__":
    _ = unittest.main(verbosity=2)
