# -*- coding: utf-8 -*-
"""盘前简报：隔夜外盘 + 昨日情绪 + 今日观察要点。

每天 08:30 跑，输出到 D:\\明远阁\\reports\\premarket-YYYY-MM-DD.md 并可直接邮件发送。
"""
import datetime
import json
import os
import subprocess
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import BASE, PY, REPORT_DIR, HIST_DIR, BASELINE  # noqa: E402

OVERSEAS = [
    ("gb_dji", "道琼斯", 2),
    ("gb_ixic", "纳斯达克", 2),
    ("gb_inx", "标普500", 2),
    ("hf_CHA50CFD", "富时A50期货", 7),
    ("hf_CL", "纽约原油", 7),
    ("hf_GC", "纽约黄金", 7),
]

# 美股板块 ETF → 对应的 A 股概念
US_SECTORS = [
    ("gb_smh", "美股半导体(SMH)", "A股半导体/芯片"),
    ("gb_soxx", "美股半导体(SOXX)", "A股半导体设备/材料"),
    ("gb_botz", "美股机器人(BOTZ)", "A股机器人/自动化"),
    ("gb_xlk", "美股科技(XLK)", "A股科技成长/TMT"),
    ("gb_arkk", "美股创新(ARKK)", "A股题材成长"),
    ("gb_xlre", "美股房地产(XLRE)", "A股地产/建筑"),
    ("gb_xle", "美股能源(XLE)", "A股石油/煤炭"),
    ("gb_xlf", "美股金融(XLF)", "A股银行/券商"),
    ("gb_xlv", "美股医疗(XLV)", "A股医药"),
    ("gb_xlp", "美股必需消费(XLP)", "A股食品饮料"),
    ("gb_xlu", "美股公用事业(XLU)", "A股电力/公用"),
    ("gb_xli", "美股工业(XLI)", "A股机械/工程"),
    ("gb_xly", "美股可选消费(XLY)", "A股汽车/家电"),
    ("gb_xlb", "美股材料(XLB)", "A股化工/材料"),
    ("gb_iwm", "美股小盘(IWM)", "A股中小盘风格"),
]


def fetch_us_sectors():
    codes = ",".join(c for c, _, _ in US_SECTORS)
    req = urllib.request.Request(
        f"http://hq.sinajs.cn/list={codes}", headers={"Referer": "https://finance.sina.com.cn"})
    raw = urllib.request.urlopen(req, timeout=20).read().decode("gbk", errors="replace")
    rows = []
    for line in raw.strip().split("\n"):
        if "=" not in line:
            continue
        key = line.split("=")[0].split("hq_str_")[-1]
        body = line.split('"')[1] if '"' in line else ""
        if not body:
            continue
        v = body.split(",")
        meta = next((x for x in US_SECTORS if x[0] == key), None)
        if not meta or len(v) < 3:
            continue
        try:
            price, pct = float(v[1]), float(v[2])
        except Exception:
            continue
        rows.append((meta[1], pct, meta[2]))
    rows.sort(key=lambda x: -x[1])
    return rows
# sina 字段：gb_ 为 [名称,现价,涨跌幅,...]；hf_ 为 [现价,?,买,卖,高,低,时间,昨结,开,...]


def fetch_overseas():
    codes = ",".join(c for c, _, _ in OVERSEAS)
    req = urllib.request.Request(
        f"http://hq.sinajs.cn/list={codes}", headers={"Referer": "https://finance.sina.com.cn"})
    raw = urllib.request.urlopen(req, timeout=20).read().decode("gbk")
    out = []
    for line in raw.strip().split("\n"):
        if "=" not in line:
            continue
        key = line.split("=")[0].split("hq_str_")[-1]
        body = line.split('"')[1] if '"' in line else ""
        if not body:
            continue
        v = body.split(",")
        meta = next((x for x in OVERSEAS if x[0] == key), None)
        if not meta:
            continue
        name = meta[1]
        try:
            if key.startswith("gb_"):
                price, pct = float(v[1]), float(v[2])
            else:
                price = float(v[0])
                prev = float(v[7]) if len(v) > 7 and v[7] else 0
                pct = (price / prev - 1) * 100 if prev else None
        except Exception:
            continue
        out.append((name, price, pct))
    return out


