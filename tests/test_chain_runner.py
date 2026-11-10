# -*- coding: utf-8 -*-
import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import chain_runner as cr


def _mk_bars(db: Path, latest: str):
    # qfq 行 = 基线日；none 行 = 基线日+1（模拟 fill_timing 盘中快照更晚）
    con = sqlite3.connect(str(db))
    con.execute("CREATE TABLE daily_bar (code TEXT, date TEXT, adjust TEXT)")
    con.execute("INSERT INTO daily_bar VALUES ('000001.SZ', ?, 'qfq')", (latest,))
    next_day = (date.fromisoformat(latest) + timedelta(days=1)).isoformat()
    con.execute("INSERT INTO daily_bar VALUES ('000001.SZ', ?, 'none')", (next_day,))
    con.commit()
    con.close()


PLACEHOLDER_NOTE = "本环境未运行上游 18:30 全链路/无真实持仓，不生成占位标的与决策"


def _mk_opp(logs: Path, date: str, pitch=None,
            name="opp_pool_20261109_150000.json", n=3, note=None):
    logs.mkdir(parents=True, exist_ok=True)
    payload = {"date": date, "n": n, "pitch": pitch or []}
    if note is not None:
        payload["note"] = note
    (logs / name).write_text(json.dumps(payload), encoding="utf-8")


def _mk_placeholder_opp(logs: Path, date: str,
                        name="opp_pool_20261110_130026.json"):
    # fill_deck_data.do_contracts 写出的空占位池风格
    _mk_opp(logs, date, name=name, n=0, note=PLACEHOLDER_NOTE)


def _set_mtime(path: Path, ts: float):
    import os
    os.utime(path, (ts, ts))


class TestFreshness(unittest.TestCase):
    def setUp(self):
        # 测试零副作用：不向真实 chain_runner.log 追加
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patcher = mock.patch.object(cr, "RUN_LOG",
                                    Path(tmp.name) / "runner.log")
        patcher.start()
        self.addCleanup(patcher.stop)

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

    def test_check_ignores_newer_none_snapshot(self):
        # _mk_bars 的 none 行比 qfq 基线日晚 1 天：bars_latest 只看 qfq，
        # opp=基线日 → 0 新鲜；opp 更早 → 2
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            _mk_bars(d / "bars.db", "2026-11-09")
            _mk_opp(d / "logs", "2026-11-09")
            with mock.patch.object(cr, "BARS_DB", d / "bars.db"), \
                 mock.patch.object(cr, "LOGS", d / "logs"):
                self.assertEqual(cr.check(), 0)
            _mk_opp(d / "logs", "2026-11-08")
            with mock.patch.object(cr, "BARS_DB", d / "bars.db"), \
                 mock.patch.object(cr, "LOGS", d / "logs"):
                self.assertEqual(cr.check(), 2)

    def test_finance_ready_false_when_missing(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            with mock.patch.object(cr, "FIN_DB", d / "nope.db"), \
                 mock.patch.object(cr, "QD_DB", d / "nope2.db"):
                self.assertFalse(cr.finance_ready())

    def test_check_returns_2_when_bars_db_missing(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            with mock.patch.object(cr, "BARS_DB", d / "nope.db"):
                self.assertEqual(cr.check(), 2)

    def test_placeholder_only_is_stale(self):
        # 用例 D：只有 fill 占位池（date=bars 最新）→ 占位不算新鲜 → 2
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            _mk_bars(d / "bars.db", "2026-11-09")
            _mk_placeholder_opp(d / "logs", "2026-11-09")
            with mock.patch.object(cr, "BARS_DB", d / "bars.db"), \
                 mock.patch.object(cr, "LOGS", d / "logs"):
                self.assertEqual(cr.check(), 2)
                self.assertEqual(cr.opp_latest_date(), "")

    def test_placeholder_shadowed_by_real_pool_is_fresh(self):
        # 用例 E：占位 + 更新的真实池（n>0，date 相同或更晚，mtime 更晚）
        # → 0，且 opp_latest_date() 返回真实池的 date
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            _mk_bars(d / "bars.db", "2026-11-09")
            ph = d / "logs" / "opp_pool_20261110_130026.json"
            real = d / "logs" / "opp_pool_20261110_130040.json"
            _mk_placeholder_opp(d / "logs", "2026-11-09",
                                name=ph.name)
            _mk_opp(d / "logs", "2026-11-10", name=real.name, n=706)
            _set_mtime(ph, 1_800_000_000)
            _set_mtime(real, 1_800_000_600)
            with mock.patch.object(cr, "BARS_DB", d / "bars.db"), \
                 mock.patch.object(cr, "LOGS", d / "logs"):
                self.assertEqual(cr.check(), 0)
                self.assertEqual(cr.opp_latest_date(), "2026-11-10")


class TestMainPitchDegradation(unittest.TestCase):
    """空 pitch 候选降级：pitch 步 rc!=0 但 opp pitch=0 → rc=0；pitch>0 → rc=1"""

    def _run_main(self, d: Path, rcs: dict, pitch: list) -> int:
        _mk_bars(d / "bars.db", "2026-11-09")
        _mk_opp(d / "logs", "2026-11-09", pitch=pitch)

        def fake_run_cmd(name, cmd, timeout):
            return rcs.get(name, 0)

        with mock.patch.object(cr, "BARS_DB", d / "bars.db"), \
             mock.patch.object(cr, "LOGS", d / "logs"), \
             mock.patch.object(cr, "RUN_LOG", d / "chain_runner.log"), \
             mock.patch.object(cr, "run_cmd", side_effect=fake_run_cmd), \
             mock.patch.object(sys, "argv",
                               ["chain_runner.py", "--now", "--skip-finance"]):
            return cr.main()

    def test_empty_pitch_pool_with_nonzero_rc_is_success(self):
        with tempfile.TemporaryDirectory() as d:
            rc = self._run_main(Path(d), {"scan": 0, "pitch": 1}, pitch=[])
            self.assertEqual(rc, 0)

    def test_nonempty_pitch_pool_with_nonzero_rc_is_failure(self):
        with tempfile.TemporaryDirectory() as d:
            rc = self._run_main(Path(d), {"scan": 0, "pitch": 1},
                                pitch=[{"code": "000001.SZ"}])
            self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
