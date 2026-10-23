# -*- coding: utf-8 -*-
"""生成监控基准：每只票近 20 日日均成交量/成交额（剔除当日），供盘中量能倍率计算。

跑一次即可，建议每天盘前跑。
"""
import json
import subprocess
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import PY, SCRIPT, BASELINE as OUT  # noqa: E402
CODES = ["300287", "600279", "000514", "600094"]


def kline(code):
    out = subprocess.run(
        [PY, SCRIPT, "kline", code, "--period", "daily", "--start", "20250601", "--end", "20261231", "--adjust", "qfq"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
    )
    text = out.stdout.strip()
    start = text.find("{")
    if start < 0:
        raise RuntimeError(f"{code}: no json ({out.stderr[:200]})")
    return json.loads(text[start:])


def main():
    base = {}
    for code in CODES:
        try:
            d = kline(code)
            rows = d["data"]
            # 剔除最后一根（可能是当日未收盘 bar）
            hist = rows[:-1] if rows else []
            last20 = hist[-20:]
            avg_vol = sum(r["volume"] for r in last20) / len(last20)
            avg_amt = sum(r["amount"] for r in last20) / len(last20)
            base[code] = {
                "name": code,
                "avg_vol20": round(avg_vol, 1),
                "avg_amt20": round(avg_amt, 1),
                "last_date": last20[-1]["date"],
                "n": len(last20),
            }
            print(f"{code}: 20日均量 {avg_vol/1e4:.0f} 万股, 均额 {avg_amt/1e8:.2f} 亿, 截至 {last20[-1]['date']}")
        except Exception as e:
            print(f"{code}: FAILED {e}")
    base["_built_at"] = "auto"
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(base, f, ensure_ascii=False, indent=2)
    print("saved:", OUT)


if __name__ == "__main__":
    main()