def yesterday_stats():
    """读最近一份收盘历史，拿成交额和板块。"""
    if not os.path.isdir(HIST_DIR):
        return None
    files = sorted(f for f in os.listdir(HIST_DIR) if f.endswith(".json"))
    if not files:
        return None
    try:
        return json.load(open(os.path.join(HIST_DIR, files[-1]), encoding="utf-8"))
    except Exception:
        return None


def watch_levels():
    try:
        base = json.load(open(BASELINE, encoding="utf-8"))
    except Exception:
        base = {}
    rules = {
        "300287": ("飞利信", 3.62, 3.17),
        "600279": ("重庆港", 4.41, 3.94),
        "600094": ("大名城", 4.54, 4.20),
    }
    rows = []
    for code, (name, up, down) in rules.items():
        b = base.get(code, {})
        rows.append((code, name, up, down, b.get("low20")))
    return rows


def main():
    today = datetime.date.today().isoformat()
    L = [f"# 盘前简报 {today}", ""]

    L.append("## 一、隔夜外盘（影响今日开盘）")
    try:
        for name, price, pct in fetch_overseas():
            p = f"{pct:+.2f}%" if pct is not None else "n/a"
            L.append(f"- {name} {price:.2f}（{p}）")
    except Exception as e:
        L.append(f"- 外盘取数失败：{type(e).__name__}")
    L.append("")
    L.append("> 判断口径：纳指跌超 2% 通常压制 A 股科技成长股开盘；A50 期货反映外资对 A 股的即时定价。")
    L.append("> 若外盘大跌而 A50 跌幅明显更小，说明 A 股有独立逻辑，重点看开盘半小时能否收回。")

    L.append("")
    L.append("## 一之二、外盘板块分化（对应 A 股的概念）")
    try:
        secs = fetch_us_sectors()
        if secs:
            L.append(f"**最强 5 个**：")
            for name, pct, cn in secs[:5]:
                L.append(f"- {name} {pct:+.2f}% → {cn}")
            L.append(f"**最弱 5 个**：")
            for name, pct, cn in secs[-5:][::-1]:
                L.append(f"- {name} {pct:+.2f}% → {cn}")
            L.append("")
            L.append("> 传导判断：看跌得最狠的美股板块，是否正是昨日 A 股最强的板块。")
            L.append("> 若是，今日高开要小心冲高回落；若不是，A 股有独立逻辑，按自身量价走。")
        else:
            L.append("- 外盘板块数据为空")
    except Exception as e:
        L.append(f"- 外盘板块取数失败：{type(e).__name__}")

    st = yesterday_stats()
    L.append("")
    L.append("## 二、昨日情绪基线")
    if st:
        L.append(f"- 日期 {st.get('date')}｜两市成交额 {st.get('amount', 0):.0f} 亿")
        secs = st.get("sectors", {})
        if secs:
            top = sorted(secs.items(), key=lambda x: -x[1])[:5]
            L.append("- 昨日最强板块：" + "｜".join(f"{k} {v:+.2f}%" for k, v in top))
    else:
        L.append("- 无历史数据（首次运行后开始积累）")
    L.append("")
    L.append("> 今日看点：昨日最强板块能否延续。连续 2 日进前五才算主线，单日冲高多为一日游。")

    L.append("")
    L.append("## 三、观察池触发线")
    for code, name, up, down, low20 in watch_levels():
        L.append(f"- {code} {name}：向上 {up}｜向下 {down}" + (f"｜20日低点 {low20}" if low20 else ""))

    L.append("")
    L.append("## 四、今日纪律")
    L.append("- 开盘半小时（9:30–10:00）只看不动，等量能确认。")
    L.append("- 触发线上方追买需同时满足：量能 ≥1.5 倍、距 20 日低点 <8%。不满足就不做。")
    L.append("- 外盘大跌 + A 股低开但快速收回，是强势信号；低开后继续走弱，当天不动。")
    L.append("")
    L.append("---")
    L.append("本简报为研究记录，不构成投资建议，涉及真实资金请自行承担风险。")

    text = "\n".join(L)
    os.makedirs(REPORT_DIR, exist_ok=True)
    path = os.path.join(REPORT_DIR, f"premarket-{today}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(text)
    print(f"\n[saved] {path}")


if __name__ == "__main__":
    main()
