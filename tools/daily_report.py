# -*- coding: utf-8 -*-
"""每日收盘总结 v2 —— 只放行情软件上看不到的东西。

包含：市场情绪（封板率/连板高度/炸板）、板块持续性（5日/20日）、
资金与成交额趋势、观察池个股技术判定、明日关注清单。

输出：终端文本 + D:\\明远阁\\reports\\YYYY-MM-DD.md
历史：D:\\明远阁\\history\\YYYY-MM-DD.json（用于计算板块与成交额的连续性）
"""
import datetime
import json
import os
import subprocess
import sys
import urllib.request

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import BASE, PY, SCRIPT, REPORT_DIR, HIST_DIR  # noqa: E402
WATCH = ["300287", "600279", "000514", "600094"]

pd.set_option("display.unicode.east_asian_width", True)


def sina_index():
    req = urllib.request.Request(
        "http://hq.sinajs.cn/list=s_sh000001,s_sz399001,s_sz399006,s_sh000300",
        headers={"Referer": "https://finance.sina.com.cn"},
    )
    raw = urllib.request.urlopen(req, timeout=20).read().decode("gbk")
    names = {"sh000001": "上证指数", "sz399001": "深证成指", "sz399006": "创业板指", "sh000300": "沪深300"}
    out = {}
    for line in raw.strip().split("\n"):
        if "=" not in line:
            continue
        key = line.split("=")[0].split("_")[-1]
        v = line.split('"')[1].split(",")
        if len(v) < 6:
            continue
        out[names.get(key, key)] = {"close": float(v[1]), "pct": float(v[3]),
                                    "amount_wan": float(v[5]) if v[5] else 0}
    return out


def fetch_quotes(codes):
    out = subprocess.run(
        [PY, SCRIPT, "quote"] + codes,
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
    )
    t = out.stdout.strip()
    i = t.find("{")
    if i < 0:
        return {}
    d = json.loads(t[i:])
    if not d.get("ok"):
        return {}
    return {r["code"]: r for r in d["data"]}


