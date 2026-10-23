# -*- coding: utf-8 -*-
"""回测：『放量站上 20 日均线』这个信号，进场到底是早还是晚？

对每只票，历史找出所有「收盘价上穿 MA20 且成交量 >= 20日均量 * 1.5」的日子，
统计之后 1/3/5/10 个交易日的收益率分布（中位数、胜率、最好、最差）。
再对比「信号出现时价格距离最近 20 日最低价」的距离，看是不是已经涨透了。
"""
import json
import subprocess
import statistics

PY = r"D:\明远阁\.venv\Scripts\python.exe"
SCRIPT = r"D:\明远阁\market_data.py"
CODES = {"300287": "飞利信", "600094": "大名城", "000514": "渝开发", "600279": "重庆港"}


def kline(code):
    out = subprocess.run(
        [PY, SCRIPT, "kline", code, "--period", "daily", "--start", "20230101", "--end", "20261231", "--adjust", "qfq"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
    )
    text = out.stdout.strip()
    s = text.find("{")
    if s < 0:
        raise RuntimeError(f"{code} no json: {out.stderr[:150]}")
    return json.loads(text[s:])["data"]


def sma(vals, n, i):
    if i + 1 < n:
        return None
    return sum(vals[i + 1 - n:i + 1]) / n


def analyze(code, name):
    rows = kline(code)
    closes = [r["close"] for r in rows]
    vols = [r["volume"] for r in rows]
    dates = [r["date"] for r in rows]

    signals = []
    for i in range(25, len(rows) - 10):
        ma20 = sma(closes, 20, i)
        ma20_prev = sma(closes, 20, i - 1)
        avgv = sma(vols, 20, i - 1)
        if not ma20 or not ma20_prev or not avgv:
            continue
        if closes[i - 1] <= ma20_prev and closes[i] > ma20 and vols[i] >= 1.5 * avgv:
            # 距离最近 20 日最低价的距离（判断是否已经涨透）
            recent_low = min(closes[max(0, i - 20):i + 1])
            dist = (closes[i] / recent_low - 1) * 100
            rets = {}
            for n in (1, 3, 5, 10):
                if i + n < len(closes):
                    rets[n] = (closes[i + n] / closes[i] - 1) * 100
            signals.append({"date": dates[i], "dist_low": dist, **{f"r{n}": v for n, v in rets.items()}})

    if not signals:
        return f"{code} {name}: 无信号样本"

    lines = [f"\n=== {code} {name}｜信号样本 {len(signals)} 次 ==="]
    for n in (1, 3, 5, 10):
        key = f"r{n}"
        vals = [s[key] for s in signals if key in s]
        if not vals:
            continue
        win = sum(1 for v in vals if v > 0) / len(vals) * 100
        lines.append(
            f"  后 {n:>2} 日：中位 {statistics.median(vals):+.2f}%｜均值 {statistics.mean(vals):+.2f}%｜"
            f"胜率 {win:.0f}%｜最好 {max(vals):+.2f}%｜最差 {min(vals):+.2f}%｜样本 {len(vals)}"
        )
    dists = [s["dist_low"] for s in signals]
    lines.append(f"  信号出现时距 20 日低点：中位 {statistics.median(dists):+.1f}%｜均值 {statistics.mean(dists):+.1f}%")
    # 分组：距离低点 <5% vs >=5%
    low_g = [s for s in signals if s["dist_low"] < 5]
    high_g = [s for s in signals if s["dist_low"] >= 5]
    for label, grp in (("距低点<5%", low_g), ("距低点>=5%", high_g)):
        vals = [s["r5"] for s in grp if "r5" in s]
        if vals:
            win = sum(1 for v in vals if v > 0) / len(vals) * 100
            lines.append(f"  {label}：后5日中位 {statistics.median(vals):+.2f}%｜胜率 {win:.0f}%｜样本 {len(vals)}")
    return "\n".join(lines)


for code, name in CODES.items():
    try:
        print(analyze(code, name))
    except Exception as e:
        print(f"{code}: FAILED {e}")
