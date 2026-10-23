# -*- coding: utf-8 -*-
"""测试隔夜外盘数据源是否可用（新浪行情接口）。"""
import urllib.request

CODES = ["gb_dji", "gb_ixic", "gb_inx", "hf_CHA50CFD", "hf_CL", "hf_GC", "s_sh000001"]


def main():
    url = "http://hq.sinajs.cn/list=" + ",".join(CODES)
    req = urllib.request.Request(url, headers={"Referer": "https://finance.sina.com.cn"})
    raw = urllib.request.urlopen(req, timeout=20).read().decode("gbk")
    for line in raw.strip().split("\n"):
        print(line[:200])


if __name__ == "__main__":
    main()
