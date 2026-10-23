# -*- coding: utf-8 -*-
"""跑四类数据验证并打印精简摘要（ASCII only，避免控制台乱码）。"""
import json
import pathlib
import subprocess
import sys

base = pathlib.Path(__file__).resolve().parent
py = base / ".venv" / "Scripts" / "python.exe"
script = base / "market_data.py"
samples = base / "samples"
samples.mkdir(exist_ok=True)

CASES = [
    ("quote", ["quote", "000001", "600519"]),
    ("kline", ["kline", "000001", "--period", "daily", "--start", "20250901", "--end", "20251020"]),
    ("financial", ["financial", "000001"]),
    ("macro", ["macro", "--items", "gdp,cpi,ppi,m2,lpr"]),
]

summary = {}
for name, argv in CASES:
    proc = subprocess.run([str(py), str(script), *argv], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    raw = (proc.stdout or "").strip()
    out_file = samples / f"{name}.json"
    out_file.write_text(raw, encoding="utf-8")
    try:
        obj = json.loads(raw)
    except Exception as exc:
        summary[name] = f"BAD_JSON {exc} raw={raw[:120]}"
        continue
    if not obj.get("ok"):
        summary[name] = f"FAIL {obj.get('error')}"
        continue
    data = obj["data"]
    if name == "quote":
        summary[name] = "; ".join(
            f"{d.get('code')} {d.get('name')} price={d.get('price')} pct={d.get('pct_chg')} "
            f"vol={d.get('volume')} src={d.get('source')}" for d in data)
    elif name == "kline":
        first, last = data[0], data[-1]
        summary[name] = f"rows={len(data)} first={first.get('date')} close={first.get('close')} last={last.get('date')} close={last.get('close')}"
    elif name == "financial":
        abstract = data.get("abstract")
        val = data.get("valuation")
        a_ok = isinstance(abstract, list)
        v = val[0] if isinstance(val, list) and val else {}
        summary[name] = (f"abstract_rows={len(abstract) if a_ok else 'ERR'} "
                         f"valuation_date={v.get('date')} pe_ttm={v.get('pe_ttm')} "
                         f"pb={v.get('pb')} total_mv={v.get('total_mv')}")
    else:
        parts = []
        for key, item in data.items():
            if "rows" in item:
                r = item["rows"][-1]
                keys = [k for k in r if k not in ("date",)]
                parts.append(f"{key}:rows={len(item['rows'])} last={ {k: r[k] for k in keys[:3]} }")
            else:
                parts.append(f"{key}:{item.get('error')}")
        summary[name] = " | ".join(parts)

print(json.dumps(summary, ensure_ascii=True, indent=1))
