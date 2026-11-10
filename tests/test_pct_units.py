# -*- coding: utf-8 -*-
import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UP = ROOT / "deepseek-harness-quant"
sys.path.insert(0, str(UP))
BARS = UP / "data" / "cache" / "bars.db"


class TestPctChgUnit(unittest.TestCase):
    """pct_chg 契约 = 百分数（9.99=9.99%），与上游 _board_pct(9.5/19.5) 对齐"""

    @unittest.skipUnless(BARS.exists(), "bars.db 不存在")
    def test_known_limit_up_reaches_threshold(self):
        con = sqlite3.connect(f"file:{BARS}?mode=ro&immutable=1", uri=True)
        # 2026-11-09 真实涨停样本（修复前存 0.1726/0.2 等小数）
        row = con.execute(
            "SELECT pct_chg FROM daily_bar WHERE code='688585.SH' AND date='2026-11-09' "
            "AND adjust='qfq'").fetchone()
        con.close()
        self.assertIsNotNone(row, "样本行缺失")
        # 该日真实涨停 20% → 百分数刻度应 >= 9.5（修复前为 0.2 → 红）
        self.assertGreaterEqual(abs(row[0]), 9.5,
                                f"pct_chg={row[0]} 仍是小数刻度（应为百分数）")

    def test_emotion_features_detects_limit_up(self):
        import pandas as pd
        from factors.opportunities.tech_pitch_v3 import _emotion_features
        df = pd.DataFrame([
            {"code": "000001.SZ", "date": "2026-11-09", "pct_chg": 10.05,
             "high": 11.0, "low": 10.0, "close": 11.0, "turn": 0.05, "is_st": 0,
             "volume": 100000.0},
            {"code": "000001.SZ", "date": "2026-11-08", "pct_chg": 2.0,
             "high": 10.2, "low": 9.9, "close": 10.0, "turn": 0.03, "is_st": 0,
             "volume": 90000.0},
        ])
        out = _emotion_features(df)
        self.assertTrue(len(out))
        r = out.iloc[0]
        self.assertEqual(int(r["limup_cnt"]), 1, r.to_dict())
        self.assertEqual(int(r["consec_max"]), 1, r.to_dict())


class TestTurnUnit(unittest.TestCase):
    """turn 契约 = 百分数（0.2 = 0.2%），与 build_hist_mv 公式 amount/(turn/100) 对齐"""

    @unittest.skipUnless(BARS.exists(), "bars.db 不存在")
    def test_turn_percent_scale(self):
        con = sqlite3.connect(f"file:{BARS}?mode=ro&immutable=1", uri=True)
        row = con.execute(
            "SELECT turn FROM daily_bar WHERE code='600519.SH' AND date='2026-11-09' "
            "AND adjust='qfq'").fetchone()
        con.close()
        self.assertIsNotNone(row)
        # 茅台日换手真实约 0.2% → 百分数刻度应 >=0.05（修复前 0.002 → 红）
        self.assertGreaterEqual(row[0], 0.05, f"turn={row[0]} 仍是小数刻度")


if __name__ == "__main__":
    unittest.main()
