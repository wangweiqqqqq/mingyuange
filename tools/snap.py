# -*- coding: utf-8 -*-
"""快速行情/技术面快照：python tools/snap.py <code> [起始日] [结束日]

只做取数与基础计算（均线、RSI14、近N日高低、量能），不做买卖判断。
输出 ASCII JSON，避免控制台 GBK 乱码。
"""
import json
import pathlib
import subprocess
import sys
import datetime as dt

base = pathlib.Path(__file__).resolve().parent.parent
py = base / ".venv" / "Scripts" / "python.exe"
script = base / "market_data.py"

code = sys.argv[1] if len(sys.argv) > 1 else "000001"
end = sys.argv[2] if len(sys.argv) > 2 else dt.date.today().strftime("%Y%m%d")
start = sys.argv[3] if len(sys.argv) > 3 else (dt.date.today() - dt.timedelta(days=200)).strftime("%Y%m%d")


def run(argv):
    proc = subprocess.run([str(py), str(script), *argv], capture_output=True, text=True,
                          encoding="utf-8", errors="replace",
                          env={**__import__("os").environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
    try:
        return json.loads(proc.stdout.strip())
    except Exception:
        return {"ok": False, "raw": (proc.stdout or "")[:200], "err": (proc.stderr or "")[:300]}


out = {"code": code, "range": [start, end]}
q = run(["quote", code])
if q.get("ok"):
    out["quote"] = q["data"][0]
else:
    out["quote_error"] = q

k = run(["kline", code, "--period", "daily", "--start", start, "--end", end])
rows = k.get("data") if k.get("ok") else None
if rows:
    closes = [float(r["close"]) for r in rows]
    vols = [float(r.get("volume") or 0) for r in rows]

    def ma(n):
        return round(sum(closes[-n:]) / n, 2) if len(closes) >= n else None

    def rsi(n=14):
        if len(closes) <= n:
            return None
        gains, losses = [], []
        for i in range(1, len(closes)):
            d = closes[i] - closes[i - 1]
            gains.append(max(d, 0))
            losses.append(max(-d, 0))
        ag = sum(gains[-n:]) / n
        al = sum(losses[-n:]) / n
        if al == 0:
            return 100.0
        rs = ag / al
        return round(100 - 100 / (1 + rs), 1)

    out["kline"] = {
        "rows": len(rows),
        "first": rows[0]["date"], "first_close": rows[0]["close"],
        "last": rows[-1]["date"], "last_close": rows[-1]["close"],
        "last_pct_chg": rows[-1].get("pct_chg"),
        "high_60": max(float(r["high"]) for r in rows[-60:]),
        "low_60": min(float(r["low"]) for r in rows[-60:]),
        "ma5": ma(5), "ma10": ma(10), "ma20": ma(20), "ma60": ma(60),
        "rsi14": rsi(14),
        "vol_last": vols[-1],
        "vol_ma20": round(sum(vols[-20:]) / 20, 0) if len(vols) >= 20 else None,
        "source": rows[-1].get("source"),
    }
else:
    out["kline_error"] = k

f = run(["financial", code])
if f.get("ok"):
    d = f["data"]
    val = d.get("valuation")
    out["financial"] = {
        "abstract_rows": len(d["abstract"]) if isinstance(d.get("abstract"), list) else "ERR",
        "valuation": val[0] if isinstance(val, list) and val else val,
    }
else:
    out["financial_error"] = f

print(json.dumps(out, ensure_ascii=True, indent=1))