def kline_stats(code, quote=None):
    out = subprocess.run(
        [PY, SCRIPT, "kline", code, "--period", "daily", "--start", "20250301", "--end", "20261231", "--adjust", "qfq"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
    )
    t = out.stdout.strip()
    i = t.find("{")
    if i < 0:
        raise RuntimeError("no json")
    rows = json.loads(t[i:])["data"]
    today = datetime.date.today().isoformat()
    # 若 K 线最后一根不是今天（新浪日线收盘后才出），用实时快照补今日
    live = quote if (quote and rows and rows[-1]["date"] != today) else None
    hist = rows if live is None else rows  # 均线/低点用已收盘的历史
    if live is not None:
        # 今日这根单独处理：历史序列剔除可能存在的今日
        hist = [r for r in rows if r["date"] != today]
        close = live["price"]
        vol_today = live["volume"]
    else:
        hist = rows[:-1]
        close = rows[-1]["close"]
        vol_today = rows[-1]["volume"]
    ma = lambda n: sum(r["close"] for r in hist[-n:]) / n
    low20 = min(r["low"] for r in hist[-20:])
    avgv = sum(r["volume"] for r in hist[-20:]) / 20
    return {
        "close": close, "ma5": ma(5), "ma20": ma(20), "ma60": ma(60) if len(hist) >= 60 else None,
        "low20": low20, "dist_low": (close / low20 - 1) * 100,
        "vol": vol_today, "vol_ratio": vol_today / avgv if avgv else None,
        "date": today, "live": live is not None,
    }


def main():
    today = datetime.date.today()
    ds = today.strftime("%Y%m%d")
    iso = today.isoformat()
    os.makedirs(REPORT_DIR, exist_ok=True)
    os.makedirs(HIST_DIR, exist_ok=True)
    L = [f"# 收盘总结 {iso}", ""]

    idx = sina_index()
    amt_total = (idx.get("上证指数", {}).get("amount_wan", 0) + idx.get("深证成指", {}).get("amount_wan", 0)) / 1e4

    L.append("## 一、市场情绪（涨停池）")
    zt = zb = dt = None
    try:
        import akshare as ak
        zt = ak.stock_zt_pool_em(date=ds)
        zb = ak.stock_zt_pool_zbgc_em(date=ds)
        dt = ak.stock_zt_pool_dtgc_em(date=ds)
    except Exception as e:
        L.append(f"- 涨停池取数失败：{type(e).__name__}")

    if zt is not None:
        nzt, nzb, ndt = len(zt), len(zb), len(dt)
        seal = nzt / (nzt + nzb) * 100 if (nzt + nzb) else 0
        L.append(f"- 涨停 {nzt} 家｜炸板 {nzb} 家｜跌停 {ndt} 家｜**封板率 {seal:.1f}%**（炸板率 {100-seal:.1f}%）")
        zt["连板数"] = pd.to_numeric(zt["连板数"], errors="coerce")
        maxlb = int(zt["连板数"].max())
        dist = zt["连板数"].value_counts().sort_index()
        parts = [f"{int(k)}板×{int(v)}" for k, v in dist.items() if int(k) >= 1]
        L.append(f"- 连板结构：{'｜'.join(parts)}｜最高 **{maxlb} 板**")
        zt["封板资金"] = pd.to_numeric(zt["封板资金"], errors="coerce")
        top_seal = zt.nlargest(3, "封板资金")
        L.append("- 封单最厚：" + "｜".join(f"{r['名称']} {r['封板资金']/1e8:.2f} 亿" for _, r in top_seal.iterrows()))
        ind = zt["所属行业"].value_counts().head(5)
        L.append("- 涨停行业分布：" + "｜".join(f"{k} {v}" for k, v in ind.items()))
        lb = zt[zt["连板数"] >= 2].sort_values("连板数", ascending=False)
        if len(lb):
            L.append("- 连板股（明日最容易分化）：" + "｜".join(
                f"{r['名称']}({int(r['连板数'])}板)" for _, r in lb.head(8).iterrows()))
    L.append("")

    L.append("## 二、量能与趋势")
    L.append(f"- 两市成交额约 **{amt_total:.0f} 亿元**")
    # 历史对比
    prev = sorted(f for f in os.listdir(HIST_DIR) if f.endswith(".json") and not f.startswith(iso))
    if prev:
        amts = []
        for f in prev[-20:]:
            try:
                h = json.load(open(os.path.join(HIST_DIR, f), encoding="utf-8"))
                amts.append(h.get("amount", 0))
            except Exception:
                pass
        if amts:
            a5 = sum(amts[-5:]) / len(amts[-5:])
            a20 = sum(amts) / len(amts)
            L.append(f"- 对比：前 5 日均值 {a5:.0f} 亿（**{amt_total/a5*100-100:+.1f}%**）｜前 20 日均值 {a20:.0f} 亿（{amt_total/a20*100-100:+.1f}%）")
    L.append("")

    L.append("## 三、指数")
    for k, v in idx.items():
        L.append(f"- {k} {v['close']:.2f}（{v['pct']:+.2f}%）")
    L.append("")

    # 板块
    L.append("## 四、板块强度与持续性")
    sec_hist = {}
    try:
        import akshare as ak
        sec = ak.stock_board_industry_summary_ths()
        sec["涨跌幅"] = pd.to_numeric(sec["涨跌幅"], errors="coerce")
        sec["总成交额"] = pd.to_numeric(sec["总成交额"], errors="coerce")
        cur = dict(zip(sec["板块"], sec["涨跌幅"]))
        # 读历史板块涨幅
        seq = {}
        for f in prev[-5:]:
            try:
                h = json.load(open(os.path.join(HIST_DIR, f), encoding="utf-8"))
                for k, v in h.get("sectors", {}).items():
                    seq.setdefault(k, []).append(v)
            except Exception:
                pass
        rows = []
        for _, r in sec.iterrows():
            past = seq.get(r["板块"], [])
            s5 = sum(past[-4:]) + r["涨跌幅"] if past else None
            rows.append((r["板块"], r["涨跌幅"], s5, r["领涨股"]))
        rows.sort(key=lambda x: -x[1])
        L.append("**今日最强**：")
        for n, t, s5, ld in rows[:5]:
            s5s = f"｜近5日累计 {s5:+.1f}%" if s5 is not None else ""
            L.append(f"- {n} {t:+.2f}%{s5s}（领涨 {ld}）")
        L.append("**今日最弱**：")
        for n, t, s5, ld in rows[-3:]:
            L.append(f"- {n} {t:+.2f}%")
        L.append("**持续性提示**：同一板块连续 2 日以上进前五，才算主线；单日冲高多为轮动。")
        sec_hist = cur
        # 保存历史
        json.dump({"date": iso, "amount": amt_total,
                   "sectors": {k: float(v) for k, v in cur.items() if pd.notna(v)}},
                  open(os.path.join(HIST_DIR, f"{iso}.json"), "w", encoding="utf-8"), ensure_ascii=False)
    except Exception as e:
        L.append(f"- 板块取数失败：{type(e).__name__}: {e}")
    L.append("")

    # 观察池个股判定
    L.append("## 五、观察池个股技术判定")
    L.append("> 判定标准：距 20 日低点 <8% 且站上 MA20 且量能 ≥1.5 倍，三者同时满足才叫「启动」")
    quotes = fetch_quotes(WATCH)
    for code in WATCH:
        try:
            s = kline_stats(code, quotes.get(code))
            flags = []
            flags.append("距低点" + ("✅" if s["dist_low"] < 8 else "❌") + f" {s['dist_low']:+.1f}%")
            flags.append("MA20" + ("✅" if s["close"] > s["ma20"] else "❌") + f" {(s['close']/s['ma20']-1)*100:+.1f}%")
            flags.append("量能" + ("✅" if (s["vol_ratio"] or 0) >= 1.5 else "❌") + f" {(s['vol_ratio'] or 0):.2f}x")
            src = "含今日" if s.get("live") else s["date"]
            nm = (quotes.get(code) or {}).get("name", "").replace(" ", "")
            L.append(f"- **{code} {nm}** 收 {s['close']}（{src}）：" + "｜".join(flags))
        except Exception as e:
            L.append(f"- {code} 判定失败：{type(e).__name__}")
    L.append("")

    L.append("## 六、风险提示")
    L.append("- 本报告为研究记录，不构成投资建议。")
    L.append("- 涨停池数据来自东方财富，个别日期可能缺失；封板率仅反映当日情绪，不代表次日走势。")

    text = "\n".join(L)
    path = os.path.join(REPORT_DIR, f"{iso}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(text)
    print(f"\n[saved] {path}")


if __name__ == "__main__":
    main()
