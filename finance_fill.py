#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""finance_fill.py — 财务/质量数据补齐（a-stock-data 新浪财报三表 → 上游同 schema）

产出（与上游 fetcher_finance.py / fetch_quality.py 逐列一致）：
  deepseek-harness-quant/data/cache/finance.db::finance_report
  deepseek-harness-quant/data/cache/finance_quality.db::quality

口径：
  net_profit/revenue/sq_* = 亿元；roe/gp/np/同比/cfo = 小数；period = YYYY-MM-DD；
  code = stock_basic 全格式（000001.SZ）；roe = 累计归母净利 / 归母权益。

用法：
  .venv/bin/python daily_stock_analysis/finance_fill.py --init          # 全量（约 20 分钟）
  .venv/bin/python daily_stock_analysis/finance_fill.py --codes 600519.SH,000001.SZ
  .venv/bin/python daily_stock_analysis/finance_fill.py --start 100     # 断点续传偏移
  .venv/bin/python daily_stock_analysis/finance_fill.py --status        # 只看进度
"""
import argparse
import random
import sqlite3
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # A-stock
UPSTREAM = ROOT / "deepseek-harness-quant"
sys.path.insert(0, str(UPSTREAM))

from data.finance_calc import (parse_num, quarter_month, to_cum_map,
                               single_quarter_values, yoy)  # noqa: E402

FIN_DB = UPSTREAM / "data" / "cache" / "finance.db"
QD_DB = UPSTREAM / "data" / "cache" / "finance_quality.db"
BASIC_DB = UPSTREAM / "data" / "cache" / "stock_basic.db"
PROGRESS = ROOT / "daily_stock_analysis" / "cache" / "finance_fill_failed.txt"

FIN_COLS = ["code", "period", "net_profit", "revenue", "sq_net_profit",
            "sq_net_yoy", "sq_revenue", "sq_rev_yoy", "eps", "roe", "source"]
Q_COLS = ["code", "period", "roe_avg", "gp_margin", "np_margin",
          "current_ratio", "liability_to_asset", "cfo_to_np", "cfo_to_or", "pub_date"]

NUM_PERIODS = 8          # 2 年 × 4 季：够算单季同比
N_WORKERS = 4
MIN_INTERVAL = 0.30      # 单线程对新浪最小间隔（秒）
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

_local = threading.local()


def init_finance_db(path=None) -> str:
    con = sqlite3.connect(path or str(FIN_DB))
    con.execute("""CREATE TABLE IF NOT EXISTS finance_report (
        code TEXT, period TEXT, net_profit REAL, revenue REAL,
        sq_net_profit REAL, sq_net_yoy REAL, sq_revenue REAL, sq_rev_yoy REAL,
        eps REAL, roe REAL, source TEXT,
        PRIMARY KEY (code, period))""")
    con.commit()
    con.close()
    return str(path or FIN_DB)


def init_quality_db(path=None) -> str:
    con = sqlite3.connect(path or str(QD_DB))
    con.execute("""CREATE TABLE IF NOT EXISTS quality (
        code TEXT, period TEXT, roe_avg REAL, gp_margin REAL, np_margin REAL,
        current_ratio REAL, liability_to_asset REAL, cfo_to_np REAL, cfo_to_or REAL,
        pub_date TEXT, PRIMARY KEY(code, period))""")
    con.commit()
    con.close()
    return str(path or QD_DB)


def _pick(items: dict, *names):
    for n in names:
        if n in items and items[n] is not None:
            v = parse_num(items[n])
            if v is not None:
                return v
    return None


def _yi(v):
    return None if v is None else round(v / 1e8, 4)


def build_rows(code: str, lrb: dict, fzb: dict, llb: dict, period_keys=None):
    """新浪三表原始行 → (finance_rows, quality_rows)。
    lrb/fzb/llb: {period_key('20260930'): {科目: 值}}；period_keys 显式指定顺序（测试用）。"""
    keys = period_keys if period_keys is not None else sorted(set(lrb) & set(fzb) & set(llb), reverse=True)
    per_sorted = [p for p in sorted(keys) if p in lrb and p in fzb and p in llb]
    if not per_sorted:
        return [], []

    def series_get(table, names):
        return [_pick(table[p], *names) for p in per_sorted]

    np_vals = series_get(lrb, ("归属于母公司所有者的净利润", "净利润"))
    rev_vals = series_get(lrb, ("营业总收入", "营业收入"))
    if all(v is None for v in np_vals) or all(v is None for v in rev_vals):
        return [], []

    # quarter_month/to_cum_map 只认 YYYY-MM-DD，8 位键需先转虚线格式
    dashed = [f"{p[:4]}-{p[4:6]}-{p[6:8]}" for p in per_sorted]
    cum_np = to_cum_map(dashed, np_vals)       # {(y,m): 元}
    cum_rev = to_cum_map(dashed, rev_vals)
    sq_np = single_quarter_values(cum_np)
    sq_rev = single_quarter_values(cum_rev)

    fin_rows, q_rows = [], []
    for p in per_sorted:
        period = f"{p[:4]}-{p[4:6]}-{p[6:8]}"
        ym = quarter_month(period)
        if ym is None:
            continue
        net = cum_np.get(ym)
        rev = cum_rev.get(ym)
        sqn = sq_np.get(ym)
        sqr = sq_rev.get(ym)
        cost = _pick(lrb[p], "营业成本")
        assets = _pick(fzb[p], "资产总计")
        liab = _pick(fzb[p], "负债合计")
        ca = _pick(fzb[p], "流动资产合计")
        cl = _pick(fzb[p], "流动负债合计")
        eq = _pick(fzb[p], "归属于母公司股东权益合计",
                   "所有者权益(或股东权益)合计", "所有者权益")
        cfo = _pick(llb[p], "经营活动产生的现金流量净额")
        shares = _pick(fzb[p], "实收资本(或股本)", "股本")

        roe = (net / eq) if (net is not None and eq) else None
        eps = (net / shares) if (net is not None and shares) else None
        fin_rows.append((
            code, period, _yi(net), _yi(rev), _yi(sqn),
            yoy(sq_np, ym), _yi(sqr), yoy(sq_rev, ym),
            None if eps is None else round(eps, 4),
            None if roe is None else round(roe, 4),
            "sina",
        ))
        gp = ((rev - cost) / rev) if (rev and cost is not None) else None
        npm = (net / rev) if (net is not None and rev) else None
        q_rows.append((
            code, period,
            None if roe is None else round(roe, 4),
            None if gp is None else round(gp, 4),
            None if npm is None else round(npm, 4),
            (ca / cl) if (ca is not None and cl) else None,
            (liab / assets) if (liab is not None and assets) else None,
            (cfo / net) if (cfo is not None and net) else None,
            (cfo / rev) if (cfo is not None and rev) else None,
            None,
        ))
    return fin_rows, q_rows
