# -*- coding: utf-8 -*-
"""明远阁 · 盘中异动/风险检查。

规则（对 watchlist.json 里的每只票）：
  R1 涨跌幅绝对值 >= 5%
  R2 现价跨越 MA20（上穿/下破）
  R3 RSI(14) >= 70 或 <= 30
  R4 触发止损线（watchlist 里 stop_loss 字段，可选）
同一标的同一规则同一交易日只报一次（状态存 alerts_state.json）。

用法：
  python tools/intraday_alert.py            # 检查，触发则打印
  python tools/intraday_alert.py --send     # 触发时发邮件
  python tools/intraday_alert.py --force    # 忽略当日去重
"""
import argparse
import datetime as dt
import json
import os
import pathlib
import subprocess
import sys

BASE = pathlib.Path(__file__).resolve().parent.parent
PY = BASE / ".venv" / "Scripts" / "python.exe"
MD = BASE / "market_data.py"
MAILER = BASE / "tools" / "send_mail.py"
WATCH = BASE / "watchlist.json"
STATE = BASE / "alerts_state.json"


def call(argv):
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    p = subprocess.run([str(PY), str(MD), *argv], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env, timeout=120)
    try:
        return json.loads(p.stdout.strip())
    except Exception:
        return {"ok": False, "error": {"message": (p.stdout or p.stderr or "")[:150]}}


def ma(closes, n):
    return round(sum(closes[-n:]) / n, 2) if len(closes) >= n else None


def rsi(closes, n=14):
    if len(closes) <= n:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    ag, al = sum(gains[-n:]) / n, sum(losses[-n:]) / n
    if al == 0:
        return 100.0
    return round(100 - 100 / (1 + ag / al), 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    cfg = json.loads(WATCH.read_text(encoding="utf-8")) if WATCH.exists() else {}
    stocks = cfg.get("stocks") or []
    stop_loss = cfg.get("stop_loss") or {}
    if not stocks:
        print("NO_WATCHLIST")
        return 0

    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    today = dt.date.today().isoformat()
    today_state = state.setdefault(today, {})

    alerts = []
    for code in stocks:
        q = call(["quote", code])
        if not q.get("ok") or not q.get("data"):
            alerts.append(f"[{code}] 行情取数失败：{q.get('error')}")
            continue
        d = q["data"][0]
        price = float(d.get("price") or 0)
        pct = float(d.get("pct_chg") or 0)
        name = d.get("name") or code

        if abs(pct) >= 5:
            key = f"{code}|R1"
            if key not in today_state or args.force:
                alerts.append(f"[{name} {code}] 涨跌幅 {pct:+.2f}%（阈值 ±5%）现金价 {price}")
                today_state[key] = True

        sl = stop_loss.get(code)
        if sl and price and price <= float(sl):
            key = f"{code}|R4"
            if key not in today_state or args.force:
                alerts.append(f"[{name} {code}] 触发止损线 {sl}，现价 {price}（距止损 {(price/float(sl)-1)*100:+.2f}%）")
                today_state[key] = True

        today = dt.date.today()
        start = (today - dt.timedelta(days=150)).strftime("%Y%m%d")
        k = call(["kline", code, "--period", "daily", "--start", start, "--end", today.strftime("%Y%m%d")])
        if not k.get("ok") or not k.get("data"):
            continue
        rows = k["data"]
        closes = [float(r["close"]) for r in rows]
        prev_close = closes[-1]
        ma20 = ma(closes, 20)
        r = rsi(closes)
        if ma20 and price:
            crossed = (prev_close < ma20 <= price) or (prev_close > ma20 >= price)
            if crossed:
                key = f"{code}|R2"
                if key not in today_state or args.force:
                    direction = "上穿" if price > ma20 else "下破"
                    alerts.append(f"[{name} {code}] {direction} MA20（MA20 {ma20}，现价 {price}）")
                    today_state[key] = True
        if r is not None and (r >= 70 or r <= 30):
            key = f"{code}|R3"
            if key not in today_state or args.force:
                alerts.append(f"[{name} {code}] RSI(14) {r}（极值区 70/30），现价 {price}")
                today_state[key] = True

    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")

    if not alerts:
        print("NO_ALERT")
        return 0

    body = "\n".join([f"# 明远阁 · 盘中异动 {dt.datetime.now():%Y-%m-%d %H:%M}", ""] +
                     [f"- {a}" for a in alerts] +
                     ["", "规则：±5% / 跨越 MA20 / RSI 极值 / 止损线。只做规则提示，不构成投资建议。"])
    print(body)

    if args.send:
        env = {**os.environ}
        p = subprocess.run([str(PY), str(MAILER), "--subject",
                            f"Mingyuan | 盘中异动 {dt.datetime.now():%m-%d %H:%M}",
                            "--body", body], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=env, timeout=120)
        print((p.stdout or "").strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
