# -*- coding: utf-8 -*-
"""600094 大名城 风控指标计算（Risk Manager，2026-10-23）

数据源：D:\明远阁\market_data.py kline 600094 --period daily --start 20250101 --end 20261023 --adjust qfq
口径：
  - ATR(n) = SMA(TR, n)，TR = max(H-L, |H-PC|, |L-PC|)
  - 年化波动率 = std(daily log return, ddof=1) * sqrt(252)
  - 日均成交额 = 近 20 根日线 amount 的算术均值（amount 单位：元）
  - Amihud 非流动性 = |日收益率| / 日成交额（亿元）
"""
import json
import subprocess
import math
import numpy as np
import pandas as pd

PY = r"D:\明远阁\.venv\Scripts\python.exe"
SCRIPT = r"D:\明远阁\market_data.py"


def fetch():
    out = subprocess.run([PY, SCRIPT, "kline", "600094", "--period", "daily",
                          "--start", "20250101", "--end", "20261023", "--adjust", "qfq"],
                         capture_output=True, text=True, encoding="utf-8")
    if out.returncode != 0:
        raise RuntimeError((out.stderr or "")[-2000:] + (out.stdout or "")[-2000:])
    payload = json.loads(out.stdout)
    if not payload.get("ok"):
        raise RuntimeError(str(payload))
    return payload["data"]


def main():
    rows = fetch()
    df = pd.DataFrame(rows)
    for c in ["open", "high", "low", "close", "volume", "amount", "turnover"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["close", "amount"]).reset_index(drop=True)
    df["date"] = pd.to_datetime(df["date"])

    pc = df["close"].shift(1)
    df["tr"] = np.maximum.reduce([df["high"] - df["low"],
                                  (df["high"] - pc).abs(), (df["low"] - pc).abs()])
    df["ret"] = df["close"].pct_change()
    df["logret"] = np.log(df["close"] / df["close"].shift(1))

    last = df.iloc[-1]
    print("== 样本 ==")
    print("日期范围:", df["date"].min().date(), "->", df["date"].max().date(), "共", len(df), "根日线")
    print("最新收盘(10-22):", last["close"], "当日成交额(元):", f"{last['amount']:,.0f}")

    for n in (20, 60):
        atr = df["tr"].rolling(n).mean().iloc[-1]
        print(f"\nATR({n}) = {atr:.4f} 元  (ATR/收盘 = {atr/last['close']*100:.2f}%)")

    for n in (20, 60):
        sd = df["logret"].tail(n).std(ddof=1)
        print(f"年化波动率(近{n}日) = {sd*math.sqrt(252)*100:.2f}%")
    sd_all = df["logret"].std(ddof=1)
    print(f"年化波动率(全样本{len(df)}日) = {sd_all*math.sqrt(252)*100:.2f}%")
    print(f"日收益率标准差(近20日) = {df['logret'].tail(20).std(ddof=1)*100:.3f}%")

    amt20 = df["amount"].tail(20).mean()
    amt60 = df["amount"].tail(60).mean()
    print(f"\n== 流动性 ==\n日均成交额 近20日 = {amt20:,.0f} 元 = {amt20/1e8:.2f} 亿元")
    print(f"日均成交额 近60日 = {amt60:,.0f} 元 = {amt60/1e8:.2f} 亿元")
    print(f"日均成交额 全样本 = {df['amount'].mean():,.0f} 元 = {df['amount'].mean()/1e8:.2f} 亿元")
    vol20 = df["volume"].tail(20).mean()
    print(f"近20日均成交量 = {vol20:,.0f} 股；按10-22收盘价换算日均成交额 = {vol20*last['close']/1e8:.2f} 亿元")
    print(f"近20日成交额 最小 = {df['amount'].tail(20).min():,.0f} 元；最大 = {df['amount'].tail(20).max():,.0f} 元")
    print(f"近20日换手率均值 = {df['turnover'].tail(20).mean()*100:.3f}%")

    print("\n规模占近20日均成交额比例:")
    for size in (50e4, 200e4, 500e4, 1000e4, 3000e4):
        print(f"  {size/1e4:>6.0f}万元 = {size/amt20*100:.2f}%")

    df["amihud"] = df["ret"].abs() / (df["amount"] / 1e8)
    am20 = df["amihud"].tail(20).mean()
    am60 = df["amihud"].tail(60).mean()
    am_all = df["amihud"].mean()
    print(f"\nAmihud 非流动性 近20日均值 = {am20:.5f} (%/亿元)；近60日 = {am60:.5f}；全样本 = {am_all:.5f}")
    for lbl, a in (("近20日", am20), ("近60日", am60)):
        for size in (50e4, 200e4, 500e4):
            print(f"  {lbl} Amihud={a:.5f}: {size/1e4:.0f}万元 占近20日均 {size/amt20*100:.2f}% -> 预期滑点≈{a*size/1e8*100:.2f}%")

    print("\n== 极端波动 ==")
    up = df["ret"]
    print(f"单日涨幅≥9.5% 的天数: {(up>=0.095).sum()} 次 / {len(df)} 日 ({(up>=0.095).mean()*100:.2f}%)")
    print(f"单日跌幅≤-9.5% 的天数: {(up<=-0.095).sum()} 次 / {len(df)} 日 ({(up<=-0.095).mean()*100:.2f}%)")
    amp_all = ((df["high"] - df["low"]) / pc * 100)
    print(f"单日振幅(高-低)/昨收 均值 = {amp_all.mean():.2f}%；近20日均值 = {amp_all.tail(20).mean():.2f}%")
    print(f"最大单日涨幅 = {up.max()*100:.2f}% ({df.loc[up.idxmax(),'date'].date()})")
    print(f"最大单日跌幅 = {up.min()*100:.2f}% ({df.loc[up.idxmin(),'date'].date()})")

    print("\n== 区间回撤 ==")
    recent = df[df["date"] >= "2026-01-01"]
    hi = recent["close"].max()
    lo = recent["close"].min()
    print(f"2026年内 收盘最高 = {hi} ({recent.loc[recent['close'].idxmax(),'date'].date()})，最低 = {lo} ({recent.loc[recent['close'].idxmin(),'date'].date()})")
    print(f"区间高低差 = {(hi/lo-1)*100:.1f}%；高点回撤到低点 = {(lo/hi-1)*100:.1f}%")
    runmax = df["close"].cummax()
    dd = df["close"] / runmax - 1
    print(f"全样本最大回撤 = {dd.min()*100:.1f}% (2025-07起)")
    print("\n从最新价 4.39 出发:")
    for pct in (-5, -10, -15, -20, -30, -44):
        print(f"  {pct}% -> {4.39*(1+pct/100):.2f}")

    print("\n== 涨停(≥9.5%)次日表现 ==")
    big = df[df["ret"] >= 0.095]
    if len(big):
        nxt = df["close"].shift(-1).loc[big.index]
        rr = (nxt / df["close"].loc[big.index] - 1).dropna()
        print(f"样本 {len(rr)} 次, 均值 {rr.mean()*100:.2f}%, 中位 {rr.median()*100:.2f}%, 最大 {rr.max()*100:.2f}%, 最小 {rr.min()*100:.2f}%")


if __name__ == "__main__":
    main()