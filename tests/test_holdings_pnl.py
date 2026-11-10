# -*- coding: utf-8 -*-
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
UP = ROOT / "deepseek-harness-quant"
sys.path.insert(0, str(UP))


class TestPortfolioPnlQuotesShape(unittest.TestCase):
    def test_pnl_tolerates_list_quotes(self):
        """patch 层曾把 quotes 以 list 返回——portfolio_pnl 必须兼容不崩"""
        import deck.live_api as la

        fake_pf = {"positions": [{
            "code": "600519", "status": "holding",
            "entry_price": 100.0, "cost": 100.0, "entry_date": "2026-11-10",
        }]}
        fake_rt = {"ok": True, "market_open": True,
                   "quotes": [{"code": "600519", "price": 110.0, "pct": 1.0, "name": "X"}]}
        with mock.patch.object(la, "live_realtime", return_value=fake_rt), \
             mock.patch("strategy.portfolio._load", return_value=fake_pf), \
             mock.patch("strategy.portfolio._save"), \
             mock.patch("strategy.portfolio._entry_price_of", return_value=100.0), \
             mock.patch("strategy.portfolio._latest_close_of", return_value=109.0):
            out = la.portfolio_pnl()
        self.assertTrue(out.get("ok", True), out)
        rows = out.get("rows") or out.get("positions") or []
        self.assertTrue(rows, out)
        row = rows[0]
        # 盘中实时价优先：110/100-1 = 10%
        self.assertAlmostEqual(float(row["ret"]), 0.10, places=6)
        # 真实实现字段名为 price_src（live_api.portfolio_pnl）
        self.assertEqual(row.get("price_src"), "realtime")


if __name__ == "__main__":
    unittest.main()
