# -*- coding: utf-8 -*-
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "deepseek-harness-quant"))


class TestPortfolioPriceBackfill(unittest.TestCase):
    def test_latest_close_returns_price(self):
        """相对路径 as_uri 曾抛 ValueError → 永远 None；修后应返回真实收盘"""
        from strategy.portfolio import _latest_close_of
        v = _latest_close_of("000430.SZ")
        self.assertIsNotNone(v, "_latest_close_of 返回 None（as_uri 相对路径 bug 回归）")
        self.assertGreater(float(v), 0)

    def test_entry_price_fallback_when_date_missing(self):
        """审批日尚无 qfq（fill 设计滞后一天）→ 应回退到 date<= 的最近收盘"""
        from strategy.portfolio import _entry_price_of
        # 2026-11-10 是今天：qfq 无此日 → 修前 None，修后应回退到 11-09 收盘
        v = _entry_price_of("000430.SZ", "2026-11-10")
        self.assertIsNotNone(v, "entry_price 回退失败")
        self.assertGreater(float(v), 0)
        # 精确日仍应工作（历史日）
        v2 = _entry_price_of("000430.SZ", "2026-11-09")
        self.assertIsNotNone(v2)


if __name__ == "__main__":
    unittest.main()
