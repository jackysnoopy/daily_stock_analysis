# -*- coding: utf-8 -*-
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "daily_stock_analysis"))
sys.path.insert(0, str(ROOT / "deepseek-harness-quant"))

import finance_fill as ff

UP_FIN_COLS = ["code", "period", "net_profit", "revenue", "sq_net_profit",
               "sq_net_yoy", "sq_revenue", "sq_rev_yoy", "eps", "roe", "source"]
UP_Q_COLS = ["code", "period", "roe_avg", "gp_margin", "np_margin",
             "current_ratio", "liability_to_asset", "cfo_to_np", "cfo_to_or", "pub_date"]


def _cols(db_path, table):
    con = sqlite3.connect(db_path)
    rows = [r[1] for r in con.execute(f"PRAGMA table_info({table})")]
    con.close()
    return rows


class TestSchema(unittest.TestCase):
    def test_finance_report_columns_match_upstream(self):
        with tempfile.TemporaryDirectory() as d:
            p = str(Path(d) / "finance.db")
            ff.init_finance_db(p)
            self.assertEqual(_cols(p, "finance_report"), UP_FIN_COLS)

    def test_quality_columns_match_upstream(self):
        with tempfile.TemporaryDirectory() as d:
            p = str(Path(d) / "finance_quality.db")
            ff.init_quality_db(p)
            self.assertEqual(_cols(p, "quality"), UP_Q_COLS)

    def test_module_cols_match_ddl_order(self):
        # 锁定 ff.FIN_COLS/Q_COLS 与 DDL 列序一致（Task 4 位置式 INSERT 依赖）
        self.assertEqual(ff.FIN_COLS, UP_FIN_COLS)
        self.assertEqual(ff.Q_COLS, UP_Q_COLS)


def _canned_tables():
    """4 期（含去年同期）三表原始数据，单位：元。覆盖全部必需科目。"""
    periods = ["20250630", "20250930", "20260630", "20260930"]
    lrb, fzb, llb = {}, {}, {}
    for i, p in enumerate(periods):
        np_ = 10e8 * (i + 1)              # 累计净利 10/20/30/40 亿
        rev = 100e8 * (i + 1)
        lrb[p] = {"归属于母公司所有者的净利润": str(np_),
                  "净利润": str(np_ + 1e6),
                  "营业总收入": str(rev),
                  "营业成本": str(rev * 0.6)}
        fzb[p] = {"资产总计": str(500e8), "负债合计": str(200e8),
                  "流动资产合计": str(300e8), "流动负债合计": str(150e8),
                  "归属于母公司股东权益合计": str(300e8),
                  "实收资本(或股本)": str(10e8)}
        llb[p] = {"经营活动产生的现金流量净额": str(8e8 * (i + 1))}
    return periods, lrb, fzb, llb


class TestBuildRows(unittest.TestCase):
    def test_ratios_units_and_single_quarter(self):
        periods, lrb, fzb, llb = _canned_tables()
        fin, qual = ff.build_rows("000001.SZ", lrb, fzb, llb,
                                  period_keys=periods)
        self.assertEqual(len(fin), 4)
        self.assertEqual(len(qual), 4)
        # 最新期 2026-09-30：累计净利 40 亿 / 累计营收 400 亿
        row = dict(zip(ff.FIN_COLS, next(r for r in fin if r[1] == "2026-09-30")))
        self.assertAlmostEqual(row["net_profit"], 40.0, places=2)
        self.assertAlmostEqual(row["revenue"], 400.0, places=2)
        # 单季净利 = 40 - 30 = 10 亿（2026Q3 单季）
        self.assertAlmostEqual(row["sq_net_profit"], 10.0, places=2)
        # 单季同比 = (2026Q3 - 2025Q3)/|2025Q3| = (10-10)/10 = 0
        self.assertAlmostEqual(row["sq_net_yoy"], 0.0, places=6)
        # roe = 40/300（累计/归母权益，小数）
        self.assertAlmostEqual(row["roe"], 40.0 / 300.0, places=4)
        q = dict(zip(ff.Q_COLS, next(r for r in qual if r[1] == "2026-09-30")))
        # gp = (400-240)/400 = 0.4
        self.assertAlmostEqual(q["gp_margin"], 0.4, places=4)
        self.assertAlmostEqual(q["np_margin"], 0.1, places=4)
        self.assertAlmostEqual(q["current_ratio"], 2.0, places=4)
        self.assertAlmostEqual(q["liability_to_asset"], 0.4, places=4)
        # cfo_to_np = 32/40 = 0.8；cfo_to_or = 32/400 = 0.08
        self.assertAlmostEqual(q["cfo_to_np"], 0.8, places=4)
        self.assertAlmostEqual(q["cfo_to_or"], 0.08, places=4)

    def test_missing_keys_tolerated(self):
        fin, qual = ff.build_rows("600519.SH", {"20260630": {}}, {}, {},
                                  period_keys=["20260630"])
        self.assertEqual(fin, [])
        self.assertEqual(qual, [])


if __name__ == "__main__":
    unittest.main()
