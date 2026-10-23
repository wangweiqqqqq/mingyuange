# -*- coding: utf-8 -*-
"""测试美股板块 ETF / 港股指数在新浪接口的可用性。"""
import urllib.request

CODES = [
    "gb_xlk", "gb_smh", "gb_soxx", "gb_xlre", "gb_botz", "gb_arkk",
    "gb_xli", "gb_xle", "gb_xlf", "gb_xlv", "gb_xly", "gb_xlp", "gb_xlu", "gb_xlb",
    "gb_qqq", "gb_spy", "gb_iwm", "gb_dia",
    "rt_hkHSI", "rt_hkHSTECH",
]


def main():
    for i in range(0, len(CODES), 10):
        batch = CODES[i:i + 10]
        req = urllib.request.Request(
            "http://hq.sinajs.cn/list=" + ",".join(batch),
            headers={"Referer": "https://finance.sina.com.cn"})
        raw = urllib.request.urlopen(req, timeout=20).read().decode("gbk", errors="replace")
        for line in raw.strip().split("\n"):
            print(line[:170])


if __name__ == "__main__":
    main()
