# -*- coding: utf-8 -*-
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import chain_runner as cr


def _mk_bars(db: Path, latest: str):
    con = sqlite3.connect(str(db))
    con.execute("CREATE TABLE daily_bar (code TEXT, date TEXT)")
    con.execute("INSERT INTO daily_bar VALUES ('000001.SZ', ?)", (latest,))
    con.commit()
    con.close()


def _mk_opp(logs: Path, date: str):
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "opp_pool_20261109_150000.json").write_text(
        json.dumps({"date": date, "n": 3}), encoding="utf-8")


class TestFreshness(unittest.TestCase):
    def test_check_fresh_when_opp_covers_bars(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            _mk_bars(d / "bars.db", "2026-11-09")
            _mk_opp(d / "logs", "2026-11-09")
            with mock.patch.object(cr, "BARS_DB", d / "bars.db"), \
                 mock.patch.object(cr, "LOGS", d / "logs"):
                self.assertEqual(cr.check(), 0)

    def test_check_stale_when_opp_older(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            _mk_bars(d / "bars.db", "2026-11-09")
            _mk_opp(d / "logs", "2026-11-06")
            with mock.patch.object(cr, "BARS_DB", d / "bars.db"), \
                 mock.patch.object(cr, "LOGS", d / "logs"):
                self.assertEqual(cr.check(), 2)

    def test_check_stale_when_no_opp(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            _mk_bars(d / "bars.db", "2026-11-09")
            (d / "logs").mkdir()
            with mock.patch.object(cr, "BARS_DB", d / "bars.db"), \
                 mock.patch.object(cr, "LOGS", d / "logs"):
                self.assertEqual(cr.check(), 2)

    def test_finance_ready_false_when_missing(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            with mock.patch.object(cr, "FIN_DB", d / "nope.db"), \
                 mock.patch.object(cr, "QD_DB", d / "nope2.db"):
                self.assertFalse(cr.finance_ready())


if __name__ == "__main__":
    unittest.main()
