# -*- coding: utf-8 -*-
"""盘中小助手 v2：价格突破 + 量能确认，两个条件同时满足才算「启动」。

判断逻辑：
- 向上启动 = 价格站上触发价 且 量能倍率 >= VOL_MULT
- 量能倍率 = 今日成交量 / (20 日均量 × 当日已过交易时间占比)
  这样盘中任意时点都能判断「是不是放量」，不会因为只过了半天就误判缩量。
- 向下破位 = 只看价格，破位不需要量能确认

用法：
    python watch_check.py            # 只报触发
    python watch_check.py --all      # 报全部状态（含量能倍率）
退出码：0 无触发 / 2 有触发 / 1 取数失败
"""
import datetime
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import PY, SCRIPT, BASELINE, MAIL_SCRIPT  # noqa: E402

VOL_MULT = 1.5   # 放量标准：达到同时段均量的 1.5 倍
CHASE_MAX = 8.0  # 距 20 日低点涨幅上限；超过即视为追高，放弃

# up=向上启动价, down=向下破位价
# 000514 渝开发 已于 2026-10-23 三季报后移出（Q3 扣非转负 -2010.7 万、减值扩大、跌破 20 日低点）
# 重新纳入条件：定增正式发行完成 / 放量站上 4.26 且距 20 日低点 <8% / 年报扣非转正
WATCH = {
    "300287": {"name": "飞利信", "up": 3.62, "down": 3.17,
               "upnote": "站上60日线，趋势转强", "downnote": "跌破今日低点，反抽失败"},
    "600279": {"name": "重庆港", "up": 4.41, "down": 3.94,
               "upnote": "站上最重套牢带上沿", "downnote": "跌破近60日低点"},
    "600094": {"name": "大名城", "up": 4.54, "down": 4.20,
               "upnote": "突破前高压力", "downnote": "回踩失守密集带"},
}

SESSIONS = [((9, 30), (11, 30)), ((13, 0), (15, 0))]
TOTAL_MIN = 240


def elapsed_fraction(now=None):
    now = now or datetime.datetime.now()
    t = now.hour * 60 + now.minute + now.second / 60.0
    done = 0.0
    for (h1, m1), (h2, m2) in SESSIONS:
        s, e = h1 * 60 + m1, h2 * 60 + m2
        if t <= s:
            break
        done += min(t, e) - s
    return max(0.0, min(1.0, done / TOTAL_MIN))


def fetch(codes):
    out = subprocess.run(
        [PY, SCRIPT, "quote"] + codes,
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240,
    )
    text = out.stdout.strip()
    start = text.find("{")
    if start < 0:
        raise RuntimeError(f"no json in output: {out.stdout[:200]} {out.stderr[:200]}")
    return json.loads(text[start:])


def main():
    show_all = "--all" in sys.argv
    if datetime.date.today().weekday() >= 5 and not show_all:
        print("NO_ALERT")
        sys.exit(0)
    frac = elapsed_fraction()
    try:
        base = json.load(open(BASELINE, encoding="utf-8"))
    except Exception:
        base = {}

    data = fetch(list(WATCH))
    if not data.get("ok"):
        print(f"[ERROR] 取数失败: {data.get('error')}")
        sys.exit(1)

    alerts, rows = [], []
    for r in data["data"]:
        code = r["code"]
        rule = WATCH.get(code)
        if not rule:
            continue
        p = r["price"]
        b = base.get(code, {})
        avg = b.get("avg_vol20")
        ratio = (r["volume"] / (avg * frac)) if (avg and frac > 0.02) else None
        rows.append((code, r["name"], p, r["pct_chg"], r["time"], ratio, rule))

        low20 = b.get("low20")
        dist = ((p / low20 - 1) * 100) if low20 else None

        if p >= rule["up"]:
            if ratio is None or ratio >= VOL_MULT:
                if dist is not None and dist > CHASE_MAX:
                    alerts.append(
                        f"[启动但已追高] {code} {r['name']} 现价 {p}（{r['pct_chg']:+.2f}%）站上 {rule['up']}，"
                        f"量能 {ratio:.2f}x，但已离 20 日低点 {low20} 上涨 {dist:.1f}%（上限 {CHASE_MAX:.0f}%）→ 放弃这次，别接最后一棒｜{r['time']}"
                        if ratio else
                        f"[启动但已追高] {code} {r['name']} {p} 站上 {rule['up']}，距 20 日低点 {dist:.1f}%→ 放弃｜{r['time']}"
                    )
                else:
                    dist_s = f"{dist:.1f}%" if dist is not None else "n/a"
                    alerts.append(
                        f"[启动·可介入窗口] {code} {r['name']} 现价 {p}（{r['pct_chg']:+.2f}%）站上 {rule['up']}，"
                        f"量能 {ratio:.2f}x，距 20 日低点仅 {dist_s} → {rule['upnote']}｜{r['time']}"
                        if ratio else
                        f"[启动·可介入窗口] {code} {r['name']} {p} 站上 {rule['up']}，距 20 日低点 {dist_s}（量能未确认）｜{r['time']}"
                    )
            else:
                rows[-1] = rows[-1] + ("价格已到位但量能不足，等放量",)
        if p <= rule["down"]:
            alerts.append(
                f"[破位] {code} {r['name']} 现价 {p}（{r['pct_chg']:+.2f}%）跌破 {rule['down']} → {rule['downnote']}｜{r['time']}"
            )

    if alerts:
        print("ALERT:")
        for a in alerts:
            print(" - " + a)
        if "--mail" in sys.argv:
            body = "盘中触发提醒\n\n" + "\n".join("- " + a for a in alerts) + \
                   "\n\n以上为研究记录，不构成投资建议。"
            subprocess.run(
                [PY, MAIL_SCRIPT, "--body", body,
                 "--subject", "明远阁 | 盘中触发提醒 " + datetime.date.today().isoformat()],
                timeout=120,
            )
    elif show_all:
        print(f"无触发。已过交易时间 {frac*100:.0f}%，放量标准 {VOL_MULT}x")
        for row in rows:
            code, name, p, pct, t, ratio, rule = row[:7]
            extra = row[7] if len(row) > 7 else ""
            rs = f"{ratio:.2f}x" if ratio else "n/a"
            print(f" - {code} {name} {p}（{pct:+.2f}%）量能 {rs}｜区间 {rule['down']}~{rule['up']}｜{t} {extra}")
    else:
        print("NO_ALERT")

    sys.exit(2 if alerts else 0)


if __name__ == "__main__":
    main()
